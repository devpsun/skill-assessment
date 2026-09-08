"""Offline JSON Schema contracts; runtime also checks paths and semantic invariants."""
import copy


def obj(properties, required=(), extra=False):
    return {"type": "object", "properties": properties, "required": list(required), "additionalProperties": extra}


def array(items, minimum=0):
    return {"type": "array", "items": items, "minItems": minimum}


def ref(name):
    return {"$ref": "#/$defs/" + name}


S = {"type": "string"}
TEXT = {"type": "string", "minLength": 1}
V = {"const": "1"}
NUMBER = {"type": "number", "exclusiveMinimum": 0, "maximum": 86400}
NULLABLE = {"type": ["string", "null"]}
FORMATS = array({"enum": ["json", "markdown", "html", "junit"]}, 1)
DEFS = {
    "limits": obj({"timeout_seconds": NUMBER, "max_turns": {"type": "integer", "minimum": 1, "maximum": 1000}}),
    "input": obj({"prompt": TEXT}, ["prompt"]),
    "fixture": obj({"source": TEXT, "destination": TEXT}, ["source", "destination"]),
}
shared_engine = {"type": S, "command": array(TEXT, 1), "artifacts": array(TEXT),
                 "isolation": {"enum": ["inherited", "controlled"]}}
DEFS["engine"] = {"oneOf": [
    obj({**shared_engine, "type": {"const": "claude_code"}, "command": {**array(TEXT, 1), "maxItems": 1},
         "model": S, "allowed_tools": array(TEXT), "settings_file": TEXT}, ["type"]),
    obj({**shared_engine, "type": {"const": "local"}, "parameters": {"type": "object"}},
        ["type", "command"])
]}
assertions = []
for kind, fields in {
    "contains": {"value": TEXT}, "not_contains": {"value": TEXT}, "regex": {"value": TEXT},
    "json_equals": {"pointer": S, "value": {}}, "file_exists": {"path": TEXT},
    "file_contains": {"path": TEXT, "value": TEXT},
    "file_json_equals": {"path": TEXT, "pointer": S, "value": {}},
}.items():
    assertions.append(obj({"type": {"const": kind}, "id": S, "description": S, **fields}, ["type", *fields]))
DEFS["assertion"] = {"oneOf": assertions}
DEFS["judge"] = {"oneOf": [
    obj({"type": {"const": "rule"}, "assertions": array(ref("assertion"), 1), "timeout_seconds": NUMBER},
        ["type", "assertions"]),
    obj({"type": {"const": "script"}, "path": TEXT, "python": S, "timeout_seconds": NUMBER}, ["type", "path"]),
    obj({"type": {"const": "agent"}, "criteria": array(TEXT, 1),
         "threshold": {"type": "number", "minimum": 0, "maximum": 1},
         "engine": ref("engine"), "timeout_seconds": NUMBER}, ["type", "criteria"])
]}
DEFS["case"] = obj({
    "id": {"type": "string", "pattern": "^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$"},
    "title": S, "description": S, "input": ref("input"), "fixtures": array(ref("fixture")),
    "constraints": ref("limits"), "judge": ref("judge"), "engine": ref("engine")
}, ["id", "input"])
DEFS["eval"] = obj({
    "schema_version": V, "skill": obj({"path": S, "exclude": array(TEXT)}, ["path"]),
    "engine": ref("engine"), "cases": obj({"files": array(TEXT, 1)}, ["files"]),
    "defaults": ref("limits"), "judge": ref("judge"), "report": obj({"formats": FORMATS}),
    "benchmark": obj({"enabled": {"type": "boolean"}})
}, ["schema_version", "skill", "engine", "cases"])
DEFS["request"] = obj({
    "protocol_version": V, "run_id": TEXT, "trial_id": TEXT, "case_id": TEXT, "workspace": TEXT,
    "messages": array(obj({"role": {"const": "user"}, "content": TEXT}, ["role", "content"]), 1),
    "skills": array(TEXT), "parameters": {"type": "object"}, "limits": ref("limits")
}, ["protocol_version", "run_id", "trial_id", "case_id", "workspace", "messages", "skills", "parameters", "limits"])
DEFS["response"] = obj({
    "protocol_version": V, "status": {"const": "completed"}, "final_output": S,
    "artifacts": array(TEXT), "usage": {"type": ["object", "null"]}, "model": NULLABLE,
    "session_id": NULLABLE, "agent_version": NULLABLE, "cost_usd": {"type": ["number", "null"], "minimum": 0}
}, ["protocol_version", "status", "final_output"], extra=True)
DEFS["grading"] = obj({
    "passed": {"type": "boolean"},
    "assertions": array(obj({"id": S, "description": {}, "passed": {"type": "boolean"}, "evidence": {}},
                            ["passed", "evidence"], extra=True), 1),
    "score": {"type": "number", "minimum": 0, "maximum": 1}
}, ["passed", "assertions"], extra=True)
statuses = ["passed", "failed", "execution_error", "judge_error", "skipped", "cancelled"]
DEFS["summary"] = obj({
    "planned": {"type": "integer", "minimum": 0}, "executed": {"type": "integer", "minimum": 0},
    "counts": obj({s: {"type": "integer", "minimum": 0} for s in statuses}, statuses),
    "pass_rate": {"type": ["number", "null"], "minimum": 0, "maximum": 1},
    "scoring_coverage": {"type": ["number", "null"], "minimum": 0, "maximum": 1},
}, ["planned", "executed", "counts", "pass_rate", "scoring_coverage"])
DEFS["trial"] = obj({
    "trial_id": TEXT, "case_id": TEXT, "repeat": {"type": "integer", "minimum": 1},
    "variant": {"enum": ["with_skill", "without_skill"]}, "status": {"enum": statuses},
    "grading": ref("grading"), "error": S, "fingerprint": S,
    "execution": {"type": "object"}, "output_excerpt": S,
    "evidence": {"type": "object", "additionalProperties": TEXT},
    "artifacts": array(obj({"path": TEXT, "sha256": TEXT, "size_bytes": {"type": "integer", "minimum": 0}},
                           ["path", "sha256", "size_bytes"]))
}, ["trial_id", "case_id", "repeat", "variant", "status"], extra=True)
DEFS["result"] = obj({
    "schema_version": V, "tool_version": TEXT, "run_id": TEXT, "created_at": TEXT,
    "status": {"enum": ["running", "passed", "failed", "error", "cancelled"]},
    "trials": array(ref("trial")), "summary": ref("summary"), "quality": ref("summary"),
    "parent_run_id": NULLABLE, "change_note": NULLABLE, "static": {"type": "object"},
    "limitations": array(S)
}, ["schema_version", "tool_version", "run_id", "created_at", "status", "trials", "summary"], extra=True)
DEFS["manifest"] = obj({
    "schema_version": V, "tool_version": TEXT, "run_id": TEXT, "python": TEXT, "platform": TEXT,
    "skill_files": {"type": "object", "additionalProperties": TEXT},
    "skill_digest": TEXT, "cases": {"type": "object"}
}, ["schema_version", "tool_version", "run_id", "python", "platform", "skill_files", "skill_digest", "cases"])

NAMES = ("eval", "case", "request", "response", "grading", "result", "manifest")


def schema(name):
    if name not in NAMES:
        raise ValueError("Unknown contract: " + name)
    return {"$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": f"skill-assessment {name} v1", **ref(name), "$defs": copy.deepcopy(DEFS)}
