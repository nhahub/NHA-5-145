"""Disposable Linux UID/log/packet proof; synthetic state and no external network."""

import fcntl
import hashlib
import json
import os
import socket
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

WORK = Path("/rehearsal")
RELEASE = WORK / "release"
STATE = WORK / "state"
AGENT, STORE, PROXY, CATALOGUE = 10001, 10002, 10003, 10004
PYTHON = sys.executable


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def demote(uid):
    def apply():
        os.setgroups([CATALOGUE] if uid == AGENT else [])
        os.setgid(uid)
        os.setuid(uid)
        os.umask(0o027 if uid == STORE else 0o077)

    return apply


def spawn(uid, source, *, capture=True):
    return subprocess.Popen(
        [
            PYTHON,
            "-I",
            "-S",
            "-B",
            "-c",
            "import sys;sys.path.insert(0,'/rehearsal/release');" + source,
        ],
        preexec_fn=demote(uid),
        env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )


def run(uid, source):
    child = spawn(uid, source)
    out, error = child.communicate(timeout=12)
    assert child.returncode == 0, error.decode()[:2000]
    return out.decode()


def owned(path, uid, mode, *, directory=False, group=None):
    if directory:
        path.mkdir(mode=mode, parents=True, exist_ok=True)
    os.chown(path, uid, group if group is not None else uid)
    path.chmod(mode)


def prepare():
    import importlib.util

    spec = importlib.util.spec_from_file_location("host_probe", "/input/host_probe.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    inventory = json.loads(Path("/input/runtime-profile.json").read_bytes())
    assert digest(Path("/input/runtime-profile.json")) == sys.argv[1]
    assert digest(Path(__file__)) == inventory["isolation_probe_sha256"]
    assert socket.if_nameindex() == [(1, "lo")]
    for name, expected in inventory["test_tool_files"].items():
        assert digest(Path("/tools") / name) == expected
    proof = module.unpack(inventory)
    importlib.invalidate_caches()
    sys.path.insert(0, str(RELEASE))
    from deploy.artifact import files

    manifest = proof["upstream_manifest"].copy()
    manifest["files"] = files(RELEASE)
    (RELEASE / "release.json").write_text(json.dumps(manifest))
    for path in RELEASE.rglob("*"):
        if not path.is_symlink():
            path.chmod(0o755 if path.is_dir() else 0o644)
    RELEASE.chmod(0o755)
    WORK.chmod(0o755)
    STATE.mkdir(mode=0o755)
    for role, uid in (("agent", AGENT), ("store", STORE), ("proxy", PROXY)):
        owned(STATE / role, uid, 0o700, directory=True)
        owned(WORK / "logs" / role, uid, 0o700, directory=True)
    owned(STATE / "store", STORE, 0o2750, group=CATALOGUE)
    (STATE / "store/catalogue.sqlite").write_bytes(Path("/input/catalogue.sqlite").read_bytes())
    owned(STATE / "store/catalogue.sqlite", STORE, 0o640, group=CATALOGUE)
    basic = {"version": 1, "release": str(RELEASE), "fingerprint": digest(RELEASE / "release.json")}
    for role, uid in (("agent", AGENT), ("store", STORE)):
        secret = STATE / role / "service.key"
        secret.write_bytes(b"s" * 32)
        owned(secret, uid, 0o400)
    for name in ("readiness.key", "ledger.sqlite"):
        path = STATE / "agent" / name
        path.write_bytes(b"synthetic-private")
        owned(path, AGENT, 0o600)
    foreign = WORK / "logs/agent/lifecycle.jsonl.2"
    foreign.write_bytes(b"synthetic")
    owned(foreign, STORE, 0o600)
    (STATE / "store/store.json").write_text(
        json.dumps(
            {
                **basic,
                "catalogue": str(STATE / "store/catalogue.sqlite"),
                "service_secret_file": str(STATE / "store/service.key"),
            }
        )
    )
    owned(STATE / "store/store.json", STORE, 0o400)
    (STATE / "proxy/proxy.json").write_text(json.dumps(basic))
    owned(STATE / "proxy/proxy.json", PROXY, 0o400)
    return inventory, proof


def log_cases():
    from deploy.host_diagnostics import write_event

    directory = WORK / "logs/agent"
    try:
        write_event(directory, "agent", "starting")
    except PermissionError:
        pass
    else:
        raise AssertionError("Foreign log file accepted")
    (directory / "lifecycle.jsonl.2").unlink()
    alias = directory / "alias"
    alias.symlink_to(directory, target_is_directory=True)
    try:
        write_event(alias, "agent", "starting")
    except OSError:
        pass
    else:
        raise AssertionError("Symlink log directory accepted")
    alias.unlink()
    for _ in range(20):
        write_event(directory, "agent", "stopped", result="private", maximum_bytes=256)
    names = {p.name for p in directory.iterdir()}
    assert names == {"lifecycle.jsonl", "lifecycle.jsonl.1", "lifecycle.jsonl.2"}
    for path in directory.iterdir():
        assert path.stat().st_size <= 256 and path.stat().st_mode & 0o077 == 0
        for row in path.read_text().splitlines():
            assert json.loads(row)["outcome"] == "failed" and "private" not in row
        os.utime(path, (1, 1))
    untouched = directory / "unmanaged"
    untouched.write_text("retained")
    write_event(directory, "agent", "starting")
    assert {p.name for p in directory.iterdir()} == {"lifecycle.jsonl", "unmanaged"}
    active = directory / "lifecycle.jsonl"
    for case in ("symlink", "hardlink", "fifo", "mode", "oversized"):
        active.unlink()
        if case == "symlink":
            active.symlink_to(untouched)
        elif case == "hardlink":
            os.link(untouched, active)
        elif case == "fifo":
            os.mkfifo(active, 0o600)
        else:
            active.write_bytes(b"x" * (65537 if case == "oversized" else 1))
            active.chmod(0o640 if case == "mode" else 0o600)
        try:
            write_event(directory, "agent", "starting")
        except (OSError, ValueError):
            pass
        else:
            raise AssertionError(case)
    active.unlink()
    for operation, replacement in (
        ("write", OSError("full")),
        ("fsync", OSError("sync")),
        ("write", 0),
    ):
        with patch(
            "deploy.host_diagnostics.os." + operation,
            **(
                {"side_effect": replacement}
                if isinstance(replacement, Exception)
                else {"return_value": replacement}
            ),
        ):
            try:
                write_event(directory, "agent", "starting")
            except OSError:
                pass
            else:
                raise AssertionError("I/O failure hidden")
    active.unlink()
    calls = []
    original = os.fsync
    with patch(
        "deploy.host_diagnostics.os.fsync",
        side_effect=lambda fd: (calls.append(os.fstat(fd).st_mode), original(fd)),
    ):
        write_event(directory, "agent", "starting")
    assert len(calls) == 2
    child = subprocess.Popen(
        [PYTHON, "-I", "-S", "-B", "/input/isolation_probe.py", "--hold-lock"],
        stdout=subprocess.PIPE,
    )
    try:
        assert child.stdout.readline() == b"locked\n"
        started = time.monotonic()
        try:
            write_event(directory, "agent", "starting")
        except TimeoutError:
            assert 0.9 < time.monotonic() - started < 2
        else:
            raise AssertionError("Unbounded or absent lock")
    finally:
        child.terminate()
        child.wait(timeout=3)
        child.stdout.close()
    active.unlink()
    writers = [
        subprocess.Popen(
            [PYTHON, "-I", "-S", "-B", "/input/isolation_probe.py", "--write"],
            stdout=subprocess.DEVNULL,
        )
        for _ in range(8)
    ]
    assert all(child.wait(timeout=5) == 0 for child in writers)
    assert len(active.read_text().splitlines()) == 8
    return {
        "rotation": True,
        "retention": True,
        "unsafe_files_refused": 7,
        "io_failures_propagated": 3,
        "file_and_directory_fsync": True,
        "lock_timeout_seconds": 1,
        "concurrent_writers": 8,
    }


def packets():
    from deploy.host_metadata import render_metadata

    env = {"PATH": "/usr/bin:/bin", "LD_LIBRARY_PATH": "/tools/usr/lib64"}

    def nft(batch, success=True):
        result = subprocess.run(
            ["/tools/usr/sbin/nft", "-f", "-"],
            input=batch,
            env=env,
            text=True,
            capture_output=True,
            timeout=5,
        )
        assert (result.returncode == 0) == success, result.stderr

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as control:
        address = struct.pack(
            "16sH2s4s8s",
            b"lo:scpilot",
            socket.AF_INET,
            b"\0\0",
            socket.inet_aton("169.254.169.254"),
            b"\0" * 8,
        )
        fcntl.ioctl(control, 0x8916, address)
    with socket.socket(socket.AF_INET6, socket.SOCK_DGRAM) as control:
        fcntl.ioctl(
            control,
            0x8916,
            struct.pack(
                "16sII",
                socket.inet_pton(socket.AF_INET6, "fd00:ec2::254"),
                128,
                socket.if_nametoindex("lo"),
            ),
        )
    server = socket.socket()
    server.bind(("169.254.169.254", 18080))
    server.listen(16)
    server.settimeout(1)
    ipv6 = socket.socket(socket.AF_INET6)
    deadline = time.monotonic() + 3
    while True:
        try:
            ipv6.bind(("fd00:ec2::254", 18080))
            break
        except OSError:
            assert time.monotonic() < deadline, Path("/proc/net/if_inet6").read_text()
            time.sleep(0.05)
    ipv6.listen(16)
    ipv6.settimeout(1)
    ordinary = socket.socket()
    ordinary.bind(("127.0.0.1", 18081))
    ordinary.listen(16)
    ordinary.settimeout(1)
    stop = threading.Event()

    def accept(listener):
        while not stop.is_set():
            try:
                connection, _ = listener.accept()
            except TimeoutError:
                continue
            with connection:
                connection.sendall(b"synthetic")

    threads = [
        threading.Thread(target=accept, args=(listener,)) for listener in (server, ipv6, ordinary)
    ]
    for thread in threads:
        thread.start()
    try:
        nft("add table inet scpilot_sentinel\n")
        nft(render_metadata(AGENT))
        listed = subprocess.check_output(
            ["/tools/usr/sbin/nft", "-j", "list", "ruleset"], env=env, text=True, timeout=5
        )
        nft(render_metadata(AGENT))
        again = subprocess.check_output(
            ["/tools/usr/sbin/nft", "-j", "list", "ruleset"], env=env, text=True, timeout=5
        )

        def semantic(value):
            if isinstance(value, dict):
                return {key: semantic(item) for key, item in value.items() if key != "handle"}
            if isinstance(value, list):
                return [semantic(item) for item in value]
            return value

        assert semantic(json.loads(listed)) == semantic(json.loads(again))
        assert "scpilot_sentinel" in again
        nft(render_metadata(AGENT) + "invalid synthetic command\n", success=False)
        assert (
            subprocess.check_output(
                ["/tools/usr/sbin/nft", "-j", "list", "ruleset"], env=env, text=True, timeout=5
            )
            == again
        )
        for uid in (0, AGENT, STORE, PROXY, 10005):
            for family, address, port in (
                ("AF_INET", "169.254.169.254", 18080),
                ("AF_INET6", "fd00:ec2::254", 18080),
                ("AF_INET", "127.0.0.1", 18081),
            ):
                source = (
                    f"import socket;s=socket.socket(socket.{family});s.settimeout(1);"
                    f"\ntry:s.connect(('{address}',{port}));"
                    "assert s.recv(20)==b'synthetic';print('allowed')"
                    "\nexcept OSError:print('refused')\nfinally:s.close()"
                )
                expected = "allowed" if uid in {0, AGENT} or port == 18081 else "refused"
                assert run(uid, source).strip() == expected
        return {
            "ipv4_root_and_agent_allowed": True,
            "ipv6_root_and_agent_allowed": True,
            "other_three_uids_refused": True,
            "ordinary_loopback_allowed_all_uids": True,
            "ipv6_rule_installed": True,
            "repeat_idempotent": True,
            "failure_atomic": True,
            "sentinel_preserved": True,
            "actual_imds_contacted": False,
            "nft_version": subprocess.check_output(
                ["/tools/usr/sbin/nft", "--version"], env=env, text=True, timeout=5
            ).strip(),
        }
    finally:
        stop.set()
        for thread in threads:
            thread.join(timeout=2)
        for listener in (server, ipv6, ordinary):
            listener.close()


def main():
    sys.path.insert(0, str(RELEASE))
    if sys.argv[1:] == ["--logs"]:
        print(json.dumps(log_cases()))
        return
    if sys.argv[1:] == ["--hold-lock"]:
        fd = os.open(WORK / "logs/agent", os.O_RDONLY | os.O_DIRECTORY)
        fcntl.flock(fd, fcntl.LOCK_EX)
        print("locked", flush=True)
        time.sleep(10)
        return
    if sys.argv[1:] == ["--write"]:
        from deploy.host_diagnostics import write_event

        write_event(WORK / "logs/agent", "agent", "starting")
        return
    assert os.geteuid() == 0 and sys.platform == "linux"
    inventory, proof = prepare()
    for uid, role in ((STORE, "store"), (PROXY, "proxy")):
        run(
            uid,
            "from deploy.component_config import load_component_settings;from pathlib import Path;"
            f"load_component_settings(Path('/rehearsal/state/{role}/{role}.json'),'{role}')",
        )
    checks = []
    for uid, path in (
        (STORE, "agent/readiness.key"),
        (STORE, "agent/ledger.sqlite"),
        (STORE, "agent/service.key"),
        (PROXY, "agent/service.key"),
        (PROXY, "store/service.key"),
        (AGENT, "store/service.key"),
    ):
        source = (
            f"from pathlib import Path\ntry:Path('/rehearsal/state/{path}').read_bytes()\n"
            "except PermissionError:print('denied')"
        )
        assert run(uid, source).strip() == "denied"
        checks.append([uid, path])
    private_process = spawn(
        AGENT,
        "import os,time;os.environ['PRIVATE']='synthetic';print('ready',flush=True);time.sleep(60)",
    )
    try:
        assert private_process.stdout.readline() == b"ready\n"
        for uid in (STORE, PROXY):
            source = (
                "from pathlib import Path\n"
                f"try:Path('/proc/{private_process.pid}/environ').read_bytes()\n"
                "except PermissionError:print('denied')"
            )
            assert run(uid, source).strip() == "denied"
            source = (
                f"import os\ntry:os.kill({private_process.pid},0)\n"
                "except PermissionError:print('denied')"
            )
            assert run(uid, source).strip() == "denied"
        for uid, path in (
            (STORE, "agent/ledger.sqlite"),
            (PROXY, "store/catalogue.sqlite"),
            (PROXY, "agent/readiness.key"),
        ):
            source = (
                "from pathlib import Path\n"
                f"try:Path('/rehearsal/state/{path}').open('ab')\n"
                "except PermissionError:print('denied')"
            )
            assert run(uid, source).strip() == "denied"
        for uid in (AGENT, STORE, PROXY):
            assert (
                run(
                    uid,
                    "from pathlib import Path;data=Path('/proc/self/status').read_text();"
                    "assert 'CapEff:\\t0000000000000000' in data",
                )
                == ""
            )
    finally:
        private_process.terminate()
        private_process.wait(timeout=5)
        private_process.stdout.close()
        private_process.stderr.close()
    assert (
        run(
            AGENT,
            "from pathlib import Path;"
            "assert Path('/rehearsal/state/agent/service.key').read_bytes()==b's'*32",
        )
        == ""
    )
    writer = spawn(
        STORE,
        "import sqlite3,time;db=sqlite3.connect('/rehearsal/state/store/catalogue.sqlite');"
        "assert db.execute('PRAGMA journal_mode=WAL').fetchone()[0]=='wal';"
        "db.execute('UPDATE catalogue_meta SET revision=revision+1');db.commit();"
        "print('ready',flush=True);time.sleep(60)",
    )
    try:
        assert writer.stdout.readline() == b"ready\n", writer.stderr.read(2000)
        for suffix in ("-wal", "-shm"):
            info = Path(str(STATE / "store/catalogue.sqlite") + suffix).stat()
            assert info.st_gid == CATALOGUE and info.st_mode & 0o777 == 0o640, (suffix, info)
        read = (
            "from deploy.catalogue import catalogue_status;from pathlib import Path;"
            "print(catalogue_status(Path('/rehearsal/state/store/catalogue.sqlite'))['revision'])"
        )
        first = run(AGENT, read).strip()
        assert int(first) >= 2
        denied = (
            "from pathlib import Path\n"
            "try:Path('/rehearsal/state/store/catalogue.sqlite').open('ab')\n"
            "except PermissionError:print('denied')"
        )
        assert run(AGENT, denied).strip() == "denied"
        assert (
            run(
                AGENT,
                f"import os\ntry:os.kill({writer.pid},0)\nexcept PermissionError:print('denied')",
            ).strip()
            == "denied"
        )
        assert run(AGENT, read).strip() == first
    finally:
        writer.terminate()
        writer.wait(timeout=5)
        writer.stdout.close()
        writer.stderr.close()
    assert run(AGENT, read).strip() == first
    # A closed Store can remove WAL sidecars. Agent must refuse, never create them.
    run(
        STORE,
        "import sqlite3;db=sqlite3.connect('/rehearsal/state/store/catalogue.sqlite');"
        "db.execute('SELECT * FROM catalogue_meta').fetchall();db.close()",
    )
    unavailable = spawn(AGENT, read)
    _, error = unavailable.communicate(timeout=5)
    assert unavailable.returncode != 0 and b"readonly database" in error
    for _ in range(2):
        storefront = spawn(
            STORE,
            "from deploy.host_component import main;raise SystemExit(main(['--config',"
            "'/rehearsal/state/store/store.json','--component','store']))",
        )
        try:
            deadline = time.monotonic() + 10
            while True:
                assert storefront.poll() is None, storefront.stderr.read(2000)
                with socket.socket() as connection:
                    if connection.connect_ex(("127.0.0.1", 4000)) == 0:
                        break
                assert time.monotonic() < deadline
                time.sleep(0.05)
            assert run(AGENT, read).strip() == first
        finally:
            storefront.terminate()
            storefront.wait(timeout=5)
            storefront.stdout.close()
            storefront.stderr.close()
    logs = subprocess.run(
        [PYTHON, "-I", "-S", "-B", __file__, "--logs"],
        preexec_fn=demote(AGENT),
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert logs.returncode == 0, logs.stderr
    result = {
        "source_manifest_sha256": inventory["fixture"]["upstream_manifest_sha256"],
        "derived_manifest_sha256": digest(RELEASE / "release.json"),
        "probe_sha256": digest(Path(__file__)),
        "private_read_denials": checks,
        "catalogue_live_wal_and_restart": True,
        "missing_wal_sidecars_fail_closed": True,
        "native_store_multi_uid_restarts": 2,
        "catalogue_write_denied": True,
        "cross_uid_signal_denied": True,
        "store_and_proxy_agent_environment_denied": True,
        "service_children_no_effective_capabilities": True,
        "diagnostics": json.loads(logs.stdout),
        "packets": packets(),
        "systemd_boot_tested": False,
    }
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
