import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from skill_assessment import yamlio
from skill_assessment.common import AssessmentError, contained, read_json
from skill_assessment.config import load_suite
from skill_assessment.process import run_process
from skill_assessment.reporting import render
from skill_assessment.runner import run_suite
from skill_assessment.validation import check_skill, has_errors


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="skill-eval-中文 space-")
        self.base = Path(self.temp.name)
        self.skill = self.base / "demo"
        (self.skill / "evals").mkdir(parents=True)
        self.entry = self.skill / "SKILL.md"
        self.entry.write_text("---\nname: demo\ndescription: A test skill\n---\nDo a test task.\n", encoding="utf-8")
        self.engine = {"type": "local", "command": [sys.executable, str(ROOT / "tests/support_agent.py"),
                                                    "{input_file}", "{output_file}"],
                       "isolation": "controlled"}
        self.case = {"id": "basic", "input": {"prompt": "done"},
                     "judge": {"type": "rule", "assertions": [{"type": "contains", "value": "done"}]}}
        self.config = {"schema_version": "1", "skill": {"path": ".."}, "engine": self.engine,
                       "cases": {"files": ["case.yaml"]}}

    def tearDown(self):
        self.temp.cleanup()

    def suite(self):
        (self.skill / "evals/eval.yaml").write_text(json.dumps(self.config), encoding="utf-8")
        (self.skill / "evals/case.yaml").write_text(json.dumps(self.case), encoding="utf-8")
        return load_suite(self.skill)

    def run_case(self, **kwargs):
        return run_suite(self.suite(), output=self.base / "runs", **kwargs)

    def test_valid_static(self):
        self.assertFalse(has_errors(check_skill(self.skill)))

    def test_duplicate_yaml(self):
        with self.assertRaises(AssessmentError):
            yamlio.loads("name: x\nname: y\n")

    def test_yaml_alias_and_unsafe_tag(self):
        for text in ("a: &x [1]\nb: *x", "a: !!python/object:abc {}"):
            with self.subTest(text=text), self.assertRaises(AssessmentError):
                yamlio.loads(text)

    def test_json_compatible_yaml(self):
        self.assertEqual(yamlio.loads("date: 2026-01-01")["date"], "2026-01-01")
        for text in ("value: .inf", "value: .nan", "value: !!set {a: null}"):
            with self.subTest(text=text), self.assertRaises(AssessmentError):
                yamlio.loads(text)

    def test_strict_json_input(self):
        path = self.base / "invalid.json"
        for text in ('{"a":1,"a":2}', '{"a":1e999}', '{"a":NaN}'):
            path.write_text(text)
            with self.subTest(text=text), self.assertRaises(AssessmentError):
                read_json(path)

    def test_nested_boolean_is_not_number(self):
        self.case["input"]["prompt"] = '{"value":true}'
        self.case["judge"]["assertions"] = [{"type": "json_equals", "pointer": "", "value": {"value": 1}}]
        _, result, code = self.run_case()
        self.assertEqual(code, 1, result)

    def test_case_ids_are_windows_portable(self):
        self.case["id"] = "CON"
        with self.assertRaises(AssessmentError):
            self.suite()

    def test_tampered_report_summary_is_rejected(self):
        directory, result, _ = self.run_case()
        result["summary"]["planned"] = 99
        with self.assertRaises(AssessmentError):
            render(result, directory, ["html"])

    def test_output_parent_can_contain_target_skill(self):
        _, result, code = run_suite(self.suite(), output=self.base)
        self.assertEqual(code, 0, result)

    def test_yaml_encoding_and_metadata_types(self):
        self.entry.write_text("\ufeff---\r\nname: demo\r\ndescription: ok\r\nmetadata:\r\n  version: 1\r\n---\r\nbody", encoding="utf-8")
        self.assertIn("SPEC009", [x["rule_id"] for x in check_skill(self.skill)["issues"]])

    def test_links_and_fences(self):
        with self.entry.open("a", encoding="utf-8") as f:
            f.write("\n" + chr(96)*3 + "\n[ignored](missing.py)\n" + chr(96)*3 + "\n")
        self.assertFalse(has_errors(check_skill(self.skill)))
        with self.entry.open("a") as f:
            f.write("\n[missing](missing.md)\n")
        self.assertTrue(has_errors(check_skill(self.skill)))

    def test_unknown_fields(self):
        self.config["engine"]["typo"] = True
        with self.assertRaises(AssessmentError):
            self.suite()

    def test_invalid_constraints(self):
        for value in (True, 0, -1, "10"):
            self.case["constraints"] = {"timeout_seconds": value}
            with self.subTest(value=value), self.assertRaises(AssessmentError):
                self.suite()

    def test_path_traversal(self):
        for p in ("../x", "/tmp/x", "C:/temp/x", "a\\..\\x", "a//b"):
            with self.subTest(path=p), self.assertRaises(AssessmentError):
                contained(self.base, p)

    def test_static_gate_and_source_unchanged(self):
        self.entry.write_text("broken", encoding="utf-8")
        directory, result, code = self.run_case()
        self.assertEqual(code, 1)
        self.assertEqual(result["blocked"], "static_validation")
        self.assertEqual(result["summary"]["executed"], 0)
        self.assertFalse((directory / "trials").exists())

    def test_pass_and_snapshot_isolation(self):
        self.engine["parameters"] = {"mode": "leak-check"}
        before = self.entry.read_bytes()
        directory, result, code = self.run_case()
        self.assertEqual(code, 0, result)
        self.assertEqual(self.entry.read_bytes(), before)
        self.assertEqual(result["summary"]["pass_rate"], 1)
        self.assertTrue((directory / "snapshots/cases/basic/case.json").exists())
        self.assertTrue((directory / "report.html").exists())

    def test_functional_failure(self):
        self.case["input"]["prompt"] = "wrong"
        _, result, code = self.run_case()
        self.assertEqual(code, 1)
        self.assertEqual(result["trials"][0]["status"], "failed")

    def test_execution_errors(self):
        for mode in ("exit", "missing", "invalid", "escape", "timeout"):
            with self.subTest(mode=mode):
                self.engine["parameters"] = {"mode": mode}
                self.case["constraints"] = {"timeout_seconds": 0.2 if mode == "timeout" else 10}
                _, result, code = self.run_case()
                self.assertEqual(code, 2, result)
                self.assertEqual(result["trials"][0]["status"], "execution_error")
                self.assertIsNone(result["summary"]["pass_rate"])

    def test_artifact_grading_and_portable_report(self):
        self.engine["parameters"] = {"mode": "artifact"}
        self.case["judge"]["assertions"] = [{"type": "file_json_equals", "path": "data.json",
                                             "pointer": "/answer", "value": 42}]
        directory, result, code = self.run_case()
        self.assertEqual(code, 0, result)
        moved = self.base / "moved"
        shutil.copytree(directory, moved)
        render(read_json(moved / "result.json"), moved, ["html", "markdown", "junit"])
        self.assertIn('trials/basic--with_skill--1/artifacts/data.json', (moved / "report.html").read_text())
        self.assertTrue((moved / "junit.xml").exists())

    def test_agent_judge_and_malformed_output(self):
        self.case["judge"] = {"type": "agent", "criteria": ["Respond correctly"],
                              "engine": {**self.engine, "parameters": {"mode": "judge"}}}
        _, result, code = self.run_case()
        self.assertEqual(code, 0, result)
        self.case["judge"]["engine"]["parameters"]["mode"] = "bad-judge"
        _, result, code = self.run_case()
        self.assertEqual(code, 2)
        self.assertEqual(result["trials"][0]["status"], "judge_error")

    def test_script_judge(self):
        script = self.skill / "evals/grader.py"
        script.write_text("import json,sys\nfrom pathlib import Path\n"
                          "p=json.loads(Path(sys.argv[1]).read_text())\n"
                          "v=p['final_output']=='done'\n"
                          "Path(sys.argv[2]).write_text(json.dumps({'passed':v,'assertions':[{'passed':v,'evidence':p['final_output']}]}))\n")
        self.case["judge"] = {"type": "script", "path": "grader.py"}
        _, result, code = self.run_case()
        self.assertEqual(code, 0, result)

    def test_repeated_benchmark_and_uncontrolled_baseline(self):
        _, result, code = self.run_case(repeat=2, benchmark=True)
        self.assertEqual(code, 0, result)
        self.assertEqual(result["summary"]["planned"], 4)
        self.assertTrue(result["benchmark"]["valid"])
        self.engine["isolation"] = "inherited"
        _, result, _ = self.run_case(benchmark=True)
        self.assertFalse(result["benchmark"]["valid"])
        self.assertIsNone(result["benchmark"]["pass_rate_delta"])

    def test_parent_rerun_and_changed_standard(self):
        self.case["input"]["prompt"] = "wrong"
        first, _, _ = self.run_case()
        self.case["judge"]["assertions"][0]["value"] = "wrong"
        _, result, code = self.run_case(parent=first / "result.json", failed_only=True, change_note="Correct expected output")
        self.assertEqual(code, 0)
        self.assertFalse(result["comparison"][0]["comparable"])
        self.assertEqual(result["change_note"], "Correct expected output")

    def test_html_escapes_output(self):
        self.case["input"]["prompt"] = "<script>alert(1)</script>"
        self.case["judge"]["assertions"][0]["value"] = self.case["input"]["prompt"]
        directory, _, _ = self.run_case()
        page = (directory / "report.html").read_text()
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)

    def test_regex_timeout(self):
        self.case["input"]["prompt"] = "a" * 30 + "!"
        self.case["judge"] = {"type": "rule", "timeout_seconds": 0.15,
                              "assertions": [{"type": "regex", "value": "(a+)+$"}]}
        _, result, code = self.run_case()
        self.assertEqual(code, 2)
        self.assertEqual(result["trials"][0]["status"], "judge_error")

    def test_stdout_limit(self):
        proc = run_process([sys.executable, "-c", "print('x'*100000)"], self.base,
                           self.base / "logs", 10, max_log_bytes=1024)
        self.assertEqual(proc["status"], "output_limit")
        self.assertLessEqual((self.base / "logs/stdout.txt").stat().st_size, 1024)

    def test_demo_examples(self):
        for name in ("text-normalizer", "sales-summary", "sum-numbers"):
            with self.subTest(name=name):
                _, result, code = run_suite(load_suite(ROOT / "examples" / name), output=self.base / "examples")
                self.assertEqual(code, 0, result)


if __name__ == "__main__":
    unittest.main()
