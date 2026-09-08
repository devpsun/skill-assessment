"""Snapshot inputs and archive only explicit, contained artifacts."""

import fnmatch
import os
import shutil
from pathlib import Path

from .common import AssessmentError, contained, file_hash

DEFAULT_EXCLUDES = {".git", ".venv", "node_modules", "__pycache__", "evals",
                    ".skill-assessment-runs", ".claude", ".codex"}


def copy_skill(source, destination, exclude=(), forbidden=()):
    source, destination = Path(source).resolve(), Path(destination)
    blocked = [Path(p).resolve() for p in forbidden]
    manifest = {}
    total = 0
    def paths():
        for directory, dirs, files in os.walk(source, followlinks=False):
            kept = []
            for name in sorted(dirs):
                path = Path(directory) / name
                relative = path.relative_to(source).as_posix()
                if (name in DEFAULT_EXCLUDES or any(fnmatch.fnmatch(relative, x) for x in exclude)
                        or any(path.resolve() == p or path.resolve().is_relative_to(p) for p in blocked)):
                    continue
                if path.is_symlink():
                    raise AssessmentError(f"Symlinks are not supported in Skill snapshots: {relative}")
                kept.append(name)
            dirs[:] = kept
            for name in sorted(files):
                yield Path(directory) / name

    for path in paths():
        rel = path.relative_to(source)
        name = rel.as_posix()
        if any(p in DEFAULT_EXCLUDES for p in rel.parts) or any(fnmatch.fnmatch(name, x) for x in exclude):
            continue
        if path.is_symlink():
            raise AssessmentError(f"Symlinks are not supported in Skill snapshots: {name}")
        if any(path.resolve() == p or (p.is_dir() and path.resolve().is_relative_to(p)) for p in blocked):
            continue
        if not path.is_file():
            continue
        total += path.stat().st_size
        if total > 64 * 1024 * 1024 or len(manifest) >= 2000:
            raise AssessmentError("Skill snapshot exceeds 64 MiB or 2000 files")
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        manifest[name] = file_hash(target)
    if "SKILL.md" not in manifest:
        raise AssessmentError("Snapshot must include SKILL.md")
    return manifest


def archive_artifacts(workspace, destination, paths):
    if not isinstance(paths, list) or not all(isinstance(x, str) for x in paths):
        raise AssessmentError("artifacts must be a list of relative file paths")
    if len(paths) > 100:
        raise AssessmentError("Artifact count exceeds 100")
    records, total = [], 0
    for value in dict.fromkeys(paths):
        path = contained(workspace, value)
        if not path.is_file():
            raise AssessmentError(f"Missing artifact: {value}")
        size = path.stat().st_size
        total += size
        if total > 32 * 1024 * 1024:
            raise AssessmentError("Artifacts exceed 32 MiB")
        target = contained(destination, value)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        records.append({"path": value, "size_bytes": size, "sha256": file_hash(target)})
    return records
