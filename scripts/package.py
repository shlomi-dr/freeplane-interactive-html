#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Build the experimental manual-install ZIP without installing anything."""

from pathlib import Path
from zipfile import ZIP_STORED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist" / "freeplane-interactive-html-manual.zip"
FILES = {
    "scripts/init/interactive-html.groovy": "src/init.groovy",
    "addons/interactive-html/resources/InteractiveHtmlAddon.groovy": "src/InteractiveHtmlAddon.groovy",
    "addons/interactive-html/resources/viewer-template.html": "src/viewer-template.html",
    "addons/interactive-html/README.md": "README.md",
    "addons/interactive-html/LICENSE": "LICENSE",
    "addons/interactive-html/NOTICE": "NOTICE",
}


def main():
    payloads = {}
    for destination, source in sorted(FILES.items()):
        path = ROOT / source
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Expected a regular source file: {source}")
        payloads[destination] = path.read_bytes()
    OUTPUT.parent.mkdir(exist_ok=True)
    with ZipFile(OUTPUT, "w", compression=ZIP_STORED) as archive:
        for destination, payload in payloads.items():
            entry = ZipInfo(destination, date_time=(1980, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            entry.compress_type = ZIP_STORED
            archive.writestr(entry, payload)
    with ZipFile(OUTPUT) as archive:
        if archive.namelist() != list(payloads) or archive.testzip() is not None:
            raise RuntimeError("Archive integrity or layout check failed")
        for destination, payload in payloads.items():
            if archive.read(destination) != payload:
                raise RuntimeError(f"Archive content mismatch: {destination}")
    print(f"Built dist/{OUTPUT.name} ({len(payloads)} files)")


if __name__ == "__main__":
    main()
