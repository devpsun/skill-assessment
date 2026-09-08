"""Portable, escaped reports rendered entirely from saved JSON."""

import html
import json
from collections import Counter
from pathlib import Path
from urllib.parse import quote
from xml.etree import ElementTree as ET

from .common import AssessmentError

STATUSES = ("passed", "failed", "execution_error", "judge_error", "skipped", "cancelled")


def summarize(trials):
    counts = Counter(t["status"] for t in trials)
    scored = counts["passed"] + counts["failed"]
    return {"planned": len(trials), "executed": sum(counts[s] for s in STATUSES[:4]),
            "counts": {s: counts[s] for s in STATUSES},
            "pass_rate": counts["passed"] / scored if scored else None,
            "scoring_coverage": scored / len(trials) if trials else None}


def exit_code(result):
    counts = result["summary"]["counts"]
    if result.get("cancelled") or counts["cancelled"]:
        return 130
    if result.get("error") or counts["execution_error"] or counts["judge_error"]:
        return 2
    # Baseline task failures are expected measurements; only the target gates quality.
    target_failed = any(t["variant"] == "with_skill" and t["status"] == "failed" for t in result["trials"])
    if result.get("blocked") or target_failed or counts["skipped"]:
        return 1
    return 0


def benchmark_summary(trials):
    groups = {}
    for trial in trials:
        groups.setdefault(trial["variant"], []).append(trial)
    if "without_skill" not in groups:
        return None
    valid = all(t.get("execution", {}).get("isolation", {}).get("controlled", False)
                for t in trials) and all(t["status"] in ("passed", "failed") for t in trials)
    summaries = {key: summarize(group) for key, group in groups.items()}
    return {"valid": valid, "basis": "configured execution isolation; see per-trial limitations",
            "reason": None if valid else "Uncontrolled isolation or incomplete scores; no causal delta reported.",
            "variants": summaries,
            "pass_rate_delta": (summaries["with_skill"]["pass_rate"] - summaries["without_skill"]["pass_rate"])
            if valid else None}


def render(result, directory, formats):
    if result.get("schema_version") != "1" or not isinstance(result.get("trials"), list):
        raise AssessmentError("Unsupported or invalid result.json")
    directory = Path(directory)
    summary = result["summary"]
    lines = [f"# Skill assessment — {result['run_id']}", "",
             f"Status: {result['status']}", "",
             f"Planned: {summary['planned']} · Executed: {summary['executed']} · "
             f"Pass rate: {summary['pass_rate']} · Scoring coverage: {summary['scoring_coverage']}", "",
             "## Static checks", ""]
    issues = result.get("static", {}).get("issues", [])
    lines.extend(f"- {i['severity']} {i['rule_id']}: {i['message']}" for i in issues)
    if not issues:
        lines.append("No static issues recorded.")
    lines.extend(["", "## Trials", ""])
    for t in result["trials"]:
        lines.extend([f"### {t['case_id']} / {t['variant']} / repeat {t['repeat']}", "",
                      f"Status: {t['status']}", ""])
        if t.get("error"):
            lines.extend([f"Error: {t['error']}", ""])
        for a in t.get("grading", {}).get("assertions", []):
            lines.append(f"- {'PASS' if a['passed'] else 'FAIL'} {a.get('id', '')}: "
                         f"{json.dumps(a.get('evidence'), ensure_ascii=False)}")
        for artifact in t.get("artifacts", []):
            target = f"trials/{t['trial_id']}/artifacts/{artifact['path']}"
            lines.append(f"- Artifact: [{artifact['path']}]({quote(target, safe='/')})")
        lines.append("")
    if result.get("benchmark"):
        lines.extend(["## Benchmark", "", json.dumps(result["benchmark"], ensure_ascii=False, indent=2), ""])
    if result.get("comparison"):
        lines.extend(["## Previous run", "", json.dumps(result["comparison"], ensure_ascii=False, indent=2), ""])
    lines.extend(["## Limitations", "", *[f"- {x}" for x in result.get("limitations", [])], ""])
    markdown = "\n".join(lines)
    if "markdown" in formats:
        (directory / "report.md").write_text(markdown, encoding="utf-8")
    if "html" in formats:
        blocks = []
        for t in result["trials"]:
            data = html.escape(json.dumps(t, ensure_ascii=False, indent=2))
            links = []
            for a in t.get("artifacts", []):
                target = quote(f"trials/{t['trial_id']}/artifacts/{a['path']}", safe="/")
                links.append(f'<a href="{html.escape(target, quote=True)}">{html.escape(a["path"])}</a>')
            blocks.append(f'<details><summary>{html.escape(t["case_id"])} · {html.escape(t["variant"])} · '
                          f'{html.escape(t["status"])}</summary><p>{" · ".join(links)}</p><pre>{data}</pre></details>')
        page = ('<!doctype html><html lang="en"><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1">'
                '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">'
                '<title>Skill assessment</title><style>'
                'body{font:16px system-ui;background:#f6f8fc;color:#182338;max-width:1100px;margin:40px auto;padding:0 24px}'
                'h1{letter-spacing:-1px}details{background:white;border:1px solid #dce2ec;border-radius:10px;margin:12px 0;padding:18px}'
                'summary{cursor:pointer;font-weight:600}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px ui-monospace,monospace}'
                'a{color:#2458be}</style>'
                f'<h1>Skill assessment</h1><p>{html.escape(result["run_id"])}</p>'
                f'<pre>{html.escape(json.dumps(summary, ensure_ascii=False, indent=2))}</pre>'
                f'<details><summary>Run metadata and static checks</summary><pre>{html.escape(markdown)}</pre></details>'
                + "".join(blocks) + '</html>')
        (directory / "report.html").write_text(page, encoding="utf-8")
    if "junit" in formats:
        root = ET.Element("testsuite", name="skill-assessment", tests=str(len(result["trials"])),
                          failures=str(summary["counts"]["failed"]),
                          errors=str(summary["counts"]["execution_error"] + summary["counts"]["judge_error"]),
                          skipped=str(summary["counts"]["skipped"] + summary["counts"]["cancelled"]))
        for trial in result["trials"]:
            el = ET.SubElement(root, "testcase", name=trial["trial_id"], classname=trial["case_id"])
            state = trial["status"]
            if state != "passed":
                tag = "failure" if state == "failed" else ("skipped" if state in ("skipped", "cancelled") else "error")
                ET.SubElement(el, tag, message=trial.get("error") or state).text = json.dumps(trial.get("grading", {}))
        ET.ElementTree(root).write(directory / "junit.xml", encoding="utf-8", xml_declaration=True)
