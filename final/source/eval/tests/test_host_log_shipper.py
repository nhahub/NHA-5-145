"""Shipping host event records to CloudWatch Logs (seam 3: a fake CloudWatch client)."""

import json
import os

import pytest

GROUP = "/scpilot/agent-events"


class FakeLogs:
    """Records put_log_events calls; can be made unreachable or missing its stream."""

    class exceptions:
        class ResourceNotFoundException(Exception):
            pass

        class ResourceAlreadyExistsException(Exception):
            pass

        class InvalidParameterException(Exception):
            pass

    def __init__(self, *, streams=("agent-local",)):
        self.sent = []
        self.calls = 0
        self.streams = set(streams)
        self.unreachable = False
        self.rejects = set()

    def create_log_stream(self, *, logGroupName, logStreamName):
        assert logGroupName == GROUP
        if logStreamName in self.streams:
            raise self.exceptions.ResourceAlreadyExistsException()
        self.streams.add(logStreamName)

    def put_log_events(self, *, logGroupName, logStreamName, logEvents):
        self.calls += 1
        if any(json.loads(e["message"]).get("status") in self.rejects for e in logEvents):
            raise self.exceptions.InvalidParameterException()
        if logEvents[-1]["timestamp"] - logEvents[0]["timestamp"] > 24 * 3600 * 1000:
            raise self.exceptions.InvalidParameterException()
        if self.unreachable:
            raise ConnectionError("CloudWatch unreachable")
        if logStreamName not in self.streams:
            raise self.exceptions.ResourceNotFoundException()
        assert logGroupName == GROUP
        assert [e["timestamp"] for e in logEvents] == sorted(e["timestamp"] for e in logEvents)
        self.sent.extend(json.loads(e["message"]) for e in logEvents)
        return {}


NOW = 1794996060.0  # 2026-11-18T10:01:00Z


def line(status, *, debug=False, second=1, day="2026-11-18"):
    record = {
        "time": f"{day}T10:00:{second:02d}.000+00:00",
        "release": "local",
        "event": "debug" if debug else "http_request",
        "status": status,
    }
    if debug:
        record.update(debug=True, kind="shopper_message", text="عايز كوتشي")
    return json.dumps(record, ensure_ascii=True) + "\n"


def append(folder, text, name="events.jsonl"):
    with open(folder / name, "a", encoding="ascii", newline="\n") as file:
        file.write(text)
    (folder / name).chmod(0o600)  # the host refuses log files others can read


@pytest.fixture
def folders(tmp_path, monkeypatch):
    """Private folders; on Linux the host's real descriptor checks run on them.

    Only the ancestor check is relaxed, because the shared temporary folder is
    writable by other users; every other host file-safety check is real.
    """
    if os.name == "posix":
        import deploy.host_diagnostics as diagnostics

        real = diagnostics._parent_metadata
        protected = {os.stat(path).st_ino for path in (tmp_path, *tmp_path.parents)}

        def parent(info, uid):
            if info.st_ino not in protected:
                real(info, uid)

        monkeypatch.setattr(diagnostics, "_parent_metadata", parent)
    logs, state = tmp_path / "logs", tmp_path / "state"
    for folder in (logs, state):
        folder.mkdir(mode=0o700)
        folder.chmod(0o700)
    return logs, state


def shipper(folders, client):
    from deploy.host_log_shipper import Shipper

    logs, state = folders
    return Shipper(
        logs,
        client,
        group=GROUP,
        stream="agent-local",
        checkpoint=state / "ship.json",
        clock=lambda: NOW,
    )


def statuses(client):
    return [r["status"] for r in client.sent]


def test_new_records_are_shipped_once_in_order(folders) -> None:
    client = FakeLogs()
    ship = shipper(folders, client)
    append(folders[0], line(200, second=1) + line(201, second=2))

    ship.poll()
    ship.poll()
    append(folders[0], line(202, second=3))
    ship.poll()

    assert statuses(client) == [200, 201, 202]


def test_debug_records_are_never_shipped(folders) -> None:
    client = FakeLogs()
    append(folders[0], line(200) + line(0, debug=True) + line(201))

    shipper(folders, client).poll()

    assert statuses(client) == [200, 201]
    assert "كوتشي" not in json.dumps(client.sent, ensure_ascii=False)


def test_nothing_is_lost_while_cloudwatch_is_unreachable(folders) -> None:
    client = FakeLogs()
    ship = shipper(folders, client)
    append(folders[0], line(200) + line(201))
    client.unreachable = True

    assert ship.poll() is False
    client.unreachable = False
    ship.poll()

    assert statuses(client) == [200, 201]


def test_after_a_restart_shipping_resumes_without_duplicates_or_gaps(folders) -> None:
    client = FakeLogs()
    append(folders[0], line(200) + line(201))
    shipper(folders, client).poll()
    append(folders[0], line(202))

    shipper(folders, client).poll()

    assert statuses(client) == [200, 201, 202]


def test_records_left_in_a_rotated_file_go_out_before_the_new_file(folders) -> None:
    logs, _ = folders
    client = FakeLogs()
    ship = shipper(folders, client)
    append(logs, line(200, second=1))
    ship.poll()
    append(logs, line(201, second=2))
    (logs / "events.jsonl").rename(logs / "events.jsonl.1")
    append(logs, line(202, second=3))

    ship.poll()

    assert statuses(client) == [200, 201, 202]


def test_a_half_written_line_waits_until_it_is_complete(folders) -> None:
    logs, _ = folders
    client = FakeLogs()
    ship = shipper(folders, client)
    whole = line(200)
    append(logs, line(199) + whole[:20])

    ship.poll()
    append(logs, whole[20:])
    ship.poll()

    assert statuses(client) == [199, 200]


def test_a_missing_stream_is_created_and_the_batch_sent(folders) -> None:
    client = FakeLogs(streams=())
    append(folders[0], line(200))

    shipper(folders, client).poll()

    assert "agent-local" in client.streams
    assert statuses(client) == [200]


def test_events_cloudwatch_would_refuse_for_their_age_are_skipped_not_stuck(folders) -> None:
    client = FakeLogs()
    append(
        folders[0],
        line(100, day="2026-10-01") + line(200) + line(300, day="2026-11-19"),
    )

    shipper(folders, client).poll()

    assert statuses(client) == [200]


def test_a_batch_cloudwatch_rejects_is_skipped_so_later_records_still_go(folders) -> None:
    client = FakeLogs()
    client.rejects = {500}
    ship = shipper(folders, client)
    append(folders[0], line(500))
    ship.poll()
    append(folders[0], line(201))

    ship.poll()

    assert statuses(client) == [201]


def test_records_spanning_more_than_a_day_go_in_separate_batches(folders) -> None:
    client = FakeLogs()
    append(folders[0], line(200, day="2026-11-16") + line(201, day="2026-11-18"))

    shipper(folders, client).poll()

    assert statuses(client) == [200, 201]
    assert client.calls == 2


def test_records_already_shipped_are_not_resent_when_their_file_is_gone(folders) -> None:
    logs, _ = folders
    client = FakeLogs()
    ship = shipper(folders, client)
    append(logs, line(200, second=1))
    ship.poll()
    # The checkpointed file is rotated away and pruned; a new file holds a new record.
    (logs / "events.jsonl").unlink()
    append(logs, line(200, second=1) + line(201, second=2), name="events.jsonl.1")
    append(logs, line(202, second=3))

    ship.poll()

    assert statuses(client) == [200, 201, 202]


def test_a_truncated_or_replaced_file_is_read_from_its_start(folders) -> None:
    logs, _ = folders
    client = FakeLogs()
    ship = shipper(folders, client)
    append(logs, line(200, second=1) + line(201, second=2))
    ship.poll()
    (logs / "events.jsonl").write_text(line(202, second=3), encoding="ascii")
    (logs / "events.jsonl").chmod(0o600)

    ship.poll()

    assert statuses(client) == [200, 201, 202]


def test_an_unreadable_checkpoint_starts_over_without_crashing(folders) -> None:
    _, state = folders
    client = FakeLogs()
    (state / "ship.json").write_text("{not json")
    (state / "ship.json").chmod(0o600)
    append(folders[0], line(200))

    assert shipper(folders, client).poll() is True
    assert statuses(client) == [200]


def test_stopping_closes_the_client_and_ends_the_thread(folders) -> None:
    class Closable(FakeLogs):
        closed = False

        def close(self):
            self.closed = True

    client = Closable()
    ship = shipper(folders, client)
    ship.start(interval=0.01)

    ship.stop()

    assert client.closed and not ship.running
