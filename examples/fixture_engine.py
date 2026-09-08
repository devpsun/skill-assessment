"""Deterministic demonstration executor. This is NOT an LLM or a quality benchmark."""

import csv
import json
import subprocess
import sys
from pathlib import Path

request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
workspace = Path(request["workspace"])
prompt = request["messages"][0]["content"]
artifacts = []
if request["case_id"] == "names":
    names = [x.strip() for x in prompt.split(":", 1)[1].split(",") if x.strip()]
    if request["skills"]:
        names = [x.upper() for x in names]
    output = json.dumps({"names": names})
elif request["case_id"] == "sales":
    with (workspace / "sales.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    result = {"count": len(rows), "total": sum(int(r["amount"]) for r in rows)}
    (workspace / "summary.json").write_text(json.dumps(result), encoding="utf-8")
    artifacts = ["summary.json"]
    output = "Wrote summary.json"
elif request["case_id"] == "sum":
    script = Path(request["skills"][0]) / "scripts/sum_numbers.py" if request["skills"] else None
    output = subprocess.check_output([sys.executable, str(script), "2", "4", "6"], text=True).strip() if script else "0"
else:
    raise SystemExit("Unknown demonstration case")
Path(sys.argv[2]).write_text(json.dumps({"protocol_version": "1", "status": "completed",
                                        "final_output": output, "artifacts": artifacts,
                                        "usage": None}), encoding="utf-8")
