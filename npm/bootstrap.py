"""Prepare an offline environment for this exact bundle and Python interpreter."""

import contextlib
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import venv
from pathlib import Path


@contextlib.contextmanager
def lock(path, timeout=120):
    with path.open("a+b") as stream:
        stream.seek(0)
        stream.write(b"0")
        stream.flush()
        start = time.monotonic()
        while True:
            stream.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() - start >= timeout:
                    raise RuntimeError("Timed out waiting for environment initialization")
                time.sleep(0.1)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def main():
    root = Path(__file__).resolve().parent.parent
    manifest = json.loads((root / "wheelhouse/manifest.json").read_text(encoding="utf-8"))
    wheel = root / "wheelhouse" / manifest["wheel"]
    actual = hashlib.sha256(wheel.read_bytes()).hexdigest()
    if actual != manifest["sha256"]:
        raise RuntimeError("Bundled wheel integrity check failed")
    key = hashlib.sha256((actual + sys.executable + sys.implementation.cache_tag +
                          platform.machine() + sys.version).encode()).hexdigest()[:24]
    base = Path(os.environ.get("SKILL_ASSESSMENT_HOME", Path.home() / ".cache" / "skill-assessment")).expanduser()
    base.mkdir(parents=True, exist_ok=True)
    target = base / key
    python = target / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    marker = target / "ready.json"
    with lock(base / (key + ".lock")):
        if not python.is_file() or not marker.is_file() or marker.read_text() != actual:
            if target.exists():
                shutil.rmtree(target)
            print("Preparing skill-assessment's offline Python environment...", file=sys.stderr)
            try:
                venv.EnvBuilder(with_pip=True).create(target)
                subprocess.run(
                    [str(python), "-I", "-m", "pip", "--isolated", "--disable-pip-version-check",
                     "install", "--no-index", "--no-deps", "--no-cache-dir", "--require-hashes",
                     "--find-links", str(root / "wheelhouse"), "-r", str(root / "wheelhouse/requirements.txt")],
                    check=True, stdout=sys.stderr, stderr=sys.stderr, stdin=subprocess.DEVNULL)
                marker.write_text(actual)
            except BaseException:
                shutil.rmtree(target, ignore_errors=True)
                raise
    args = [str(python), "-I", "-m", "skill_assessment", *sys.argv[1:]]
    if os.name != "nt":
        os.execv(str(python), args)
    return subprocess.call(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:
        print(f"Initialization failed: {exc}", file=sys.stderr)
        raise SystemExit(2)
