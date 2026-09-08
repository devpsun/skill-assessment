"""Installed-package checks: no source checkout or registry dependency at runtime."""
import concurrent.futures
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from skill_assessment.process import executable_command


@unittest.skipUnless(shutil.which("node") and shutil.which("npm"), "Node/npm required for distribution tests")
class DistributionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable, str(ROOT / "scripts/build_npm.py")], check=True, capture_output=True)
        cls.temp = tempfile.TemporaryDirectory(prefix="skill-package-中文 space-")
        cls.base = Path(cls.temp.name)
        cls.env = dict(os.environ, SKILL_ASSESSMENT_HOME=str(cls.base / "cache"),
                       SKILL_ASSESSMENT_PYTHON=sys.executable,
                       npm_config_cache=str(cls.base / "npm-cache"),
                       PIP_INDEX_URL="http://127.0.0.1:9/unreachable",
                       npm_config_registry="http://127.0.0.1:9/unreachable")
        prefix = cls.base / "installed"
        subprocess.run([*executable_command(["npm"]), "install", "--offline", "--ignore-scripts",
                        "--no-audit", "--no-fund", "--prefix", str(prefix),
                        str(ROOT / "dist/skill-assessment-0.1.0.tgz")],
                       check=True, capture_output=True, env=cls.env)
        cls.package = prefix / "node_modules/skill-assessment"
        cls.command = [shutil.which("node"), str(cls.package / "bin/skill-assessment.js")]

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def call(self, *args, **kwargs):
        return subprocess.run([*self.command, *args], cwd=self.base, env=self.env,
                              capture_output=True, text=True, encoding="utf-8", timeout=120, **kwargs)

    def test_01_concurrent_fresh_bootstrap(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            values = list(executor.map(lambda _: self.call("--version"), range(3)))
        for result in values:
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "0.1.0")
        self.assertEqual(len(list((self.base / "cache").glob("*/ready.json"))), 1)

    def test_02_installed_skill_and_example(self):
        install = self.call("skill", "install", "--dest", str(self.base / "agent skills"), "--json")
        self.assertEqual(install.returncode, 0, install.stderr)
        target = json.loads(install.stdout)["installed"]
        check = self.call("check", target, "--json")
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        run = self.call("run", str(self.package / "examples/text-normalizer"),
                        "--benchmark", "--output", str(self.base / "reports"), "--json")
        self.assertEqual(run.returncode, 0, run.stderr + run.stdout)
        path = Path(json.loads(run.stdout)["result"])
        value = json.loads(path.read_text(encoding="utf-8"))
        self.assertTrue(value["benchmark"]["valid"])
        self.assertEqual(value["benchmark"]["pass_rate_delta"], 1)
        self.assertTrue((path.parent / "junit.xml").is_file())

    def test_03_wheel_integrity_failure(self):
        manifest = json.loads((self.package / "wheelhouse/manifest.json").read_text())
        wheel = self.package / "wheelhouse" / manifest["wheel"]
        original = wheel.read_bytes()
        try:
            wheel.write_bytes(original + b"tampered")
            result = self.call("--version")
            self.assertEqual(result.returncode, 2)
            self.assertIn("integrity", result.stderr)
        finally:
            wheel.write_bytes(original)

    def test_04_bootstrap_recovery(self):
        next((self.base / "cache").glob("*/ready.json")).unlink()
        result = self.call("--version")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Preparing", result.stderr)

    def test_05_npm_bin_shim(self):
        prefix = self.package.parent.parent
        shim = prefix / "node_modules/.bin" / ("skill-assessment.cmd" if os.name == "nt" else "skill-assessment")
        result = subprocess.run([*executable_command([str(shim)]), "--version"],
                                cwd=self.base, env=self.env, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
