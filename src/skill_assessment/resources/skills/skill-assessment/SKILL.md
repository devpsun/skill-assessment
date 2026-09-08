---
name: skill-assessment
description: Evaluate a local Agent Skill using the skill-assessment CLI, create task-based eval cases, and interpret structured quality reports. When the user explicitly requests improvement, use failure evidence to repair the Skill or its evals and rerun regression tests.
---

# Skill assessment

Use the installed skill-assessment CLI to evaluate the user's target Skill.
Match the user's language. The CLI owns execution, grading and saved evidence;
use the host Agent's file and command tools for case authoring and explanation.

## Locate and prepare

Identify the target directory containing SKILL.md. Read its instructions and
relevant resources to determine its claimed behavior and dependencies.
Run skill-assessment --version. If unavailable, explain that the tool must be
installed from the user's configured npm registry; do not fetch GitHub scripts
or install a separate Agent automatically.

Use skill-assessment check <skill-dir> --json for static checks. Explain errors
using rule IDs and file locations. Do not repair source files unless the user
has asked for changes.

If evals/eval.yaml is missing, read [the authoring reference](references/evals.md).
Create realistic task inputs, independent expected results and any necessary
fixtures. Include representative successful behavior and a meaningful edge
case. Avoid testing only whether the Skill can describe itself. Keep fixtures
separate from hidden answers and graders. Preserve existing useful cases.

Use the chosen execution Agent independently of the current host Agent.
Claude Code uses its existing service, model and authentication configuration.
A custom local Agent needs a command adapter implementing
[the execution protocol](references/protocol.md). Do not assume installing
this Skill also creates that adapter.

## Evaluate and report

Validate the suite before running it. Run skill-assessment run <skill-dir>
--json, keeping the returned result path. The run performs static checks again.
Read result.json and, for failures, the referenced per-trial output, grading
evidence and logs. Follow [the report reference](references/reports.md).

Report passed/failed counts, execution or grading errors, coverage and
limitations. A task pass does not prove natural Skill triggering or safety.
Treat deterministic example executors as tooling demonstrations, not model
benchmarks. Repeat trials or enable with/without comparison when relevant to
the user's request and budget; invalid comparisons must not be presented as gains.

When the user only requested evaluation, finish by explaining findings.
An evaluation request does not itself request edits to the target Skill.

## Improve only when requested

Use the selected report's evidence to distinguish Skill defects from incorrect
tests, grading failures and environment failures. Modify the relevant source
or eval files within the user's requested scope, explaining why each change
is justified. Do not weaken valid assertions to turn a failure into a pass.

Rerun affected failures with --parent <result.json> --failed-only and
--change-note <reason>; then rerun the full suite, referencing the preceding
run without --failed-only. New cases must also be exercised in the full run.
Changed grading standards are not directly comparable improvements.

Stop after the requested scope passes, or when blocked, out of the user's
budget, or no evidence-supported improvement remains. Preserve failed
evidence and explain unresolved issues. Do not start an unattended background
optimization loop or publish the target Skill as a side effect.
