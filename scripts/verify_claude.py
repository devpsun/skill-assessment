"""Opt-in real Agent acceptance. Uses existing Claude configuration, never requests secrets."""
import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from skill_assessment.cli import doctor
from skill_assessment.config import load_suite
from skill_assessment.runner import run_suite


def main():
    parser = argparse.ArgumentParser(description="Runs a real Claude task; uses your existing model service.")
    parser.add_argument("--agent", default="claude")
    parser.add_argument("--output", default="claude-acceptance")
    parser.add_argument("--controlled", action="store_true", help="Requires Claude --safe-mode")
    parser.add_argument("--agent-judge", action="store_true", help="Adds an independent model grading call")
    args = parser.parse_args()
    info, code = doctor(args.agent, require=True)
    if code:
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return code
    with tempfile.TemporaryDirectory(prefix="claude-验收 space-") as temp:
        root = Path(temp) / "protocol-smoke"
        (root / "evals").mkdir(parents=True)
        (root / "SKILL.md").write_text(
            "---\nname: protocol-smoke\ndescription: Respond to the protocol greeting task.\n---\n"
            "When asked for the protocol greeting, respond with exactly SKILL_ASSESSMENT_READY.\n", encoding="utf-8")
        engine = {"type": "claude_code", "command": [args.agent], "allowed_tools": ["Read"],
                  "isolation": "controlled" if args.controlled else "inherited"}
        case = {"id": "read-skill", "input": {"prompt": "Give the protocol greeting defined by the supplied Skill."},
                "judge": {"type": "rule", "assertions": [{"type": "regex", "value": "^SKILL_ASSESSMENT_READY\\s*$"}]}}
        if args.agent_judge:
            case["judge"] = {"type": "agent", "criteria": [
                "The response consists only of SKILL_ASSESSMENT_READY, allowing surrounding whitespace."], "threshold": 1}
        config = {"schema_version": "1", "skill": {"path": ".."}, "engine": engine,
                  "cases": {"files": ["case.yaml"]}, "report": {"formats": ["json", "markdown", "html", "junit"]}}
        for name, value in (("eval.yaml", config), ("case.yaml", case)):
            (root / "evals" / name).write_text(json.dumps(value), encoding="utf-8")
        directory, result, code = run_suite(load_suite(root), output=args.output)
        print(json.dumps({"doctor": info, "result": str(directory / "result.json"), "status": result["status"]},
                         ensure_ascii=False, indent=2))
        return code


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
