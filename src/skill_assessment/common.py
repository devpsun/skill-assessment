"""Serialization and filesystem boundaries shared by the evaluator."""

import hashlib
import json
import math
import os
import tempfile
from pathlib import Path, PureWindowsPath


class AssessmentError(Exception):
    """An actionable configuration or execution problem."""


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path, max_bytes=16 * 1024 * 1024):
    path = Path(path)
    if path.stat().st_size > max_bytes:
        raise AssessmentError(f"JSON exceeds {max_bytes} bytes: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"),
                          parse_constant=lambda x: (_ for _ in ()).throw(
                              ValueError(f"Non-finite JSON value: {x}")))
    except (ValueError, UnicodeError) as exc:
        raise AssessmentError(f"Invalid JSON {path}: {exc}") from exc


def write_json(path, value):
    """Atomic replacement; readers never observe a partially written result."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))
            stream.write("\n")
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def relative_path(value):
    """Portable workspace paths; reject Windows traversal even on POSIX."""
    if not isinstance(value, str) or not value or "\x00" in value:
        raise AssessmentError("Expected a non-empty relative path")
    if "\\" in value or Path(value).is_absolute() or PureWindowsPath(value).drive:
        raise AssessmentError(f"Use a relative path with forward slashes: {value}")
    if any(p in ("", ".", "..") for p in value.split("/")):
        raise AssessmentError(f"Invalid relative path: {value}")
    for part in value.split("/"):
        if (any(c in part for c in '<>:"|?*') or any(ord(c) < 32 for c in part)
                or part.endswith((" ", ".")) or PureWindowsPath(part).is_reserved()):
            raise AssessmentError(f"Path is not portable to Windows: {value}")
    return value


def contained(root, value):
    root = Path(root).resolve()
    path = root / relative_path(value)
    if not path.resolve().is_relative_to(root):
        raise AssessmentError(f"Path escapes workspace: {value}")
    return path


def positive(value, label, maximum=86400):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AssessmentError(f"{label} must be a number")
    if not math.isfinite(value) or not 0 < value <= maximum:
        raise AssessmentError(f"{label} must be > 0 and <= {maximum}")
    return value


def object_keys(value, allowed, required=(), label="object"):
    if not isinstance(value, dict) or not all(isinstance(k, str) for k in value):
        raise AssessmentError(f"{label} must be an object with string keys")
    unknown, missing = set(value) - set(allowed), set(required) - set(value)
    if unknown:
        raise AssessmentError(f"{label}: unknown fields {sorted(unknown)}")
    if missing:
        raise AssessmentError(f"{label}: missing fields {sorted(missing)}")
    return value


def strings(value, label, nonempty=False):
    if not isinstance(value, list) or not all(isinstance(x, str) and x for x in value):
        raise AssessmentError(f"{label} must be an array of non-empty strings")
    if nonempty and not value:
        raise AssessmentError(f"{label} cannot be empty")
    return value
