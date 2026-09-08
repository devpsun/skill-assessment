# Custom local execution protocol v1

Configure an executable argument array, including {input_file} and
{output_file}. For a Python adapter, use {python} followed by its script path
and those file arguments. {config_dir} anchors paths at the eval.yaml folder.
Pass commands as arguments, not shell command strings.

The input JSON contains protocol_version "1", run_id, trial_id, case_id,
workspace, messages, skills, limits and parameters. messages contains the
test prompt without grading criteria; skills lists local Skill root paths
and is empty for the without-Skill variant. limits supplies timeout_seconds
and max_turns. Honor both, create a fresh session, and use the Agent's existing
model configuration.

Write output JSON to the requested output path:

    {
      "protocol_version": "1",
      "status": "completed",
      "final_output": "The task output",
      "artifacts": ["summary.json"],
      "usage": null
    }

completed indicates execution completion, not grading success. For an
execution failure, return a non-zero process exit code or a non-completed
status with error details. stdout and stderr are collected as logs.

Artifact paths must point to existing files within workspace, use forward
slashes and contain no traversal. The CLI archives only declared files.
The default artifact limits are 100 files and 32 MiB total.

usage and model/session metadata are optional; unavailable information stays
null. Never invent Token or cost values. Do not put credentials in the input,
response, logs or fixtures. Authentication remains local to the Agent.

Setting isolation: controlled is an adapter declaration that test cases do
not reuse conversations and the without-Skill variant cannot discover the
target Skill elsewhere. Report this declaration honestly; workspace paths
alone do not enforce filesystem access control.
