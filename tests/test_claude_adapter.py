"""Fake Claude CLI boundary checks, explicitly not model integration tests."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from skill_assessment.config import load_suite
from skill_assessment.runner import run_suite


@unittest.skipUnless(shutil.which("node"), "Node is needed for the fake CLI executable")
class ClaudeAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="claude-contract-中文 space-")
        self.base = Path(self.temp.name)
        self.skill = self.base / "demo"
        (self.skill / "evals").mkdir(parents=True)
        (self.skill / "SKILL.md").write_text("---\nname: demo\ndescription: test\n---\nDo the task.\n", encoding="utf-8")
        self.script = self.base / "entry.js"
        self.shim = self.base / ("claude.cmd" if os.name == "nt" else "claude")
        if os.name == "nt":
            self.shim.write_text('@echo off\nset dp0=%~dp0\nnode "%dp0%\\entry.js" %*\n', encoding="utf-8")
        else:
            self.shim = self.script
        self.settings = self.base / "existing-settings.json"
        self.settings.write_text('{"model":"fixture-only"}', encoding="utf-8")
        self.config = {"schema_version": "1", "skill": {"path": ".."},
                       "engine": {"type": "claude_code", "command": [str(self.shim)], "isolation": "controlled",
                                  "settings_file": str(self.settings), "allowed_tools": ["Read"],
                                  "artifacts": ["invocation.json"]},
                       "cases": {"files": ["case.yaml"]}}
        self.case = {"id": "basic", "input": {"prompt": "Do the task"},
                     "judge": {"type": "rule", "assertions": [{"type": "contains", "value": "HIDDEN_EXPECTED"}]}}

    def tearDown(self):
        self.temp.cleanup()

    def run_fixture(self, denied=False):
        self.script.write_text(
            "#!/usr/bin/env node\nconst fs=require('node:fs');const args=process.argv.slice(2);\n"
            "if(args.includes('--version')) {console.log('fixture-claude/1');process.exit(0);}\n"
            "const prompt=fs.readFileSync(0,'utf8');fs.writeFileSync('invocation.json',JSON.stringify({args,prompt}));\n"
            "console.log(JSON.stringify({result:'HIDDEN_EXPECTED',session_id:args[args.indexOf('--session-id')+1],"
            "model:'fixture-model',usage:{input_tokens:10},total_cost_usd:.01,"
            "permission_denials:" + ("[{tool_name:'Read'}]" if denied else "[]") + "}));\n", encoding="utf-8")
        self.script.chmod(0o755)
        for name, value in (("eval.yaml", self.config), ("case.yaml", self.case)):
            (self.skill / "evals" / name).write_text(json.dumps(value), encoding="utf-8")
        return run_suite(load_suite(self.skill), output=self.base / "runs")

    def test_flags_context_and_observed_metadata(self):
        directory, result, code = self.run_fixture()
        self.assertEqual(code, 0, result)
        trial = result["trials"][0]
        invocation = json.loads((directory / "trials" / trial["trial_id"] / "artifacts/invocation.json").read_text(encoding="utf-8"))
        self.assertIn("--safe-mode", invocation["args"])
        self.assertIn(str(self.settings), invocation["args"])
        self.assertIn("SKILL.md", invocation["prompt"])
        self.assertNotIn("HIDDEN_EXPECTED", invocation["prompt"])
        self.assertEqual(trial["execution"]["agent_version"], "fixture-claude/1")
        self.assertEqual(trial["execution"]["model"], "fixture-model")
        self.assertFalse(any(p.name == self.settings.name for p in (directory / "snapshots").rglob("*")))

    def test_permission_denial_is_execution_error(self):
        _, result, code = self.run_fixture(denied=True)
        self.assertEqual(code, 2)
        self.assertEqual(result["trials"][0]["status"], "execution_error")
        self.assertIn("permission", result["trials"][0]["error"])
