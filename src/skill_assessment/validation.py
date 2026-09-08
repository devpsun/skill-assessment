"""Static checks; these never execute a Skill or access the network."""

import re
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urlsplit

from . import yamlio
from .common import AssessmentError

SPEC = "https://agentskills.io/specification"
FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
EXTENSIONS = {"argument-hint", "disable-model-invocation", "user-invocable",
              "model", "context", "agent", "hooks"}


def check_skill(directory, strict=False):
    root = Path(directory).resolve()
    issues = []

    def add(rule, severity, message, line=None, category="spec", suggestion=None):
        issues.append(dict(rule_id=rule, rule_version="1", severity=severity,
                           category=category, message=message, file="SKILL.md",
                           line=line, column=None, source=SPEC if category == "spec" else "project",
                           suggestion=suggestion))

    result = {"schema_version": "1", "rule_profile": "agentskills-unicode-v1",
              "skill_path": str(root), "issues": issues,
              "coverage": ["frontmatter", "inline-local-markdown-links"],
              "limitations": ["Dynamic paths and semantic instruction quality are not checked."]}
    path = root / "SKILL.md"
    if not root.is_dir() or not path.is_file():
        add("SPEC001", "error", "A directory containing SKILL.md is required")
        return result
    if not any(p.name == "SKILL.md" for p in root.iterdir()):
        add("SPEC002", "error", "The entry filename must be exactly SKILL.md")
    try:
        if path.stat().st_size > 2 * 1024 * 1024:
            raise OSError("SKILL.md exceeds 2 MiB")
        text = path.read_text(encoding="utf-8-sig")
    except (UnicodeError, OSError) as exc:
        add("IO001", "error", str(exc), category="engineering")
        return result
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        add("SPEC003", "error", "SKILL.md must start with YAML frontmatter", 1)
        return result
    closing = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if closing is None:
        add("SPEC003", "error", "Missing closing frontmatter delimiter", 1)
        return result
    try:
        meta = yamlio.loads("\n".join(lines[1:closing]), str(path))
        if not isinstance(meta, dict):
            raise AssessmentError("Frontmatter must be a mapping")
    except AssessmentError as exc:
        add("SPEC004", "error", str(exc), 2)
        return result

    def line_for(key):
        return next((i + 1 for i, ln in enumerate(lines[:closing])
                     if re.match(rf"^{re.escape(key)}\s*:", ln)), 2)

    for key, maximum in (("name", 64), ("description", 1024), ("compatibility", 500)):
        if key not in meta and key == "compatibility":
            continue
        value = meta.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > maximum:
            add("SPEC005", "error", f"{key} must be a non-empty string of at most {maximum} characters",
                line_for(key))
    name = meta.get("name")
    if isinstance(name, str) and name:
        normalized = unicodedata.normalize("NFKC", name)
        valid = (name == name.strip() and normalized == normalized.lower()
                 and all(c.isalnum() or c == "-" for c in normalized)
                 and not normalized.startswith("-") and not normalized.endswith("-")
                 and "--" not in normalized)
        if not valid:
            add("SPEC006", "error", "Invalid Skill name: lowercase letters/digits and single hyphens required",
                line_for("name"))
        if normalized != unicodedata.normalize("NFKC", root.name):
            add("SPEC007", "error", "Skill name must match its directory name", line_for("name"))
    for key in ("license", "allowed-tools"):
        if key in meta and not isinstance(meta[key], str):
            add("SPEC008", "error", f"{key} must be a string", line_for(key))
    if "metadata" in meta:
        val = meta["metadata"]
        if not isinstance(val, dict) or not all(isinstance(v, str) for v in val.values()):
            add("SPEC009", "error", "metadata must map strings to strings", line_for("metadata"))
    for key in meta.keys() - FIELDS:
        if key not in EXTENSIONS or strict:
            add("EXT001", "error" if strict else "warning", f"Non-standard frontmatter field: {key}",
                line_for(key), "engineering")
    body = lines[closing + 1:]
    if not "\n".join(body).strip():
        add("STYLE001", "warning", "Skill has no instructions", closing + 2, "advisory")
    if len(lines) >= 500:
        add("STYLE002", "warning", "Consider moving detailed instructions to references",
            1, "advisory")
    fence = None
    for i, line in enumerate(body, closing + 2):
        match = re.match(r"^\s*(\x60{3,}|~{3,})", line)
        if match:
            marker = match.group(1)
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
            continue
        if fence or line.startswith("    "):
            continue
        line = re.sub(r"(\x60+).*?\1", "", line)
        for target in re.findall(r"\[[^\]]*\]\((<[^>]*>|[^)\s]+)(?:\s+[^)]*)?\)", line):
            target = target.strip("<>")
            parts = urlsplit(target)
            if parts.scheme or parts.netloc or not parts.path:
                continue
            decoded = unquote(parts.path)
            dest = (root / decoded).resolve()
            if not dest.is_relative_to(root):
                add("REF002", "warning", f"Reference is outside Skill: {target}", i, "engineering")
            elif not dest.exists():
                add("REF001", "error", f"Local link does not exist: {target}", i, "engineering")
    return result


def has_errors(result):
    return any(i["severity"] == "error" for i in result["issues"])
