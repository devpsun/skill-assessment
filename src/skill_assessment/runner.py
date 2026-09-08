"""Evaluation lifecycle and immutable per-run evidence."""

import copy
import datetime as dt
import fnmatch
import platform
import shutil
import time
import uuid
from pathlib import Path

from . import __version__
from .common import AssessmentError, canonical, contained, digest, file_hash, read_json, write_json
from .engines import execute
from .judges import grade
from .process import check_cancelled
from .reporting import benchmark_summary, exit_code, render, summarize
from .validation import check_skill, has_errors
from .workspace import archive_artifacts, copy_skill


def run_suite(suite, output=None, include=None, repeat=1, benchmark=False,
              parent=None, failed_only=False, change_note=None, formats=None, strict=False):
    parent_result = read_json(parent) if parent else None
    if parent_result and parent_result.get("schema_version") != "1":
        raise AssessmentError("Unsupported parent result schema")
    failed_ids = ({t["case_id"] for t in parent_result["trials"] if t["status"] != "passed"}
                  if parent_result and failed_only else None)
    if failed_only and not parent_result:
        raise AssessmentError("--failed-only requires --parent result.json")
    cases = [copy.deepcopy(c) for c in suite.cases
             if (not include or any(fnmatch.fnmatchcase(c["id"], p) for p in include))
             and (failed_ids is None or c["id"] in failed_ids)]
    if not cases:
        raise AssessmentError("No cases selected")
    variants = ["with_skill", "without_skill"] if benchmark or suite.data.get("benchmark", {}).get("enabled") else ["with_skill"]
    now = dt.datetime.now(dt.timezone.utc)
    run_id = now.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    root = Path(output).expanduser().resolve() if output else suite.skill.parent / ".skill-assessment-runs"
    directory = root / run_id
    directory.mkdir(parents=True, exist_ok=False)
    result = {"schema_version": "1", "tool_version": __version__, "run_id": run_id,
              "created_at": now.isoformat(), "status": "running", "trials": [],
              "parent_run_id": parent_result["run_id"] if parent_result else None,
              "change_note": change_note,
              "limitations": ["Local workspaces are not OS sandboxes.",
                              "Remote model behavior may change; snapshots do not guarantee identical outputs.",
                              "Skill activation/trigger accuracy is not inferred from a passing task."]}
    result["static"] = check_skill(suite.skill, strict)
    for case in cases:
        for variant in variants:
            for repetition in range(1, repeat + 1):
                trial_id = f"{case['id']}--{variant}--{repetition}"
                result["trials"].append({"trial_id": trial_id, "case_id": case["id"],
                                         "variant": variant, "repeat": repetition, "status": "skipped"})
    event_file = directory / "events.jsonl"
    sequence = 0

    def event(name, **values):
        nonlocal sequence
        sequence += 1
        with event_file.open("a", encoding="utf-8") as f:
            f.write(canonical({"event": name, "time": dt.datetime.now(dt.timezone.utc).isoformat(),
                               "run_id": run_id, "sequence": sequence, **values}) + "\n")

    def save():
        result["summary"] = summarize(result["trials"])
        write_json(directory / "result.json", result)

    event("run_started")
    save()
    started = time.monotonic()
    active = None
    try:
        if has_errors(result["static"]):
            result["blocked"] = "static_validation"
            for trial in result["trials"]:
                trial["error"] = "Static validation blocked dynamic execution"
        else:
            snapshots = directory / "snapshots"
            hidden = [suite.path, root, *[Path(c["_path"]) for c in suite.cases]]
            for c in suite.cases:
                j = c.get("judge", suite.data.get("judge"))
                if j["type"] == "script":
                    hidden.append(suite.path.parent / j["path"])
            skill_hashes = copy_skill(suite.skill, snapshots / "skill" / suite.skill.name,
                                      suite.data["skill"].get("exclude", []), hidden)
            write_json(snapshots / "eval.json", suite.data)
            manifest = {"schema_version": "1", "tool_version": __version__, "run_id": run_id,
                        "python": platform.python_version(), "platform": platform.platform(),
                        "skill_files": skill_hashes, "skill_digest": digest(skill_hashes), "cases": {}}
            for case in cases:
                cid = case["id"]
                case_snap = snapshots / "cases" / cid
                write_json(case_snap / "case.json", {k: v for k, v in case.items() if not k.startswith("_")})
                fixture_hashes = {}
                fixture_bytes = 0
                for index, fixture in enumerate(case.get("fixtures", [])):
                    source = suite.path.parent / fixture["source"]
                    fixture_bytes += source.stat().st_size
                    if fixture_bytes > 32 * 1024 * 1024 or index >= 100:
                        raise AssessmentError("Case fixtures exceed 32 MiB or 100 files")
                    dest = case_snap / f"fixture-{index}"
                    shutil.copyfile(source, dest)
                    fixture_hashes[fixture["destination"]] = file_hash(dest)
                    fixture["_snapshot"] = str(dest)
                judge = copy.deepcopy(case.get("judge", suite.data.get("judge")))
                script_hash = None
                if judge["type"] == "script":
                    dest = case_snap / "judge.py"
                    shutil.copyfile(suite.path.parent / judge["path"], dest)
                    script_hash = file_hash(dest)
                    judge["path"] = str(dest.resolve())
                effective_engine = case.get("engine", suite.data["engine"])
                fingerprint = digest({"input": case["input"], "fixtures": fixture_hashes,
                                      "judge": case.get("judge", suite.data.get("judge")),
                                      "script_hash": script_hash, "engine": effective_engine,
                                      "defaults": suite.data.get("defaults", {}),
                                      "constraints": case.get("constraints", {})})
                manifest["cases"][cid] = {"fingerprint": fingerprint, "fixtures": fixture_hashes}
                case["_judge"] = judge
            write_json(directory / "manifest.json", manifest)
            result["skill_digest"] = manifest["skill_digest"]
            for trial in result["trials"]:
                check_cancelled()
                active = trial
                case = next(c for c in cases if c["id"] == trial["case_id"])
                trial["fingerprint"] = manifest["cases"][case["id"]]["fingerprint"]
                trial_dir = directory / "trials" / trial["trial_id"]
                workspace = trial_dir / "workspace"
                workspace.mkdir(parents=True)
                engine = case.get("engine", suite.data["engine"])
                skills = []
                if trial["variant"] == "with_skill":
                    skill_dest = workspace / ".claude" / "skills" / suite.skill.name
                    shutil.copytree(snapshots / "skill" / suite.skill.name, skill_dest)
                    skills.append(str(skill_dest.resolve()))
                for fixture in case.get("fixtures", []):
                    dest = contained(workspace, fixture["destination"])
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(fixture["_snapshot"], dest)
                limits = {"timeout_seconds": 120, "max_turns": 10,
                          **suite.data.get("defaults", {}), **case.get("constraints", {})}
                request = {"protocol_version": "1", "run_id": run_id, "trial_id": trial["trial_id"],
                           "case_id": case["id"], "workspace": str(workspace.resolve()), "skills": skills,
                           "messages": [{"role": "user", "content": case["input"]["prompt"]}],
                           "parameters": engine.get("parameters", {}), "limits": limits}
                event("trial_started", trial_id=trial["trial_id"])
                trial["engine_type"] = engine["type"]
                try:
                    response = execute(engine, request, trial_dir / "execution", suite.path.parent)
                    trial["execution"] = {k: response.get(k) for k in
                                          ("duration_seconds", "usage", "model", "session_id", "isolation")}
                    artifacts = trial_dir / "artifacts"
                    artifacts.mkdir()
                    trial["artifacts"] = archive_artifacts(workspace, artifacts, response.get("artifacts", []))
                    trial["status"] = "judge_error"
                    trial["grading"] = grade(case["_judge"], response, artifacts.resolve(),
                                             trial_dir / "grading", suite.path.parent, engine, case["id"],
                                             case["input"], run_id, trial["trial_id"])
                    trial["status"] = "passed" if trial["grading"]["passed"] else "failed"
                except (AssessmentError, OSError, ValueError, TypeError) as exc:
                    if trial["status"] != "judge_error":
                        trial["status"] = "execution_error"
                    trial["error"] = str(exc)
                event("trial_finished", trial_id=trial["trial_id"], status=trial["status"])
                save()
                active = None
    except KeyboardInterrupt:
        result["cancelled"] = True
        if active:
            active["status"] = "cancelled"
            active["error"] = "User cancelled execution"
    except (AssessmentError, OSError, ValueError, TypeError) as exc:
        result["error"] = str(exc)
    result["duration_seconds"] = round(time.monotonic() - started, 6)
    result["benchmark"] = benchmark_summary(result["trials"])
    if parent_result:
        previous = {(t["case_id"], t["variant"], t["repeat"]): t for t in parent_result["trials"]}
        comparison = []
        for trial in result["trials"]:
            old = previous.get((trial["case_id"], trial["variant"], trial["repeat"]))
            comparable = bool(old and trial.get("fingerprint") and old.get("fingerprint") == trial["fingerprint"])
            comparison.append({"trial_id": trial["trial_id"], "comparable": comparable,
                               "before": old["status"] if old else None, "after": trial["status"],
                               "reason": None if comparable else "New case or changed inputs, judge, fixtures, or configuration"})
        result["comparison"] = comparison
    result["summary"] = summarize(result["trials"])
    code = exit_code(result)
    result["status"] = {0: "passed", 1: "failed", 2: "error", 130: "cancelled"}[code]
    event("run_finished", status=result["status"])
    save()
    render(result, directory, formats or suite.data.get("report", {}).get("formats", ["json", "markdown", "html"]))
    return directory, result, code
