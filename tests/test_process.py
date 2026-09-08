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
from skill_assessment.process import run_process

CHILD = "import time;from pathlib import Path\nwhile True:\n Path('heartbeat').write_text(str(time.time()))\n time.sleep(.04)"
PARENT = "import subprocess,sys,time\nsubprocess.Popen([sys.executable,'-c'," + repr(CHILD) + "])\ntime.sleep(30)"


class ProcessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="process-中文 space-&-")
        self.base = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def assert_child_stopped(self):
        path = self.base / "heartbeat"
        self.assertTrue(path.is_file(), "Child never started; test did not exercise descendants")
        before = path.read_bytes()
        time.sleep(.25)
        self.assertEqual(path.read_bytes(), before, "Descendant is still running")

    def test_timeout_kills_descendants(self):
        result = run_process([sys.executable, "-c", PARENT], self.base, self.base / "logs", 1.5)
        self.assertEqual(result["status"], "timeout")
        self.assert_child_stopped()

    def test_completed_parent_kills_descendants(self):
        command = PARENT.replace("time.sleep(30)", "time.sleep(1)")
        result = run_process([sys.executable, "-c", command], self.base, self.base / "logs", 10)
        self.assertEqual(result["returncode"], 0, result)
        self.assert_child_stopped()

    def test_cooperative_cancel_preserves_report(self):
        skill = self.base / "demo"
        (skill / "evals").mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: demo\ndescription: test\n---\nRun test", encoding="utf-8")
        agent = self.base / "agent.py"
        child = CHILD.replace("Path('heartbeat')", "Path(" + repr(str(self.base / "heartbeat")) + ")")
        agent.write_text("import subprocess,sys,time\nsubprocess.Popen([sys.executable,'-c'," + repr(child)
                         + "])\ntime.sleep(30)", encoding="utf-8")
        config = {"schema_version": "1", "skill": {"path": ".."},
                  "engine": {"type": "local", "command": [sys.executable, str(agent), "{input_file}", "{output_file}"]},
                  "cases": {"files": ["case.yaml"]}}
        case = {"id": "cancel", "input": {"prompt": "wait"},
                "judge": {"type": "rule", "assertions": [{"type": "contains", "value": "done"}]}}
        (skill / "evals/eval.yaml").write_text(json.dumps(config), encoding="utf-8")
        (skill / "evals/case.yaml").write_text(json.dumps(case), encoding="utf-8")
        cancel = self.base / "cancel"
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), SKILL_ASSESSMENT_CANCEL_FILE=str(cancel))
        proc = subprocess.Popen([sys.executable, "-m", "skill_assessment", "run", str(skill),
                                 "--output", str(self.base / "runs"), "--json"],
                                env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
        try:
            deadline = time.monotonic() + 15
            while not (self.base / "heartbeat").exists() and time.monotonic() < deadline and proc.poll() is None:
                time.sleep(.05)
            self.assertTrue((self.base / "heartbeat").exists())
            cancel.write_text("cancel")
            stdout, stderr = proc.communicate(timeout=10)
            self.assertEqual(proc.returncode, 130, stdout + stderr)
            result = json.loads(Path(json.loads(stdout)["result"]).read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "cancelled")
            self.assertEqual(result["trials"][0]["status"], "cancelled")
            self.assert_child_stopped()
        finally:
            cancel.touch()
            if proc.poll() is None:
                proc.communicate(timeout=10)

    @unittest.skipUnless(os.name == "nt" and shutil.which("node"), "Windows npm wrapper")
    def test_windows_shim_preserves_literal_arguments(self):
        script = self.base / "entry.js"
        script.write_text("console.log(JSON.stringify(process.argv.slice(2)))", encoding="utf-8")
        shim = self.base / "agent.cmd"
        shim.write_text('@echo off\nset dp0=%~dp0\nnode "%dp0%\\entry.js" %*\n', encoding="utf-8")
        args = ["中文 space", "%PATH%", "& echo BAD", 'quote"and$()']
        result = run_process([str(shim), *args], self.base, self.base / "logs", 10)
        self.assertEqual(result["returncode"], 0, result)
        self.assertEqual(json.loads(result["stdout"]), args)


if __name__ == "__main__":
    unittest.main()
