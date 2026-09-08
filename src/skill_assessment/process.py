"""Bounded child processes, including Windows Job Object lifetime management."""

import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

from .common import AssessmentError


def check_cancelled():
    token = os.environ.get("SKILL_ASSESSMENT_CANCEL_FILE")
    if token and Path(token).is_file():
        raise KeyboardInterrupt


def executable_command(command):
    """Resolve npm's generated Node shim without interpreting user arguments in cmd."""
    import shutil
    command = list(command)
    if command[0] == "{python}":
        command[0] = sys.executable
    found = shutil.which(command[0])
    if not found:
        raise AssessmentError(f"Executable not found: {command[0]}")
    if os.name == "nt" and Path(found).suffix.lower() in (".cmd", ".bat"):
        text = Path(found).read_text(encoding="utf-8-sig")
        matches = re.findall(r'"%dp0%\\([^"\r\n]+\.(?:js|cjs|mjs))"', text, re.I)
        if not matches:
            raise AssessmentError("Unsupported cmd/bat wrapper. Configure its executable or Node script directly.")
        script = (Path(found).parent / matches[-1]).resolve()
        node = Path(found).parent / "node.exe"
        node_path = str(node) if node.is_file() else shutil.which("node")
        if not node_path or not script.is_file():
            raise AssessmentError("npm shim references missing Node executable or JavaScript entry")
        return [node_path, str(script), *command[1:]]
    return [found, *command[1:]]


class WindowsJob:
    """Kill-on-close job; process is assigned before its main thread is resumed."""

    def __init__(self, process):
        import ctypes as c
        from ctypes import wintypes as w
        self.c, self.k = c, c.WinDLL("kernel32", use_last_error=True)

        class Basic(c.Structure):
            _fields_ = [("PerProcessUserTimeLimit", c.c_int64), ("PerJobUserTimeLimit", c.c_int64),
                        ("LimitFlags", w.DWORD), ("MinimumWorkingSetSize", c.c_size_t),
                        ("MaximumWorkingSetSize", c.c_size_t), ("ActiveProcessLimit", w.DWORD),
                        ("Affinity", c.c_size_t), ("PriorityClass", w.DWORD),
                        ("SchedulingClass", w.DWORD)]

        class IO(c.Structure):
            _fields_ = [(n, c.c_uint64) for n in
                        ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                         "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class Extended(c.Structure):
            _fields_ = [("BasicLimitInformation", Basic), ("IoInfo", IO),
                        ("ProcessMemoryLimit", c.c_size_t), ("JobMemoryLimit", c.c_size_t),
                        ("PeakProcessMemoryUsed", c.c_size_t), ("PeakJobMemoryUsed", c.c_size_t)]

        self.k.CreateJobObjectW.argtypes = [c.c_void_p, w.LPCWSTR]
        self.k.CreateJobObjectW.restype = w.HANDLE
        self.k.SetInformationJobObject.argtypes = [w.HANDLE, c.c_int, c.c_void_p, w.DWORD]
        self.k.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        self.k.CloseHandle.argtypes = [w.HANDLE]
        self.handle = self.k.CreateJobObjectW(None, None)
        info = Extended()
        info.BasicLimitInformation.LimitFlags = 0x2000
        if not self.handle or not self.k.SetInformationJobObject(self.handle, 9, c.byref(info), c.sizeof(info)):
            self.close()
            raise AssessmentError(f"Cannot create Windows process job: {c.get_last_error()}")
        if not self.k.AssignProcessToJobObject(self.handle, w.HANDLE(int(process._handle))):
            self.close()
            raise AssessmentError(f"Cannot assign Windows process job: {c.get_last_error()}")
        # Popen closes its thread handle. Find the suspended thread using documented APIs.
        class ThreadEntry(c.Structure):
            _fields_ = [("dwSize", w.DWORD), ("cntUsage", w.DWORD), ("th32ThreadID", w.DWORD),
                        ("th32OwnerProcessID", w.DWORD), ("tpBasePri", w.LONG),
                        ("tpDeltaPri", w.LONG), ("dwFlags", w.DWORD)]

        self.k.CreateToolhelp32Snapshot.argtypes = [w.DWORD, w.DWORD]
        self.k.CreateToolhelp32Snapshot.restype = w.HANDLE
        self.k.Thread32First.argtypes = [w.HANDLE, c.POINTER(ThreadEntry)]
        self.k.Thread32Next.argtypes = [w.HANDLE, c.POINTER(ThreadEntry)]
        self.k.OpenThread.argtypes = [w.DWORD, w.BOOL, w.DWORD]
        self.k.OpenThread.restype = w.HANDLE
        self.k.ResumeThread.argtypes = [w.HANDLE]
        self.k.ResumeThread.restype = w.DWORD
        snapshot = self.k.CreateToolhelp32Snapshot(4, 0)
        resumed = False
        if snapshot and snapshot != c.c_void_p(-1).value:
            try:
                entry = ThreadEntry()
                entry.dwSize = c.sizeof(entry)
                exists = self.k.Thread32First(snapshot, c.byref(entry))
                while exists:
                    if entry.th32OwnerProcessID == process.pid:
                        thread = self.k.OpenThread(2, False, entry.th32ThreadID)
                        if thread:
                            try:
                                resumed = self.k.ResumeThread(thread) != 0xFFFFFFFF
                            finally:
                                self.k.CloseHandle(thread)
                        break
                    exists = self.k.Thread32Next(snapshot, c.byref(entry))
            finally:
                self.k.CloseHandle(snapshot)
        if not resumed:
            self.close()
            raise AssessmentError(f"Cannot resume child process: {c.get_last_error()}")

    def close(self):
        if getattr(self, "handle", None):
            self.k.CloseHandle(self.handle)
            self.handle = None


def run_process(command, cwd, log_dir, timeout=120, input_text="", max_log_bytes=8 * 1024 * 1024):
    check_cancelled()
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    args = executable_command(command)
    start = time.monotonic()
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    job = proc = None
    status = "completed"
    # Files avoid pipe-buffer deadlocks and keep partial evidence on cancellation.
    with (log_dir / "stdin.txt").open("wb") as f:
        f.write(input_text.encode("utf-8"))
    with (log_dir / "stdin.txt").open("rb") as inp, \
            (log_dir / "stdout.txt").open("wb") as out, (log_dir / "stderr.txt").open("wb") as err:
        try:
            kw = {"creationflags": 0x00000004 | 0x08000000} if os.name == "nt" else {"start_new_session": True}
            proc = subprocess.Popen(args, cwd=cwd, env=env, stdin=inp, stdout=out, stderr=err, **kw)
            if os.name == "nt":
                job = WindowsJob(proc)
            while proc.poll() is None:
                check_cancelled()
                if time.monotonic() - start > timeout:
                    status = "timeout"
                    break
                if (log_dir / "stdout.txt").stat().st_size + (log_dir / "stderr.txt").stat().st_size > max_log_bytes:
                    status = "output_limit"
                    break
                time.sleep(0.03)
        finally:
            if proc:
                if job:
                    job.close()
                elif os.name == "nt":
                    if proc.poll() is None:
                        proc.kill()
                else:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                proc.wait()
    for p in (log_dir / "stdout.txt", log_dir / "stderr.txt"):
        if p.stat().st_size > max_log_bytes:
            with p.open("r+b") as f:
                f.truncate(max_log_bytes)
            status = "output_limit"
    return {"status": status, "returncode": proc.returncode,
            "duration_seconds": round(time.monotonic() - start, 6),
            "stdout": (log_dir / "stdout.txt").read_text(encoding="utf-8", errors="replace"),
            "stderr": (log_dir / "stderr.txt").read_text(encoding="utf-8", errors="replace")}
