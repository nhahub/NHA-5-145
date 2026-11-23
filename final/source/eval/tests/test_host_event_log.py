"""The host Agent's private, bounded, rotating event log (seam 2).

These run the real descriptor-based writer, so they need POSIX file locking and run
on Linux CI. Only the ancestor check is relaxed, because the shared temporary
folder is writable by other users; every other host file-safety check is real.
"""

import json
import os
import time

import pytest

pytestmark = pytest.mark.skipif(os.name != "posix", reason="host file safety is POSIX-only")


@pytest.fixture
def folder(tmp_path, monkeypatch):
    import deploy.host_diagnostics as diagnostics

    real = diagnostics._parent_metadata
    protected = {os.stat(path).st_ino for path in (tmp_path, *tmp_path.parents)}

    def parent(info, uid):
        if info.st_ino not in protected:
            real(info, uid)

    monkeypatch.setattr(diagnostics, "_parent_metadata", parent)
    directory = tmp_path / "agent"
    directory.mkdir(mode=0o700)
    directory.chmod(0o700)
    return directory


def emit(log, status=200):
    log.emit("http_request", method="GET", route="/sessions", status=status, duration_ms=1)


def written(directory, name="events.jsonl"):
    path = directory / name
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def test_records_are_appended_privately_as_json_lines(folder) -> None:
    from agent.event_log import EventLog
    from deploy.host_event_log import HostFileSink

    sink = HostFileSink(folder)
    log = EventLog(sink, release="b9f28e32a9b2")

    emit(log, 200)
    emit(log, 201)
    sink.flush()

    assert [(r["status"], r["release"]) for r in written(folder)] == [
        (200, "b9f28e32a9b2"),
        (201, "b9f28e32a9b2"),
    ]
    assert (folder / "events.jsonl").stat().st_mode & 0o777 == 0o600
    assert sink.failures == 0


def test_the_log_rotates_and_never_grows_past_its_limit(folder) -> None:
    from agent.event_log import EventLog
    from deploy.host_event_log import NAMES, HostFileSink

    sink = HostFileSink(folder, file_bytes=2000)
    log = EventLog(sink)

    for status in range(200, 400):
        emit(log, status)
    sink.flush()

    assert sorted(p.name for p in folder.iterdir()) == sorted(NAMES)
    assert all((folder / name).stat().st_size <= 2000 for name in NAMES)
    kept = [r["status"] for name in reversed(NAMES) for r in written(folder, name)]
    assert kept[-1] == 399 and kept == sorted(kept) and 200 not in kept


def test_files_untouched_for_seven_days_are_pruned_on_the_next_write(folder) -> None:
    from agent.event_log import EventLog
    from deploy.host_event_log import HostFileSink

    old = folder / "events.jsonl.2"
    old.write_text('{"event":"http_request"}\n')
    old.chmod(0o600)
    stale = time.time() - 8 * 24 * 3600
    os.utime(old, (stale, stale))
    sink = HostFileSink(folder)

    emit(EventLog(sink))
    sink.flush()

    assert not old.exists()


@pytest.mark.parametrize("unsafe", ["symlink", "shared_folder", "hard_link"])
def test_unsafe_targets_are_refused_and_counted_never_raised(folder, tmp_path, unsafe) -> None:
    from agent.event_log import EventLog
    from deploy.host_event_log import HostFileSink

    outside = tmp_path / "outside.jsonl"
    outside.write_text("")
    outside.chmod(0o600)
    if unsafe == "symlink":
        (folder / "events.jsonl").symlink_to(outside)
    elif unsafe == "hard_link":
        os.link(outside, folder / "events.jsonl")
    else:
        folder.chmod(0o755)
    sink = HostFileSink(folder)

    emit(EventLog(sink))
    sink.flush()

    assert sink.failures == 1
    assert outside.read_text() == ""


def test_a_full_queue_is_counted_by_the_log_and_never_blocks(folder, monkeypatch) -> None:
    import threading

    import deploy.host_event_log as host_event_log
    from agent.event_log import EventLog

    release = threading.Event()
    real = host_event_log.append_line

    def stalled(*args, **kwargs):
        release.wait(5)
        real(*args, **kwargs)

    monkeypatch.setattr(host_event_log, "append_line", stalled)
    sink = host_event_log.HostFileSink(folder, capacity=1)
    log = EventLog(sink)

    started = time.monotonic()
    for status in range(200, 205):
        emit(log, status)
    elapsed = time.monotonic() - started
    release.set()
    sink.flush()

    assert elapsed < 1
    assert log.failures >= 3
