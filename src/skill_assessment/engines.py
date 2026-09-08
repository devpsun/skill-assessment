"""Agent adapters. Credentials stay with the installed Agent."""

import json
import uuid
from pathlib import Path

from .common import AssessmentError, read_json, write_json
from .process import run_process


def expand(command, values):
    result = []
    for arg in command:
        for key, value in values.items():
            arg = arg.replace("{" + key + "}", str(value))
        result.append(arg)
    return result


def validate_response(value):
    if not isinstance(value, dict) or value.get("protocol_version") != "1":
        raise AssessmentError('Agent response must contain protocol_version: "1"')
    if value.get("status") != "completed":
        raise AssessmentError(f"Agent reported failure: {value.get('error', value.get('status'))}")
    if not isinstance(value.get("final_output"), str):
        raise AssessmentError("Agent final_output must be text")
    paths = value.get("artifacts", [])
    if not isinstance(paths, list) or not all(isinstance(x, str) for x in paths):
        raise AssessmentError("Agent artifacts must be a string array")
    usage = value.get("usage")
    if usage is not None and not isinstance(usage, dict):
        raise AssessmentError("Agent usage must be an object or null")
    return value


def execute(engine, request, log_dir, config_dir):
    log_dir = Path(log_dir).resolve()
    log_dir.mkdir(parents=True, exist_ok=True)
    input_file, output_file = log_dir / "request.json", log_dir / "response.json"
    write_json(input_file, request)
    workspace = Path(request["workspace"])
    timeout = request["limits"]["timeout_seconds"]
    if engine["type"] == "local":
        values = {"input_file": input_file, "output_file": output_file,
                  "workspace": workspace, "config_dir": config_dir}
        command = expand(engine["command"], values)
        process = run_process(command, workspace, log_dir, timeout)
        if process["status"] != "completed" or process["returncode"] != 0:
            raise AssessmentError(f"Agent execution {process['status']}; exit={process['returncode']}")
        if not output_file.is_file():
            raise AssessmentError("Agent did not write the response file")
        response = validate_response(read_json(output_file))
        response["isolation"] = {
            "controlled": engine.get("isolation") == "controlled",
            "basis": "adapter declaration",
            "limitations": ["Local workspace is not an OS sandbox; declaration is not independently verified."]}
    else:
        command = engine.get("command", ["claude"])
        version = run_process([*command, "--version"], workspace, log_dir / "version", min(timeout, 15))
        agent_version = version["stdout"].strip()[:500] if version["returncode"] == 0 else None
        command = [*command, "-p", "--output-format", "json",
                   "--session-id", str(uuid.uuid4()),
                   "--max-turns", str(request["limits"].get("max_turns", 10))]
        if engine.get("model"):
            command.extend(["--model", engine["model"]])
        if engine.get("settings_file"):
            settings = (Path(config_dir) / engine["settings_file"]).resolve()
            if not settings.is_file():
                raise AssessmentError("Claude settings_file does not exist")
            command.extend(["--settings", str(settings)])
        if engine.get("allowed_tools"):
            command.extend(["--allowedTools", ",".join(engine["allowed_tools"])])
        # Inherited mode deliberately keeps the user's service/model configuration.
        # Safe mode is opt-in and unsupported older CLIs fail explicitly.
        controlled = engine.get("isolation") == "controlled"
        if controlled:
            command.append("--safe-mode")
        skill_text = ""
        if request["skills"]:
            locations = "\n".join(str(Path(p) / "SKILL.md") for p in request["skills"])
            skill_text = "Use the following Skill instructions for this task. Read the file and its relevant resources:\n" + locations + "\n\n"
        prompt = skill_text + "\n".join(m["content"] for m in request["messages"])
        process = run_process(command, workspace, log_dir, timeout, prompt)
        if process["status"] != "completed" or process["returncode"] != 0:
            if "cannot be launched inside another" in process["stderr"]:
                raise AssessmentError("Claude refused nested launch. Run this CLI in an independent terminal "
                                      "using the same configured Agent; the tool preserves Claude's session guard.")
            raise AssessmentError(f"Claude execution {process['status']}; exit={process['returncode']}. See stderr.txt.")
        try:
            raw = json.loads(process["stdout"])
        except ValueError as exc:
            raise AssessmentError("Claude did not return JSON; see stdout.txt") from exc
        write_json(log_dir / "claude-result.json", raw)
        if not isinstance(raw, dict) or raw.get("is_error") or not isinstance(raw.get("result"), str):
            raise AssessmentError("Claude returned an error or missing result")
        if raw.get("permission_denials"):
            raise AssessmentError("Claude reported permission denials; configure the required tools in your Agent or eval")
        response = {"protocol_version": "1", "status": "completed", "final_output": raw["result"],
                    "artifacts": engine.get("artifacts", []), "usage": raw.get("usage"),
                    "session_id": raw.get("session_id"), "model": raw.get("model"),
                    "agent_version": agent_version, "cost_usd": raw.get("total_cost_usd"),
                    "model_usage": raw.get("modelUsage"),
                    "isolation": {"controlled": controlled,
                                  "basis": "Claude safe-mode" if controlled else "inherited configuration",
                                  "limitations": ["Functional explicit Skill invocation; natural trigger behavior is not measured.",
                                                  "Workspace is not an OS sandbox."]}}
        write_json(output_file, response)
    response["duration_seconds"] = process["duration_seconds"]
    return response
