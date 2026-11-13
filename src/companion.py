#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Export a Freeplane mind map as interactive HTML using installed Freeplane."""
import argparse
import base64
import os
import secrets
import signal
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zlib

VERSION = "0.2.0-alpha.1"
# Generated package embeds these source assets; package.py replaces this mapping.
ASSETS = {}


def fail(message):
    print(f"freeplane-interactive-html: {message}", file=sys.stderr)
    raise SystemExit(2)


def locate_freeplane(override):
    candidates = []
    configured = override if override is not None else os.environ.get("FREEPLANE_HOME")
    if configured is not None:
        if not configured:
            fail("explicit Freeplane selection is empty")
        path = Path(configured).expanduser().resolve()
        if path.is_file() and os.access(path, os.X_OK):
            return path
        if path.suffix == ".app":
            candidates.append(path / "Contents" / "MacOS" / "Freeplane")
        candidates.extend((path / "../MacOS/Freeplane", path / "Freeplane"))
    elif sys.platform == "darwin":
        candidates.extend((Path("/Applications/Freeplane.app/Contents/MacOS/Freeplane"),
                           Path.home() / "Applications/Freeplane.app/Contents/MacOS/Freeplane"))
    else:
        found = shutil.which("freeplane")
        if found:
            return Path(found).resolve()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    if configured is not None:
        fail(f"could not resolve explicit Freeplane selection to an executable launcher: {configured}")
    fail("could not find installed Freeplane; pass --freeplane with its launcher path or app folder")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="input Freeplane .mm file")
    parser.add_argument("output", help="output .html or .htm file")
    parser.add_argument("--freeplane", help="Freeplane launcher, app folder, or Contents/app folder")
    parser.add_argument("--timeout", type=int, default=180, help="export time limit in seconds (default: 180)")
    parser.add_argument("--version", action="version", version=VERSION)
    args = parser.parse_args(argv)
    if args.timeout < 1:
        fail("--timeout must be a positive integer")
    source = Path(args.input).expanduser()
    if not source.is_file() or not os.access(source, os.R_OK) or source.suffix.lower() != ".mm":
        fail(f"input must be an existing readable .mm file: {source}")
    source = source.resolve()
    output = Path(args.output).expanduser()
    if output.suffix.lower() not in (".html", ".htm"):
        fail(f"output must have the .html or .htm extension: {output}")
    if output.is_dir() or not output.parent.is_dir():
        fail(f"output directory does not exist or output is a directory: {output}")
    output = output.parent.resolve() / output.name
    if output.exists() and os.path.samefile(source, output):
        fail("input and output refer to the same file")
    launcher = locate_freeplane(args.freeplane)
    if not ASSETS:
        fail("this source file is a packaging template; run scripts/package.py first")
    try:
        export(launcher, source, output, args.timeout)
    except (OSError, RuntimeError, KeyboardInterrupt) as error:
        fail(str(error) or "export cancelled")
    print(output)


class ExportCancelled(RuntimeError):
    pass


def stop_owned(process):
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def export(launcher, source, output, timeout):
    with tempfile.TemporaryDirectory(prefix="freeplane-interactive-html-") as temporary:
        work = Path(temporary)
        stage = output.parent / (".freeplane-html-export-" + secrets.token_hex(8))
        log = work / "freeplane.log"
        process = None
        handlers = {}

        def cancel(signum, frame):
            raise ExportCancelled(f"export cancelled by {signal.Signals(signum).name}")

        try:
            for name in ("SIGINT", "SIGTERM", "SIGHUP"):
                if hasattr(signal, name):
                    signum = getattr(signal, name)
                    handlers[signum] = signal.signal(signum, cancel)
            paths = {}
            for name, encoded in ASSETS.items():
                path = work / name
                path.write_bytes(zlib.decompress(base64.b64decode(encoded)))
                paths[name] = path
            profile = work / "profile"
            for version in ("1.12.x", "1.13.x"):
                folder = profile / version
                folder.mkdir(parents=True)
                (folder / "auto.properties").write_text(
                    "single_instance=false\nformula_disable_plugin=true\n", encoding="utf-8")
            marker = work / "export.ok"
            env = os.environ.copy()
            env.update({"COMPANION_ADDON": str(paths["InteractiveHtmlAddon.groovy"]),
                        "COMPANION_TEMPLATE": str(paths["viewer-template.html"]),
                        "COMPANION_INPUT": str(source), "COMPANION_OUTPUT": str(stage),
                        "COMPANION_MARKER": str(marker)})
            env.pop("FREEPLANE_HOME", None)
            with log.open("wb") as stream:
                process = subprocess.Popen([str(launcher), f"-U{profile}", f"-R{paths['companion-export.groovy']}", "-S", str(source)],
                                           stdout=stream, stderr=subprocess.STDOUT, env=env)
                try:
                    status = process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    raise RuntimeError(f"Freeplane export exceeded its {timeout}-second time limit") from None
            if status != 0 or not marker.is_file() or not stage.is_file() or stage.stat().st_size == 0:
                lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
                detail = next((line.strip() for line in lines if any(
                    word in line.lower() for word in ("exception", "error", "failed"))),
                              "\n".join(lines[-8:]))
                raise RuntimeError(f"Freeplane did not complete the export (exit {status}).\n{detail}")
            os.replace(stage, output)
        except BaseException:
            # Stop the writer before retaining its complete diagnostic log.
            for signum in handlers:
                signal.signal(signum, signal.SIG_IGN)
            stop_owned(process)
            if log.exists():
                descriptor, retained = tempfile.mkstemp(prefix="freeplane-interactive-html-", suffix=".log")
                os.close(descriptor)
                shutil.copyfile(log, retained)
                print(f"freeplane-interactive-html: Log: {retained}", file=sys.stderr)
            raise
        finally:
            stop_owned(process)
            stage.unlink(missing_ok=True)
            for signum, handler in handlers.items():
                signal.signal(signum, handler)


if __name__ == "__main__":
    main()
