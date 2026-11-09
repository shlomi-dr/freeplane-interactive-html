#!/usr/bin/env python3
"""Hermetic integration checks for bin/export-map.sh; real Freeplane is opt-in."""
import os
import pathlib
import hashlib
import json
import re
import subprocess
import tempfile
import time
import unittest

REPO = pathlib.Path(__file__).resolve().parents[1]
RUNNER = REPO / "bin" / "export-map.sh"
RUN_RUNTIME = "--runtime" in __import__("sys").argv
if RUN_RUNTIME:
    __import__("sys").argv.remove("--runtime")


class ExportRunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="companion test ")
        self.root = pathlib.Path(self.tmp.name)
        self.input = self.root / "input.mm"
        self.input.write_text("<map version=\"freeplane 1.13.4\"><node TEXT=\"fixture\"/></map>\n")
        self.app = self.root / "Mock Freeplane.app" / "Contents" / "app"
        self.app.mkdir(parents=True)
        (self.app / "freeplanelauncher.jar").touch()
        native = self.app.parent / "MacOS"
        native.mkdir()
        self.fake = native / "Freeplane"
        self.log = self.root / "launcher args.log"
        self._fake_launcher()

    def tearDown(self):
        self.tmp.cleanup()

    def _fake_launcher(self, body=None):
        body = body or r'''#!/bin/bash
set -eu
printf '%s\n' "$@" >"$ARG_LOG"
printf '%s\n' "$$" >"$PID_LOG"
case ${MOCK_MODE:-success} in
  false-success) exit 0 ;;
  write-then-fail)
    printf 'partial\n' >"$COMPANION_OUTPUT"
    : >"$COMPANION_MARKER"
    exit 9 ;;
  stubborn)
    exec python3 -c 'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)' ;;
  success)
    printf '<html>fixture</html>\n' >"$COMPANION_OUTPUT"
    test -s "$COMPANION_OUTPUT"
    : >"$COMPANION_MARKER"
    exit 0 ;;
esac
'''
        self.fake.write_text(body)
        self.fake.chmod(0o755)

    def run_export(self, output, **extra):
        env = os.environ.copy()
        env.update({"FREEPLANE_HOME": str(self.app), "ARG_LOG": str(self.log), "PID_LOG": str(self.root / "launcher.pid")})
        env.update(extra)
        return subprocess.run([str(RUNNER), str(self.input), str(output)], env=env,
                              text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=15)

    def test_invalid_paths_are_rejected_before_launch(self):
        cases = [
            (self.root / "missing.mm", self.root / "out.html"),
            (self.input, self.root / "out.txt"),
            (self.input, self.root / "absent" / "out.html"),
        ]
        for source, output in cases:
            with self.subTest(source=source, output=output):
                result = subprocess.run([str(RUNNER), str(source), str(output)],
                                        env={**os.environ, "FREEPLANE_HOME": str(self.app)},
                                        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(output.exists())
        self.assertFalse(self.log.exists())
        self.assertEqual(self.input.read_text().count("fixture"), 1)

    def test_same_file_alias_is_rejected_without_modifying_source(self):
        alias = self.root / "alias.html"
        alias.symlink_to(self.input)
        before = self.input.read_bytes()
        result = self.run_export(alias)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("same file", result.stderr)
        self.assertEqual(self.input.read_bytes(), before)
        self.assertFalse(self.log.exists())

    def test_zero_exit_without_marker_preserves_existing_destination(self):
        self._fake_launcher()
        destination = self.root / "existing.html"
        destination.write_text("KEEP-ME\n")
        result = self.run_export(destination, MOCK_MODE="false-success")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(destination.read_text(), "KEEP-ME\n")
        self.assertIn("did not complete", result.stderr)

    def test_nonzero_exit_after_marker_preserves_existing_destination(self):
        destination = self.root / "existing.html"
        destination.write_text("KEEP-ME\n")
        result = self.run_export(destination, MOCK_MODE="write-then-fail")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(destination.read_text(), "KEEP-ME\n")

    def test_quoted_unicode_arguments_and_marker_completion(self):
        weird_source = self.root / "map 'quoted' 雪 $literal.mm"
        weird_source.write_text(self.input.read_text())
        self.input.unlink()
        self.input = weird_source
        destination = self.root / "page '雪' $value.html"
        result = self.run_export(destination)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(destination.read_text(), "<html>fixture</html>\n")
        args = self.log.read_text()
        self.assertIn(str(weird_source), args)
        self.assertIn("-S", args)
        self.assertEqual(pathlib.Path(result.stdout.strip()), destination.resolve())

    def test_timeout_kills_stubborn_launcher_and_preserves_destination(self):
        destination = self.root / "timeout.html"
        destination.write_text("KEEP-ME\n")
        started = time.monotonic()
        result = self.run_export(destination, MOCK_MODE="stubborn", FREEPLANE_EXPORT_TIMEOUT="1")
        elapsed = time.monotonic() - started
        self.assertEqual(result.returncode, 124, result.stderr)
        self.assertLess(elapsed, 8, f"timeout cleanup took {elapsed:.1f}s")
        self.assertIn("time limit", result.stderr)
        self.assertEqual(destination.read_text(), "KEEP-ME\n")
        pid = int((self.root / "launcher.pid").read_text())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)


class InstalledRuntimeTests(unittest.TestCase):
    @unittest.skipUnless(RUN_RUNTIME, "pass --runtime to launch installed Freeplane")
    def test_clockwork_fixture_and_formula_safety(self):
        app = os.environ.get("FREEPLANE_HOME", "/Applications/Freeplane.app/Contents/app")
        env = {**os.environ, "FREEPLANE_HOME": app}
        source = REPO / "examples" / "Clockwork Garden Festival.mm"
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory(prefix="companion runtime ") as temporary:
            root = pathlib.Path(temporary)
            destination = root / "runtime output.html"
            result = subprocess.run([str(RUNNER), str(source), str(destination)], env=env,
                                    text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    timeout=240)
            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = self.read_manifest(destination)
            self.assertEqual(len(manifest["nodes"]), 43)
            self.assertEqual(len(manifest["links"]), 2)
            self.assertTrue(all(link["resolved"]["shape"] == "CUBIC_CURVE"
                                for link in manifest["links"]))
            self.assertTrue(manifest["summaries"])
            self.assertTrue(any(node.get("topOrLeft") for node in manifest["nodes"]))
            self.assertTrue(any(not node.get("topOrLeft") for node in manifest["nodes"]))
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), source_hash)

            sentinel = root / "formula sentinel"
            formula_source = root / "formula.mm"
            formula = "=new File('%s').text='triggered'" % sentinel
            formula_source.write_text('<map version="freeplane 1.13.4"><node TEXT="' +
                                      formula.replace("&", "&amp;").replace('"', "&quot;") +
                                      '"/></map>\n')
            formula_output = root / "formula.html"
            result = subprocess.run([str(RUNNER), str(formula_source), str(formula_output)],
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
            source.write_text('<map version="freeplane 1.13.4"><node TEXT="root" ID="root">'
                              '<node TEXT="a" ID="a"><arrowlink SHAPE="LINE" DESTINATION="b"/>'
                              '</node><node TEXT="b" ID="b"/></node></map>\n')
            destination = root / "existing.html"
            destination.write_text("KEEP-ME\n")
            result = subprocess.run([str(RUNNER), str(source), str(destination)],
                                    env={**os.environ, "FREEPLANE_HOME": app}, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=240)
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertEqual(destination.read_text(), "KEEP-ME\n")
            self.assertNotIn("missing map", result.stderr.lower())

    @staticmethod
    def read_manifest(path):
        match = re.search(r'<script id="manifest" type="application/json">(.*?)</script>',
                          path.read_text(), re.S)
        if not match:
            raise AssertionError("missing embedded manifest")
        return json.loads(match.group(1))


if __name__ == "__main__":
    unittest.main(verbosity=2)
