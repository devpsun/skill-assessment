"""Build the complete npm package using only Python's standard library."""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from build_backend import VERSION, build_wheel


def build(name=None):
    stage = ROOT / "dist" / "npm"
    if stage.exists():
        shutil.rmtree(stage)
    (stage / "bin").mkdir(parents=True)
    (stage / "python").mkdir()
    shutil.copyfile(ROOT / "npm/skill-assessment.js", stage / "bin/skill-assessment.js")
    (stage / "bin/skill-assessment.js").chmod(0o755)
    shutil.copyfile(ROOT / "npm/bootstrap.py", stage / "python/bootstrap.py")
    package = json.loads((ROOT / "package.json").read_text())
    if package["version"] != VERSION:
        raise RuntimeError("Python/npm versions differ")
    if name:
        package["name"] = name
    package.pop("scripts", None)
    package.pop("private", None)
    (stage / "package.json").write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8")
    for filename in ("README.md", "LICENSE", "THIRD_PARTY_NOTICES.md"):
        shutil.copyfile(ROOT / filename, stage / filename)
    shutil.copytree(ROOT / "examples", stage / "examples",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".skill-assessment-runs"))
    shutil.copytree(ROOT / "docs", stage / "docs")
    filename = build_wheel(stage / "wheelhouse")
    digest = hashlib.sha256((stage / "wheelhouse" / filename).read_bytes()).hexdigest()
    (stage / "wheelhouse/manifest.json").write_text(json.dumps({"wheel": filename, "sha256": digest}) + "\n")
    (stage / "wheelhouse/requirements.txt").write_text(f"skill-assessment=={VERSION} --hash=sha256:{digest}\n")
    # Invoke npm's JavaScript entry directly on Windows to avoid cmd path expansion.
    npm = shutil.which("npm")
    if not npm:
        raise RuntimeError("npm is required for packing")
    if sys.platform == "win32":
        script = Path(npm).parent / "node_modules/npm/bin/npm-cli.js"
        if not script.is_file():
            raise RuntimeError("Cannot locate npm-cli.js next to npm; run npm pack in dist/npm manually")
        command = [shutil.which("node"), str(script)]
    else:
        command = [npm]
    run = subprocess.run([*command, "pack", "--offline", "--ignore-scripts", "--json", "--pack-destination", str(ROOT / "dist")],
                         cwd=stage, check=True, capture_output=True, text=True, encoding="utf-8")
    record = json.loads(run.stdout)[0]
    path = ROOT / "dist" / record["filename"]
    print(json.dumps({"package": str(path), "wheel_sha256": digest,
                      "files": len(record["files"])}, indent=2))
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", help="Optional internal npm name, for example @your-scope/skill-assessment")
    arguments = parser.parse_args()
    build(arguments.name)
