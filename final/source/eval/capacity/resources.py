"""Bounded native process sampling, excluding the load generator/browser."""

import json
import os
import subprocess
import threading
from time import monotonic


def process_usage(pid):
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class Memory(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
                (name, ctypes.c_size_t)
                for name in (
                    "peak_rss",
                    "rss",
                    "peak_paged",
                    "paged",
                    "peak_nonpaged",
                    "nonpaged",
                    "pagefile",
                    "peak_pagefile",
                )
            ]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [
            ctypes.POINTER(wintypes.FILETIME)
        ] * 4
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(Memory),
            wintypes.DWORD,
        ]
        handle = kernel.OpenProcess(0x1000 | 0x10, False, pid)
        if not handle:
            raise OSError("Process sampling unavailable")
        try:
            times = [wintypes.FILETIME() for _ in range(4)]
            memory = Memory()
            memory.cb = ctypes.sizeof(memory)
            if not kernel.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)) or not (
                psapi.GetProcessMemoryInfo(handle, ctypes.byref(memory), memory.cb)
            ):
                raise OSError("Process sampling unavailable")
            ticks = sum((t.dwHighDateTime << 32) + t.dwLowDateTime for t in times[2:])
            return ticks / 10_000_000, memory.rss
        finally:
            kernel.CloseHandle(handle)
    if os.name == "posix" and os.path.isdir("/proc"):
        from pathlib import Path

        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        pages = int(Path(f"/proc/{pid}/statm").read_text().split()[1])
        return (int(fields[11]) + int(fields[12])) / os.sysconf("SC_CLK_TCK"), (
            pages * os.sysconf("SC_PAGE_SIZE")
        )
    raise RuntimeError("Native process sampling requires Windows or Linux")


class Resources:
    def __init__(self, processes):
        self.processes = processes
        self.pids = {name: [process.pid] for name, process in processes.items()}
        if os.name == "nt":
            # The venv launcher owns a second Python process. Sample its whole
            # owned tree, rather than claiming the idle launcher's RSS as Agent RAM.
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    "Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId "
                    "| ConvertTo-Json -Compress",
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            rows = json.loads(result.stdout)
            for ids in self.pids.values():
                for _ in range(8):
                    children = {r["ProcessId"] for r in rows if r["ParentProcessId"] in ids}
                    if children.issubset(ids):
                        break
                    ids[:] = sorted(set(ids) | children)
        self.samples = []
        self.finished = threading.Event()
        self.worker = threading.Thread(target=self._sample, daemon=True)

    def _sample(self):
        while not self.finished.is_set() and len(self.samples) < 600:
            row = {"seconds": monotonic(), "processes": {}}
            for name, ids in self.pids.items():
                try:
                    usages = [process_usage(pid) for pid in ids]
                    cpu, rss = sum(u[0] for u in usages), sum(u[1] for u in usages)
                    row["processes"][name] = {"cpu_seconds": cpu, "rss_bytes": rss}
                except OSError:
                    row["processes"][name] = None
            self.samples.append(row)
            self.finished.wait(0.1)

    def __enter__(self):
        self.worker.start()
        return self

    def __exit__(self, *_args):
        self.finished.set()
        self.worker.join(timeout=2)

    def summary(self):
        output = {}
        for name in self.processes:
            rows = [
                (r["seconds"], r["processes"][name])
                for r in self.samples
                if r["processes"][name] is not None
            ]
            if len(rows) < 2:
                raise RuntimeError("Insufficient process sampling evidence")
            elapsed = rows[-1][0] - rows[0][0]
            output[name] = {
                "peak_rss_mib": max(r[1]["rss_bytes"] for r in rows) / 2**20,
                "cpu_percent_one_core": 100
                * (rows[-1][1]["cpu_seconds"] - rows[0][1]["cpu_seconds"])
                / elapsed,
                "samples": len(rows),
            }
        return output
