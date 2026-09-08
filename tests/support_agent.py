"""Test-only protocol peer with explicit error modes."""
import json
import subprocess
import sys
import time
from pathlib import Path

request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
mode = request["parameters"].get("mode", "success")
if mode == "exit":
    raise SystemExit(3)
if mode == "timeout":
    time.sleep(20)
if mode == "missing":
    raise SystemExit(0)
if mode == "invalid":
    Path(sys.argv[2]).write_text("not-json")
    raise SystemExit(0)
workspace = Path(request["workspace"])
if mode == "leak-check":
    files = [p.name for p in workspace.rglob("*")]
    if "eval.yaml" in files or "case.yaml" in files or "judge.py" in files:
        raise SystemExit(9)
output = request["messages"][0]["content"]
if mode == "judge":
    output = json.dumps({"score": 0.9, "evidence": "The expected behavior was observed."})
if mode == "bad-judge":
    output = json.dumps({"score": "high", "evidence": ""})
artifacts = []
if mode == "artifact":
    (workspace / "data.json").write_text('{"answer":42}', encoding="utf-8")
    artifacts = ["data.json"]
if mode == "escape":
    artifacts = ["../outside.txt"]
Path(sys.argv[2]).write_text(json.dumps({"protocol_version": "1", "status": "completed",
                                        "final_output": output, "artifacts": artifacts}), encoding="utf-8")
