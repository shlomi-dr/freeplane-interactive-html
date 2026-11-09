#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Build the companion CLI ZIP and macOS app ZIP from an explicit allowlist."""

from pathlib import Path
import plistlib
import shutil
import stat
import subprocess
import sys
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
VERSION = "0.2.0-alpha.1"
CLI_ZIP = DIST / "freeplane-interactive-html-companion.zip"
MAC_ZIP = DIST / "freeplane-interactive-html-macos.zip"
CLI_FILES = (
    "bin/export-map.sh",
    "src/InteractiveHtmlAddon.groovy",
    "src/companion-export.groovy",
    "src/viewer-template.html",
    "README.md",
    "LICENSE",
    "NOTICE",
    "docs/VALIDATION.md",
    "examples/Clockwork Garden Festival.mm",
    "examples/preview.jpg",
)
APP_FILES = (
    "bin/export-map.sh",
    "src/InteractiveHtmlAddon.groovy",
    "src/companion-export.groovy",
    "src/viewer-template.html",
    "LICENSE",
    "NOTICE",
    "examples/Clockwork Garden Festival.mm",
)
EPOCH = (1980, 1, 1, 0, 0, 0)


def checked_source(relative):
    path = ROOT / relative
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Required regular source file is missing: {relative}")
    return path


def zip_tree(output, root, files):
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for relative in sorted(files):
            path = checked_source(relative) if root == ROOT else root / relative
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"Required regular package file is missing: {relative}")
            entry = ZipInfo(relative, date_time=EPOCH)
            entry.create_system = 3
            mode = (0o755 if relative == "bin/export-map.sh" else 0o644) if root == ROOT else stat.S_IMODE(path.stat().st_mode)
            entry.external_attr = (stat.S_IFREG | mode) << 16
            entry.compress_type = ZIP_DEFLATED
            archive.writestr(entry, path.read_bytes())
    with ZipFile(output) as archive:
        names = archive.namelist()
        if names != sorted(files) or archive.testzip() is not None:
            raise RuntimeError(f"Archive integrity/layout check failed: {output.name}")
        for relative in files:
            mode = archive.getinfo(relative).external_attr >> 16 & 0o777
            expected_mode = (0o755 if relative == "bin/export-map.sh" else 0o644) if root == ROOT else stat.S_IMODE((root / relative).stat().st_mode)
            if mode != expected_mode:
                raise RuntimeError(f"Archive permissions are wrong: {relative}")


def build_cli_zip():
    zip_tree(CLI_ZIP, ROOT, CLI_FILES)
    print(f"Built {CLI_ZIP.relative_to(ROOT)} ({len(CLI_FILES)} allowlisted files)")


def build_mac_app():
    if sys.platform != "darwin":
        raise RuntimeError("Building the macOS companion requires macOS and /usr/bin/osacompile")
    osacompile = Path("/usr/bin/osacompile")
    ditto = Path("/usr/bin/ditto")
    if not osacompile.is_file() or not ditto.is_file():
        raise RuntimeError("macOS packaging tools are missing (expected osacompile and ditto)")
    with tempfile.TemporaryDirectory(prefix="freeplane-html-package-") as temporary:
        work = Path(temporary)
        bundle = work / "Freeplane Interactive HTML.app"
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".applescript", delete=False) as script:
            script.write((ROOT / "packaging/Companion.applescript").read_text(encoding="utf-8"))
            source = Path(script.name)
        try:
            subprocess.run([str(osacompile), "-o", str(bundle), str(source)], check=True)
        finally:
            source.unlink(missing_ok=True)
        contents = bundle / "Contents"
        resources = contents / "Resources"
        resources.mkdir(parents=True, exist_ok=True)
        for relative in APP_FILES:
            destination = resources / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(checked_source(relative), destination)
            destination.chmod(0o755 if relative == "bin/export-map.sh" else 0o644)
        plist_path = contents / "Info.plist"
        plist = plistlib.loads(plist_path.read_bytes())
        plist_template = (ROOT / "packaging/Info.plist").read_text(encoding="utf-8")
        plist.update(plistlib.loads(plist_template.replace("@VERSION@", VERSION.split("-")[0]).encode()))
        plist["InteractiveHtmlVersion"] = VERSION
        plist_path.write_bytes(plistlib.dumps(plist))
        shutil.copyfile(ROOT / "examples/preview.jpg", resources / "preview.jpg")
        # osacompile signs its initial app. Seal again after adding resources and
        # metadata; this is local ad-hoc signing, not Developer ID notarization.
        subprocess.run(["/usr/bin/codesign", "--force", "--sign", "-", str(bundle)], check=True)
        subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(bundle)], check=True)
        app_zip_root = work / "ziproot"
        app_zip_root.mkdir()
        app_path = app_zip_root / bundle.name
        subprocess.run([str(ditto), str(bundle), str(app_path)], check=True)
        files = [p.relative_to(app_zip_root).as_posix() for p in app_path.rglob("*") if p.is_file()]
        files.extend(["README.md", "LICENSE", "NOTICE", "docs/VALIDATION.md", "examples/preview.jpg"])
        for name in ("README.md", "LICENSE", "NOTICE", "docs/VALIDATION.md", "examples/preview.jpg"):
            (app_zip_root / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, app_zip_root / name)
        (app_zip_root / "examples").mkdir(exist_ok=True)
        sample = app_zip_root / "examples/Clockwork Garden Festival.mm"
        shutil.copyfile(ROOT / "examples/Clockwork Garden Festival.mm", sample)
        files.append("examples/Clockwork Garden Festival.mm")
        zip_tree(MAC_ZIP, app_zip_root, files)
    print(f"Built {MAC_ZIP.relative_to(ROOT)} (app bundle and sample map)")


def main():
    build_cli_zip()
    build_mac_app()


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"package.py: {error}", file=sys.stderr)
        raise SystemExit(1)
