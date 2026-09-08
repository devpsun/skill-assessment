"""Versioned, strict evaluation configuration."""

import re
from dataclasses import dataclass
from pathlib import Path

from . import yamlio
from .common import AssessmentError, object_keys, positive, relative_path, strings


@dataclass
class Suite:
    path: Path
    skill: Path
    data: dict
    cases: list


def engine_config(value, label="engine"):
    object_keys(value, {"type", "command", "model", "allowed_tools", "parameters",
                        "artifacts", "isolation"}, {"type"}, label)
    if value["type"] not in ("claude_code", "local"):
        raise AssessmentError(f"{label}.type: supported engines are claude_code and local")
    if value["type"] == "local":
        strings(value.get("command"), f"{label}.command", True)
        joined = " ".join(value["command"])
        if "{input_file}" not in joined or "{output_file}" not in joined:
            raise AssessmentError("Local command must include {input_file} and {output_file}")
        if any(k in value for k in ("model", "allowed_tools")):
            raise AssessmentError("Local engine uses parameters, not model/allowed_tools fields")
    elif "command" in value:
        strings(value["command"], f"{label}.command", True)
        if len(value["command"]) != 1:
            raise AssessmentError("Claude command must contain only its executable path")
    if value["type"] == "claude_code" and "parameters" in value:
        raise AssessmentError("Claude engine does not support local adapter parameters")
    if "model" in value and not isinstance(value["model"], str):
        raise AssessmentError("engine.model must be a string")
    if "allowed_tools" in value:
        strings(value["allowed_tools"], f"{label}.allowed_tools")
    if "parameters" in value and not isinstance(value["parameters"], dict):
        raise AssessmentError("engine.parameters must be an object")
    if value.get("isolation", "inherited") not in ("inherited", "controlled"):
        raise AssessmentError("engine.isolation must be inherited or controlled")
    for p in strings(value.get("artifacts", []), "engine.artifacts"):
        relative_path(p)
    return value


def assertion_config(value):
    kind = value.get("type") if isinstance(value, dict) else None
    specs = {
        "contains": ({"value"}, {"value"}),
        "not_contains": ({"value"}, {"value"}),
        "regex": ({"value"}, {"value"}),
        "json_equals": ({"pointer", "value"}, {"pointer", "value"}),
        "file_exists": ({"path"}, {"path"}),
        "file_contains": ({"path", "value"}, {"path", "value"}),
        "file_json_equals": ({"path", "pointer", "value"}, {"path", "pointer", "value"}),
    }
    if kind not in specs:
        raise AssessmentError(f"Unsupported assertion type: {kind}")
    allowed, required = specs[kind]
    object_keys(value, allowed | {"type", "id", "description"}, required | {"type"}, "assertion")
    if "path" in value:
        relative_path(value["path"])
    if "pointer" in value:
        ptr = value["pointer"]
        if not isinstance(ptr, str) or (ptr and not ptr.startswith("/")):
            raise AssessmentError("JSON pointer must be empty or start with /")
    if kind in ("contains", "not_contains", "regex", "file_contains"):
        if not isinstance(value["value"], str) or not value["value"]:
            raise AssessmentError(f"{kind}.value must be a non-empty string")
    if kind == "regex":
        try:
            re.compile(value["value"])
        except re.error as exc:
            raise AssessmentError(f"Invalid regex: {exc}") from exc
    for key in ("id", "description"):
        if key in value and not isinstance(value[key], str):
            raise AssessmentError(f"assertion.{key} must be a string")


def judge_config(value, base):
    object_keys(value, {"type", "assertions", "path", "python", "criteria", "threshold",
                        "engine", "timeout_seconds"}, {"type"}, "judge")
    kind = value["type"]
    permitted = {
        "rule": {"type", "assertions", "timeout_seconds"},
        "script": {"type", "path", "python", "timeout_seconds"},
        "agent": {"type", "criteria", "threshold", "engine", "timeout_seconds"},
    }
    if kind not in permitted:
        raise AssessmentError(f"Unsupported judge: {kind}")
    object_keys(value, permitted[kind], {"type"}, "judge")
    if kind == "rule":
        a = value.get("assertions")
        if not isinstance(a, list) or not a:
            raise AssessmentError("Rule judge needs at least one assertion")
        for item in a:
            assertion_config(item)
    elif kind == "script":
        if not isinstance(value.get("path"), str) or not (base / value["path"]).is_file():
            raise AssessmentError("judge.path must reference an existing Python script")
        if "python" in value and not isinstance(value["python"], str):
            raise AssessmentError("judge.python must be an executable path")
    else:
        strings(value.get("criteria"), "judge.criteria", True)
        if "engine" in value:
            engine_config(value["engine"], "judge.engine")
        t = value.get("threshold", 0.7)
        if isinstance(t, bool) or not isinstance(t, (float, int)) or not 0 <= t <= 1:
            raise AssessmentError("judge.threshold must be between 0 and 1")
    positive(value.get("timeout_seconds", 120), "judge.timeout_seconds")
    return value


def load_suite(target):
    path = Path(target).expanduser().resolve()
    if path.is_dir():
        path = path / "evals" / "eval.yaml"
    if not path.is_file():
        raise AssessmentError(f"Missing {path}. Create evals with the companion Skill or init.")
    base = path.parent
    data = yamlio.load(path)
    object_keys(data, {"schema_version", "skill", "engine", "cases", "defaults",
                       "judge", "report", "benchmark"}, {"schema_version", "skill", "engine", "cases"}, "eval")
    if data["schema_version"] != "1":
        raise AssessmentError('Unsupported schema_version; expected string "1"')
    object_keys(data["skill"], {"path", "exclude"}, {"path"}, "skill")
    if not isinstance(data["skill"]["path"], str):
        raise AssessmentError("skill.path must be a string")
    skill = (base / data["skill"]["path"]).resolve()
    if not skill.is_dir():
        raise AssessmentError(f"Skill directory does not exist: {skill}")
    strings(data["skill"].get("exclude", []), "skill.exclude")
    engine_config(data["engine"])
    defaults = data.get("defaults", {})
    object_keys(defaults, {"timeout_seconds", "max_turns"}, label="defaults")
    positive(defaults.get("timeout_seconds", 120), "defaults.timeout_seconds")
    max_turns = defaults.get("max_turns", 10)
    if type(max_turns) is not int or not 1 <= max_turns <= 1000:
        raise AssessmentError("max_turns must be an integer in 1..1000")
    if "judge" in data:
        judge_config(data["judge"], base)
    report = data.get("report", {})
    object_keys(report, {"formats"}, label="report")
    formats = strings(report.get("formats", ["json", "markdown", "html"]), "report.formats", True)
    if set(formats) - {"json", "markdown", "html", "junit"}:
        raise AssessmentError("Unknown report format")
    benchmark = data.get("benchmark", {})
    object_keys(benchmark, {"enabled"}, label="benchmark")
    if "enabled" in benchmark and type(benchmark["enabled"]) is not bool:
        raise AssessmentError("benchmark.enabled must be a boolean")
    object_keys(data["cases"], {"files"}, {"files"}, "cases")
    cases, ids = [], set()
    for filename in strings(data["cases"]["files"], "cases.files", True):
        case_path = (base / filename).resolve()
        case = yamlio.load(case_path)
        object_keys(case, {"id", "title", "description", "input", "fixtures", "constraints",
                          "judge", "engine"}, {"id", "input"}, filename)
        cid = case["id"]
        if not isinstance(cid, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}", cid):
            raise AssessmentError(f"Invalid case id: {cid}")
        if cid in ids:
            raise AssessmentError(f"Duplicate case id: {cid}")
        ids.add(cid)
        object_keys(case["input"], {"prompt"}, {"prompt"}, f"{cid}.input")
        if not isinstance(case["input"]["prompt"], str) or not case["input"]["prompt"].strip():
            raise AssessmentError(f"{cid}: input.prompt must be non-empty text")
        for key in ("title", "description"):
            if key in case and not isinstance(case[key], str):
                raise AssessmentError(f"{cid}.{key} must be a string")
        fixtures = case.get("fixtures", [])
        if not isinstance(fixtures, list):
            raise AssessmentError("fixtures must be an array")
        destinations = set()
        for fixture in fixtures:
            object_keys(fixture, {"source", "destination"}, {"source", "destination"}, "fixture")
            relative_path(fixture["destination"])
            if fixture["destination"].split("/")[0].startswith("."):
                raise AssessmentError("Fixture cannot write hidden Agent configuration directories")
            normalized = fixture["destination"].casefold()
            if any(normalized == d or normalized.startswith(d + "/") or d.startswith(normalized + "/")
                   for d in destinations):
                raise AssessmentError("Duplicate fixture destination")
            destinations.add(normalized)
            if not isinstance(fixture["source"], str) or not (base / fixture["source"]).is_file():
                raise AssessmentError(f"Missing fixture: {fixture['source']}")
        constraints = case.get("constraints", {})
        object_keys(constraints, {"timeout_seconds", "max_turns"}, label="constraints")
        positive(constraints.get("timeout_seconds", defaults.get("timeout_seconds", 120)), "timeout_seconds")
        turns = constraints.get("max_turns", max_turns)
        if type(turns) is not int or not 1 <= turns <= 1000:
            raise AssessmentError("max_turns must be an integer in 1..1000")
        judge = case.get("judge", data.get("judge"))
        judge_config(judge, base)
        if "engine" in case:
            engine_config(case["engine"])
        case["_path"] = str(case_path)
        cases.append(case)
    return Suite(path, skill, data, cases)
