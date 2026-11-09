#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Build deterministic native add-on and manual ZIP, without installing anything."""

import base64
from pathlib import Path
import xml.etree.ElementTree as ET
from zipfile import ZIP_STORED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist" / "freeplane-interactive-html-manual.zip"
ADDON = OUTPUT.with_name("freeplane-interactive-html.addon.mm")
VERSION = "0.1.0-alpha.2"
FILES = {
    "scripts/init/interactive-html.groovy": "src/init.groovy",
    "addons/interactive-html/resources/InteractiveHtmlAddon.groovy": "src/InteractiveHtmlAddon.groovy",
    "addons/interactive-html/resources/viewer-template.html": "src/viewer-template.html",
    "addons/interactive-html/README.md": "README.md",
    "addons/interactive-html/LICENSE": "LICENSE",
    "addons/interactive-html/NOTICE": "NOTICE",
}


def build_addon(zip_bytes):
    # Freeplane NodeProxy.getBinary decodes the node's plain text as Base64.
    # Keep <map> at byte zero for Freeplane's file-format detection.
    document = ET.Element("map", version="freeplane 1.12.1")
    root = ET.SubElement(document, "node", TEXT="Interactive HTML", ID="ID_INTERACTIVE_HTML",
                         LINK="https://github.com/shlomi-dr/freeplane-interactive-html")
    for name, value in {
        "name": "interactive-html", "version": VERSION, "author": "shlomi-dr",
        "freeplaneVersionFrom": "1.13.3", "freeplaneVersionTo": "1.13.3",
    }.items():
        ET.SubElement(root, "attribute", NAME=name, VALUE=value)
    description = ET.SubElement(root, "node", TEXT="description")
    ET.SubElement(description, "node", TEXT=(
        "Experimental whole-map Interactive HTML export: folding, search, pan and zoom. "
        "For Freeplane 1.13.3. Restart Freeplane after installation, update or removal. "
        "Replaces the six files from the earlier manual ZIP; preserve local edits first."))
    license_node = ET.SubElement(root, "node", TEXT="license")
    ET.SubElement(license_node, "node", TEXT=(ROOT / "LICENSE").read_text())
    translations = ET.SubElement(root, "node", TEXT="translations")
    english = ET.SubElement(translations, "node", TEXT="en")
    ET.SubElement(english, "attribute", NAME="addons.interactive-html", VALUE="Interactive HTML")
    for name in ("preferences.xml", "default.properties", "scripts"):
        ET.SubElement(root, "node", TEXT=name)
    zips = ET.SubElement(root, "node", TEXT="zips")
    payload = ET.SubElement(zips, "node", TEXT="interactive-html.zip")
    ET.SubElement(payload, "node", TEXT=base64.b64encode(zip_bytes).decode("ascii"))
    deinstall = ET.SubElement(root, "node", TEXT="deinstall")
    # Freeplane does not automatically delete its registration file. Use explicit
    # files only: deleting directories could affect user-added content.
    for path in (*sorted(FILES), "addons/interactive-html.script.xml"):
        ET.SubElement(deinstall, "attribute", NAME="delete", VALUE="${installationbase}/" + path)
    ET.indent(document, space="  ")
    data = ET.tostring(document, encoding="utf-8") + b"\n"
    parsed = ET.fromstring(data)
    encoded = parsed.find("./node/node[@TEXT='zips']/node/node").attrib["TEXT"]
    if base64.b64decode(encoded, validate=True) != zip_bytes:
        raise RuntimeError("Native add-on payload round-trip failed")
    ADDON.write_bytes(data)


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
    build_addon(OUTPUT.read_bytes())
    print(f"Built dist/{ADDON.name} (version {VERSION})")


if __name__ == "__main__":
    main()
