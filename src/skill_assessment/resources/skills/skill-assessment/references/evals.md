# Authoring evals

Use schema_version "1". All suite and case relative paths resolve from the
eval.yaml directory. Put each case in evals/cases/<case-id>.yaml.
The CLI init command creates an illustrative starter; replace that starter
with real task cases before claiming coverage.

An eval object contains skill.path (normally ".."), engine, cases.files and
optional defaults, judge, report and benchmark. cases.files is a list of case
YAML filenames relative to eval.yaml. report.formats accepts json, markdown,
html and junit. JSON evidence is always saved.

The engine is either:

- type: claude_code. Optional command is an array with the executable path
  only. model is optional; omitted means use the Agent's existing model.
  allowed_tools is an explicit array of tools the user wants to permit without
  interaction. Do not add blanket permission bypass flags.
- type: local. command is an argument array with {input_file} and {output_file}.
  {python}, {workspace}, and {config_dir} are supported placeholders.
  parameters is an optional object passed to the adapter.

engine.artifacts lists workspace-relative output files to collect for Claude
Code. Local adapters return their artifact paths in the response.
engine.isolation defaults to inherited. controlled requires a custom
adapter that actually controls Skill exposure, or Claude Code supporting
safe-mode. It affects automatic context discovery; it is not an OS sandbox.

Each case has:

- id: portable unique identifier using letters, digits, hyphens or underscores.
- input.prompt: one user request as text.
- Optional fixtures: a list of {source, destination}. source resolves from
  eval.yaml; destination is a portable workspace-relative path.
- Optional constraints: timeout_seconds and max_turns.
- judge: a grader, unless the suite provides a default judge.
- Optional engine override: a complete engine configuration.

Judge types:

- rule: assertions is a non-empty array. Types contains, not_contains and regex
  use value; json_equals uses pointer (RFC 6901) and value. File variants
  file_exists, file_contains and file_json_equals additionally use path.
- script: path points to a self-contained Python grader. It receives input
  and output JSON paths as two arguments. It must return boolean passed and
  a non-empty assertions array; each assertion has passed and evidence.
  Overall passed must equal the conjunction of assertion results. Optional
  python chooses an already installed interpreter for business dependencies.
- agent: criteria is a non-empty string array; optional threshold is 0..1,
  default 0.7. Optional engine overrides the execution engine for grading.
  This uses an independent Agent session and consumes additional model calls.

All graders support timeout_seconds. Use exact file/JSON checks where possible;
use Agent grading for behavior that needs semantic judgment. Do not let the
tested Agent see hidden expected answers, grading scripts or the authoring
conversation.

The format is this project's schema. It does not silently accept arbitrary
skill-up or Anthropic eval fields. Unknown configuration fields are rejected.
