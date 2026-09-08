"""Command line entry point; JSON output remains machine-readable."""

import argparse
import json
import os
import platform
import shutil
import signal
import sys
import tempfile
from pathlib import Path

from . import __version__
from .common import AssessmentError, read_json, write_json
from .contracts import NAMES, schema
from .config import load_suite
from .process import run_process
from .reporting import render
from .runner import run_suite
from .validation import check_skill, has_errors


def print_result(value):
    print(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))


def doctor(agent="claude", require=False):
    info = {"schema_version": "1", "tool_version": __version__,
            "python": platform.python_version(), "python_executable": sys.executable,
            "platform": platform.platform(), "architecture": platform.machine(),
            "node": shutil.which("node"), "agent": {"command": agent, "available": False}}
    if shutil.which(agent):
        try:
            with tempfile.TemporaryDirectory(prefix="skill-assessment-doctor-") as temp:
                proc = run_process([agent, "--version"], temp, Path(temp) / "logs", 15)
                info["agent"].update(available=proc["returncode"] == 0 and proc["status"] == "completed",
                                     version=proc["stdout"].strip()[:500], status=proc["status"])
        except AssessmentError as exc:
            info["agent"]["error"] = str(exc)
    info["note"] = "Model service and authentication are managed by your Agent. No model request was sent."
    return info, 2 if require and not info["agent"]["available"] else 0


def install_skill(destination=None, force=False):
    source = Path(__file__).parent / "resources" / "skills" / "skill-assessment"
    parent = Path(destination).expanduser().resolve() if destination else Path.home() / ".claude" / "skills"
    target = parent / "skill-assessment"
    if not source.is_dir():
        raise AssessmentError("Companion Skill resources are missing from this installation")
    if target.is_symlink() or target.resolve() == source.resolve():
        raise AssessmentError("Refusing to overwrite a symlink or the packaged source Skill")
    if target.exists():
        if not force:
            raise AssessmentError(f"{target} already exists; use --force to replace this Skill")
        shutil.rmtree(target)
    shutil.copytree(source, target)
    return {"installed": str(target)}


def init_suite(target):
    root = Path(target).expanduser().resolve()
    if not (root / "SKILL.md").is_file():
        raise AssessmentError("init requires a Skill directory containing SKILL.md")
    evaluation = root / "evals"
    if evaluation.exists():
        raise AssessmentError("evals already exists; init never overwrites existing cases")
    (evaluation / "cases").mkdir(parents=True)
    (evaluation / "eval.yaml").write_text(
        'schema_version: "1"\nskill:\n  path: ".."\nengine:\n  type: claude_code\n'
        'cases:\n  files: [cases/basic.yaml]\nreport:\n  formats: [json, markdown, html]\n',
        encoding="utf-8")
    case = {"id": "basic", "title": "Starter case: adapt to a real Skill task before evaluation",
            "input": {"prompt": "Explain the task this Skill can perform and give one concrete example."},
            "judge": {"type": "agent", "criteria": [
                "The response accurately explains the supplied Skill and gives a concrete example."],
                      "threshold": 0.7}}
    (evaluation / "cases" / "basic.yaml").write_text(json.dumps(case, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"created": str(evaluation / "eval.yaml"),
            "note": "Starter example only. Author real task inputs and independent expected results before assessing quality."}


def build_parser():
    parser = argparse.ArgumentParser(prog="skill-assessment", description="Evaluate Skills with local evidence and optional Agent grading.")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("schema", help="Export an offline JSON Schema contract")
    export.add_argument("name", choices=NAMES)
    export.add_argument("--output")
    d = commands.add_parser("doctor", help="Inspect local runtime without a model call")
    d.add_argument("--agent", default="claude")
    d.add_argument("--require-agent", action="store_true")
    d.add_argument("--json", action="store_true")
    c = commands.add_parser("check", help="Check a Skill without executing it")
    c.add_argument("path")
    c.add_argument("--strict", action="store_true")
    c.add_argument("--json", action="store_true")
    for name in ("validate", "list-cases", "init"):
        p = commands.add_parser(name)
        p.add_argument("path")
        p.add_argument("--json", action="store_true")
    r = commands.add_parser("run", help="Execute a suite and persist evidence")
    r.add_argument("path")
    r.add_argument("--output", help="Parent directory for uniquely identified runs")
    r.add_argument("--include", action="append", help="Case ID glob; repeat this option for multiple patterns")
    r.add_argument("--repeat", type=int, default=1)
    r.add_argument("--benchmark", action="store_true")
    r.add_argument("--parent", help="Previous result.json for comparison/lineage")
    r.add_argument("--failed-only", action="store_true")
    r.add_argument("--change-note")
    r.add_argument("--strict", action="store_true")
    r.add_argument("--format", action="append", choices=["json", "markdown", "html", "junit"])
    r.add_argument("--json", action="store_true")
    p = commands.add_parser("report", help="Render an existing result without running Agents")
    p.add_argument("path")
    p.add_argument("--format", action="append", choices=["markdown", "html", "junit"])
    p.add_argument("--json", action="store_true")
    skill = commands.add_parser("skill")
    sk = skill.add_subparsers(dest="skill_command", required=True)
    install = sk.add_parser("install", help="Install the bundled Skill to an Agent skills parent directory")
    install.add_argument("--dest")
    install.add_argument("--force", action="store_true")
    install.add_argument("--json", action="store_true")
    return parser


def main(argv=None):
    def cancelled(signum, frame):
        raise KeyboardInterrupt

    if __import__("threading").current_thread() is __import__("threading").main_thread():
        signal.signal(signal.SIGTERM, cancelled)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    try:
        code = 0
        if args.command == "schema":
            value = schema(args.name)
            if args.output:
                path = Path(args.output).resolve()
                write_json(path, value)
                value = {"schema": args.name, "path": str(path)}
        elif args.command == "doctor":
            value, code = doctor(args.agent, args.require_agent)
        elif args.command == "check":
            value = check_skill(args.path, args.strict)
            code = 1 if has_errors(value) else 0
            if not args.json:
                for item in value["issues"]:
                    print(f"{item['severity'].upper()} {item['rule_id']} {item['file']}:{item['line'] or '-'} {item['message']}")
                print(f"Static checks: {'FAILED' if code else 'PASSED'} ({len(value['issues'])} issues)")
                return code
        elif args.command == "init":
            value = init_suite(args.path)
        elif args.command == "skill":
            value = install_skill(args.dest, args.force)
        elif args.command == "report":
            path = Path(args.path).resolve()
            result = read_json(path)
            formats = args.format or ["markdown", "html"]
            render(result, path.parent, formats)
            value = {"run_id": result["run_id"], "directory": str(path.parent), "formats": formats}
        else:
            suite = load_suite(args.path)
            if args.command == "validate":
                value = {"valid": True, "cases": len(suite.cases), "schema_version": "1"}
            elif args.command == "list-cases":
                value = [{"id": c["id"], "title": c.get("title", c["id"])} for c in suite.cases]
            else:
                if not 1 <= args.repeat <= 100:
                    raise AssessmentError("--repeat must be in 1..100")
                directory, result, code = run_suite(
                    suite, output=args.output, include=args.include, repeat=args.repeat,
                    benchmark=args.benchmark, parent=args.parent, failed_only=args.failed_only,
                    change_note=args.change_note, formats=args.format, strict=args.strict)
                value = {"run_id": result["run_id"], "status": result["status"],
                         "result": str(directory / "result.json"), "summary": result["summary"]}
        print_result(value)
        return code
    except KeyboardInterrupt:
        print_result({"error": "Cancelled", "exit_code": 130})
        return 130
    except (AssessmentError, OSError, ValueError, TypeError) as exc:
        if getattr(args, "json", False):
            print_result({"error": str(exc), "exit_code": 2})
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
