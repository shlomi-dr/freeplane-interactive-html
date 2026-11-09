#!/usr/bin/env python3
"""Generated Python companion checks; real Freeplane is opt-in."""
import os
import shutil
import sys
import pathlib
import hashlib
import json
import re
import subprocess
import tempfile
import unittest

from test_companion_python import CompanionPythonTests

REPO = pathlib.Path(__file__).resolve().parents[1]
PACKAGE = REPO / "dist" / "freeplane-interactive-html.py"
RUN_RUNTIME = "--runtime" in sys.argv
if RUN_RUNTIME:
    sys.argv.remove("--runtime")


class InstalledRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="copied python runtime ")
        self.runner = pathlib.Path(self.tmp.name) / "freeplane-interactive-html.py"
        shutil.copyfile(PACKAGE, self.runner)

    def tearDown(self):
        self.tmp.cleanup()

    @unittest.skipUnless(RUN_RUNTIME, "pass --runtime to launch installed Freeplane")
    def test_clockwork_fixture_and_formula_safety(self):
        app = os.environ.get("FREEPLANE_HOME", "/Applications/Freeplane.app/Contents/app")
        env = {**os.environ, "FREEPLANE_HOME": app}
        source = REPO / "examples" / "Clockwork Garden Festival.mm"
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory(prefix="companion runtime ") as temporary:
            root = pathlib.Path(temporary)
            destination = root / "runtime output.html"
            result = subprocess.run([sys.executable, str(self.runner), str(source), str(destination)], env=env,
                                    text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    timeout=240)
            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = self.read_manifest(destination)
            self.assertEqual(len(manifest["nodes"]), 43)
            self.assertEqual(len(manifest["links"]), 2)
            self.assertTrue(all(link["resolved"]["shape"] == "CUBIC_CURVE"
                                for link in manifest["links"]))
            self.assertEqual(len(manifest["summaries"]), 1)
            root_children = [node for node in manifest["nodes"]
                             if node.get("parentId") == manifest["rootId"]]
            self.assertTrue(any(node.get("topOrLeft") for node in root_children))
            self.assertTrue(any(not node.get("topOrLeft") for node in root_children))
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), source_hash)

            sentinel = root / "formula sentinel"
            formula_source = root / "formula.mm"
            formula = "=new File('%s').text='triggered'" % sentinel
            formula_source.write_text('<map version="freeplane 1.12.15"><node TEXT="' +
                                      formula.replace("&", "&amp;").replace('"', "&quot;") +
                                      '"/></map>\n')
            formula_output = root / "formula.html"
            result = subprocess.run([sys.executable, str(self.runner), str(formula_source), str(formula_output)],
                                    env=env, text=True, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, timeout=240)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(sentinel.exists(), "map formula executed during export")
            formula_manifest = self.read_manifest(formula_output)
            self.assertTrue(any(node.get("label", "").startswith("=new File")
                                for node in formula_manifest["nodes"]))

    @unittest.skipUnless(RUN_RUNTIME, "pass --runtime to launch installed Freeplane")
    def test_unsupported_connector_preserves_destination(self):
        app = os.environ.get("FREEPLANE_HOME", "/Applications/Freeplane.app/Contents/app")
        with tempfile.TemporaryDirectory(prefix="companion unsupported ") as temporary:
            root = pathlib.Path(temporary)
            source = root / "unsupported connector.mm"
            source.write_text('<map version="freeplane 1.12.15"><node TEXT="root" ID="root">'
                              '<node TEXT="a" ID="a"><arrowlink SHAPE="LINE" DESTINATION="b"/>'
                              '</node><node TEXT="b" ID="b"/></node></map>\n')
            destination = root / "existing.html"
            destination.write_text("KEEP-ME\n")
            result = subprocess.run([sys.executable, str(self.runner), str(source), str(destination)],
                                    env={**os.environ, "FREEPLANE_HOME": app}, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=240)
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertEqual(destination.read_text(), "KEEP-ME\n")
            log_match = re.search(r"Log: (.+)", result.stderr)
            self.assertIsNotNone(log_match, result.stderr)
            log = pathlib.Path(log_match.group(1)).read_text()
            self.assertIn("Unsupported captured connector shape", log)
            self.assertNotIn("missing map", result.stderr.lower())

    @unittest.skipUnless(RUN_RUNTIME, "pass --runtime to launch installed Freeplane")
    def test_timeout_reaps_owned_runtime(self):
        app = pathlib.Path(os.environ.get("FREEPLANE_HOME", "/Applications/Freeplane.app/Contents/app"))
        if app.suffix == ".app":
            launcher = app / "Contents" / "MacOS" / "Freeplane"
        elif app.is_file():
            launcher = app
        else:
            launcher = app / ".." / "MacOS" / "Freeplane"
        launcher = launcher.resolve()
        with tempfile.TemporaryDirectory(prefix="python runtime timeout ") as temporary:
            root = pathlib.Path(temporary)
            pid_file = root / "runtime.pid"
            wrapper = root / "Freeplane"
            wrapper.write_text("#!/usr/bin/env python3\nimport os, pathlib, sys\n" +
                               f"pathlib.Path({str(pid_file)!r}).write_text(str(os.getpid()))\n" +
                               f"os.execv({str(launcher)!r}, [{str(launcher)!r}] + sys.argv[1:])\n")
            wrapper.chmod(0o755)
            destination = root / "existing.html"
            destination.write_text("KEEP-ME\n")
            result = subprocess.run([sys.executable, str(self.runner),
                                     str(REPO / "examples" / "Clockwork Garden Festival.mm"),
                                     str(destination), "--freeplane", str(wrapper), "--timeout", "1"],
                                    capture_output=True, text=True, timeout=15)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("time limit", result.stderr)
            self.assertEqual(destination.read_text(), "KEEP-ME\n")
            pid = int(pid_file.read_text())
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)
            self.assertRegex(result.stderr, r"Log: .+\.log")

    @staticmethod
    def read_manifest(path):
        match = re.search(r'<script id="manifest" type="application/json">(.*?)</script>',
                          path.read_text(), re.S)
        if not match:
            raise AssertionError("missing embedded manifest")
        return json.loads(match.group(1))


if __name__ == "__main__":
    unittest.main(verbosity=2)
