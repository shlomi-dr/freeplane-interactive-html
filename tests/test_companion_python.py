"""Hermetic tests for the generated single-file Python companion."""
import os
import re
import shutil
import signal
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "dist" / "freeplane-interactive-html.py"


class CompanionPythonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="companion python ")
        self.root = Path(self.temp.name)
        self.package = self.root / "standalone companion.py"
        shutil.copyfile(PACKAGE, self.package)
        self.source = self.root / "map '雪' $input.mm"
        self.source.write_text('<map version="freeplane 1.13.4"><node TEXT="fixture"/></map>\n')
        self.app = self.root / "Mock Freeplane.app"
        self.launcher = self.app / "Contents" / "MacOS" / "Freeplane"
        self.launcher.parent.mkdir(parents=True)
        self.log = self.root / "launcher args"
        self._launcher()

    def tearDown(self):
        for log in self.root.glob("retained-log-*"):
            Path(log.read_text()).unlink(missing_ok=True)
        self.temp.cleanup()

    def _launcher(self):
        code = r'''#!/usr/bin/env python3
import os, pathlib, sys, time
for name in ("COMPANION_ADDON", "COMPANION_TEMPLATE"):
    assert pathlib.Path(os.environ[name]).is_file()
profile = pathlib.Path(next(arg[2:] for arg in sys.argv if arg.startswith("-U")))
for version in ("1.12.x", "1.13.x"):
    settings = (profile / version / "auto.properties").read_text()
    assert "single_instance=false" in settings
    assert "formula_disable_plugin=true" in settings
pathlib.Path(os.environ["PID_LOG"]).write_text(str(os.getpid()))
pathlib.Path(os.environ["ARG_LOG"]).write_text("\n".join(sys.argv[1:]))
mode = os.environ.get("MOCK_MODE", "success")
if mode == "false-success":
    print("ERROR fixture diagnostic", flush=True)
    sys.exit(0)
if mode == "timeout":
    import signal
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    time.sleep(60)
if mode == "empty-output":
    pathlib.Path(os.environ["COMPANION_OUTPUT"]).touch()
    pathlib.Path(os.environ["COMPANION_MARKER"]).touch()
    sys.exit(0)
if mode == "write-fail":
    pathlib.Path(os.environ["COMPANION_OUTPUT"]).write_text("partial")
    pathlib.Path(os.environ["COMPANION_MARKER"]).touch()
    sys.exit(9)
pathlib.Path(os.environ["COMPANION_OUTPUT"]).write_text("<html>fixture</html>\n")
pathlib.Path(os.environ["COMPANION_MARKER"]).touch()
'''
        self.launcher.write_text(code)
        self.launcher.chmod(0o755)

    def run_export(self, destination, **env_extra):
        env = os.environ.copy()
        env.update({"ARG_LOG": str(self.log), "PID_LOG": str(self.root / "launcher.pid"), "MOCK_MODE": env_extra.pop("MOCK_MODE", "success")})
        env.update(env_extra)
        result = subprocess.run([sys.executable, str(self.package), str(self.source), str(destination),
                                 "--freeplane", str(self.app)], env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15, cwd=self.root)
        self.remember_log(result.stderr)
        return result

    def remember_log(self, stderr):
        match = re.search(r"Log: (.+)", stderr)
        if match:
            path = Path(match.group(1))
            self.assertTrue(path.is_file(), stderr)
            (self.root / ("retained-log-" + path.name)).write_text(str(path))
            return path

    def assert_owned_stopped(self):
        pid = int((self.root / "launcher.pid").read_text())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)
        self.assertFalse(list(self.root.glob(".freeplane-html-export-*")))

    def test_invalid_paths_are_rejected_before_launch(self):
        for source, output in ((self.root / "missing.mm", self.root / "out.html"),
                               (self.source, self.root / "out.txt"),
                               (self.source, self.root / "missing" / "out.html")):
            result = subprocess.run([sys.executable, str(self.package), str(source), str(output),
                                     "--freeplane", str(self.app)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())
        self.assertFalse(self.log.exists())

    def test_invalid_explicit_freeplane_does_not_fall_back(self):
        fallback = self.root / "freeplane"
        fallback.write_text("#!/bin/sh\n: > \"$ARG_LOG\"\n")
        fallback.chmod(0o755)
        destination = self.root / "out.html"
        invalid = self.root / "missing Freeplane.app"
        for option in ("--freeplane", "FREEPLANE_HOME"):
            with self.subTest(option=option):
                env = {**os.environ, "PATH": str(self.root), "ARG_LOG": str(self.log)}
                env.pop("FREEPLANE_HOME", None)
                command = [sys.executable, "-c",
                           "import runpy, sys; sys.platform = 'linux'; "
                           "runpy.run_path(sys.argv.pop(1), run_name='__main__')",
                           str(self.package), str(self.source), str(destination)]
                if option == "--freeplane":
                    command.extend((option, str(invalid)))
                else:
                    env[option] = str(invalid)
                result = subprocess.run(command, env=env, capture_output=True, text=True,
                                        timeout=15, cwd=self.root)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("explicit Freeplane selection", result.stderr)
                self.assertIn(str(invalid), result.stderr)
                self.assertFalse(self.log.exists(), "default launcher was invoked")
                self.assertFalse(destination.exists())

    def test_executable_launcher_with_arbitrary_name_is_accepted(self):
        renamed = self.root / "custom launcher"
        self.launcher.rename(renamed)
        self.app = renamed
        destination = self.root / "custom.html"
        result = self.run_export(destination)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(destination.read_text(), "<html>fixture</html>\n")
        self.assertTrue(self.log.is_file())

    def test_distribution_contains_notices_and_provenance(self):
        script = self.package.read_text()
        for name in ("LICENSE", "NOTICE"):
            for line in (ROOT / name).read_text().splitlines():
                self.assertIn("# " + line + "\n", script)
        self.assertIn("# Source: https://github.com/shlomi-dr/freeplane-interactive-html", script)
        self.assertIn("# src/companion.py:", script)

    def test_embedded_assets_work_from_another_directory_and_preserve_weird_names(self):
        before = self.source.read_bytes()
        destination = self.root / "page '雪' $output.html"
        result = self.run_export(destination)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual(destination.read_text(), "<html>fixture</html>\n")
        args = self.log.read_text()
        self.assertIn(str(self.source.resolve()), args)
        self.assertIn("-S", args)
        profile = Path(next(arg[2:] for arg in args.splitlines() if arg.startswith("-U")))
        self.assertFalse(profile.parent.exists(), "success artifacts were retained")
        self.assertNotIn("Log:", result.stderr)
        self.assertFalse((self.root / "InteractiveHtmlAddon.groovy").exists())

    def test_zero_exit_without_marker_preserves_existing_output(self):
        destination = self.root / "existing.html"
        destination.write_text("KEEP\n")
        result = self.run_export(destination, MOCK_MODE="false-success")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(destination.read_text(), "KEEP\n")
        self.assertIn("ERROR fixture diagnostic", self.remember_log(result.stderr).read_text())

    def test_nonzero_after_staged_output_preserves_existing_output(self):
        destination = self.root / "existing.html"
        destination.write_text("KEEP\n")
        result = self.run_export(destination, MOCK_MODE="write-fail")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(destination.read_text(), "KEEP\n")

    def test_marker_with_empty_output_preserves_existing_output(self):
        destination = self.root / "existing.html"
        destination.write_text("KEEP\n")
        result = self.run_export(destination, MOCK_MODE="empty-output")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(destination.read_text(), "KEEP\n")
        self.assertFalse(list(self.root.glob(".freeplane-html-export-*")))

    def test_same_file_alias_is_rejected_without_modification(self):
        alias = self.root / "alias.html"
        alias.symlink_to(self.source)
        before = self.source.read_bytes()
        result = self.run_export(alias)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("same file", result.stderr)
        self.assertEqual(self.source.read_bytes(), before)

    def test_timeout_stops_owned_launcher_and_preserves_output(self):
        destination = self.root / "timeout.html"
        destination.write_text("KEEP\n")
        env = os.environ.copy()
        env.update({"ARG_LOG": str(self.log), "PID_LOG": str(self.root / "launcher.pid"), "MOCK_MODE": "timeout"})
        result = subprocess.run([sys.executable, str(self.package), str(self.source),
                                 str(destination), "--freeplane", str(self.app),
                                 "--timeout", "1"], env=env, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8)
        self.assertNotEqual(result.returncode, 0)
        self.remember_log(result.stderr)
        self.assert_owned_stopped()
        self.assertIn("time limit", result.stderr)
        self.assertEqual(destination.read_text(), "KEEP\n")

    @unittest.skipUnless(os.name == "posix", "POSIX cancellation signals")
    def test_cancellation_reaps_owned_launcher_and_preserves_output(self):
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            with self.subTest(signal=signum):
                self.log.unlink(missing_ok=True)
                destination = self.root / "cancel.html"
                destination.write_text("KEEP\n")
                env = {**os.environ, "ARG_LOG": str(self.log),
                       "PID_LOG": str(self.root / "launcher.pid"), "MOCK_MODE": "timeout"}
                process = subprocess.Popen([sys.executable, str(self.package), str(self.source),
                                            str(destination), "--freeplane", str(self.app)],
                                           env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                try:
                    deadline = time.monotonic() + 5
                    while not self.log.exists() and time.monotonic() < deadline:
                        time.sleep(0.02)
                    self.assertTrue(self.log.exists(), "launcher did not start")
                    process.send_signal(signum)
                    stdout, stderr = process.communicate(timeout=8)
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.communicate()
                self.assertNotEqual(process.returncode, 0, stdout)
                self.assertIn("cancelled", stderr)
                self.remember_log(stderr)
                self.assert_owned_stopped()
                self.assertEqual(destination.read_text(), "KEEP\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
