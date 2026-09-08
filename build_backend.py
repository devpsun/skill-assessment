"""Small stdlib-only PEP 517 backend for a pure Python, vendored distribution."""

import base64
import csv
import hashlib
import io
import tarfile
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
VERSION = PROJECT["version"]
NAME = "skill_assessment"


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    directory = Path(wheel_directory)
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{NAME}-{VERSION}-py3-none-any.whl"
    info = f"{NAME}-{VERSION}.dist-info"
    content = {}
    for p in sorted((ROOT / "src" / NAME).rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts and p.suffix not in (".pyc", ".pyo"):
            content[p.relative_to(ROOT / "src").as_posix()] = p.read_bytes()
    content[f"{info}/METADATA"] = (
        f"Metadata-Version: 2.4\nName: skill-assessment\nVersion: {VERSION}\n"
        f"Summary: {PROJECT['description']}\nRequires-Python: >=3.11\n"
        "License-Expression: Apache-2.0 AND MIT\n"
        "License-File: LICENSE\nLicense-File: PyYAML-LICENSE\n"
        "Description-Content-Type: text/markdown\n\n" + (ROOT / "README.md").read_text(encoding="utf-8")
    ).encode("utf-8")
    content[f"{info}/WHEEL"] = b"Wheel-Version: 1.0\nGenerator: skill-assessment-build\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
    content[f"{info}/entry_points.txt"] = b"[console_scripts]\nskill-assessment = skill_assessment.cli:main\n"
    content[f"{info}/licenses/LICENSE"] = (ROOT / "LICENSE").read_bytes()
    content[f"{info}/licenses/PyYAML-LICENSE"] = (ROOT / "src" / NAME / "_vendor/yaml/LICENSE").read_bytes()
    records = io.StringIO(newline="")
    writer = csv.writer(records, lineterminator="\n")
    for path, value in sorted(content.items()):
        h = base64.urlsafe_b64encode(hashlib.sha256(value).digest()).rstrip(b"=").decode()
        writer.writerow([path, "sha256=" + h, len(value)])
    writer.writerow([f"{info}/RECORD", "", ""])
    content[f"{info}/RECORD"] = records.getvalue().encode("utf-8")
    with zipfile.ZipFile(directory / filename, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, value in sorted(content.items()):
            entry = zipfile.ZipInfo(path, (2020, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            archive.writestr(entry, value)
    return filename


def build_sdist(sdist_directory, config_settings=None):
    directory = Path(sdist_directory)
    directory.mkdir(parents=True, exist_ok=True)
    name = f"{NAME}-{VERSION}"
    with tarfile.open(directory / f"{name}.tar.gz", "w:gz") as archive:
        for item in ("src", "build_backend.py", "pyproject.toml", "README.md", "LICENSE"):
            archive.add(ROOT / item, arcname=f"{name}/{item}",
                        filter=lambda info: None if "__pycache__" in info.name or info.name.endswith(".pyc") else info)
    return f"{name}.tar.gz"


def get_requires_for_build_wheel(config_settings=None):
    return []


def get_requires_for_build_sdist(config_settings=None):
    return []
