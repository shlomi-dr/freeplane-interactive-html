#!/bin/sh
# Requires a graphical desktop, a Freeplane distribution and a JDK 21 or later.
# LEGACY_ZIP can point to the published alpha.1 manual ZIP for real migration coverage.
# Without it, the current six-file payload simulates the manual installation layout.
set -eu

if [ "$#" -ne 0 ]; then
  printf '%s\n' 'Usage: FREEPLANE_HOME=/path/to/distribution JAVA_HOME=/path/to/jdk scripts/install-test.sh' >&2
  exit 2
fi
: "${FREEPLANE_HOME:?Set FREEPLANE_HOME to the distribution folder containing freeplanelauncher.jar}"
: "${JAVA_HOME:?Set JAVA_HOME to a JDK 21 or later}"
app=$(CDPATH= cd -- "$FREEPLANE_HOME" && pwd)
jdk=$(CDPATH= cd -- "$JAVA_HOME" && pwd)
repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
for file in "$app/freeplanelauncher.jar" "$app/framework.jar" "$jdk/bin/java" "$jdk/bin/javac"; do
  if [ ! -f "$file" ]; then
    printf 'Missing required file: %s\n' "$file" >&2
    exit 2
  fi
done
version=$("$jdk/bin/java" -XshowSettings:properties -version 2>&1 | sed -n 's/^[[:space:]]*java.specification.version = //p')
case "$version" in
  ''|*[!0-9]*) printf 'Cannot determine JDK version: %s\n' "$version" >&2; exit 2 ;;
esac
if [ "$version" -lt 21 ]; then
  printf 'JDK 21 or later required; found %s\n' "$version" >&2
  exit 2
fi
base=$(mktemp -d "${TMPDIR:-/tmp}/freeplane-interactive-html.XXXXXX")
printf 'Artifacts retained at: %s\n' "$base"
trap 'printf "Artifacts retained at: %s\n" "$base"' EXIT
mkdir -p "$base/classes" "$base/home" "$base/tmp"
cp "$repo/examples/Clockwork Garden Festival.mm" "$base/"
cp "$repo/tests/InstallProbe.java" "$repo/tests/install-addon.groovy" "$repo/tests/export-demo.groovy" "$base/"
cp "$repo/dist/freeplane-interactive-html.addon.mm" "$base/current.addon.mm"
python3 - "$base" <<'PYTHON'
import base64
import sys
import xml.etree.ElementTree as ET
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
base = Path(sys.argv[1])
tree = ET.parse(base / 'current.addon.mm')
root = tree.getroot().find('node')
version = next(a for a in root.findall('attribute') if a.get('NAME') == 'version')
(base / 'version.txt').write_text(version.get('VALUE'))
zips = next(n for n in root.findall('node') if n.get('TEXT') == 'zips')
payload = zips.find('node/node')
encoded = payload.get('TEXT')
with ZipFile(BytesIO(base64.b64decode(encoded))) as archive:
    paths = archive.namelist()
    assert len(paths) == 6 and all(not p.startswith('/') and '..' not in p.split('/') for p in paths)
    archive.extractall(base / 'expected')
(base / 'payload-paths.txt').write_text('\n'.join(paths) + '\n')
# A distinct prior native payload makes the update prove resource replacement.
previous = BytesIO()
with ZipFile(BytesIO(base64.b64decode(encoded))) as current, ZipFile(previous, 'w') as archive:
    for path in paths:
        content = current.read(path)
        if path == 'addons/interactive-html/resources/InteractiveHtmlAddon.groovy':
            content += b'\n// prior native installer fixture\n'
        archive.writestr(path, content)
with ZipFile(BytesIO(previous.getvalue())) as archive:
    archive.extractall(base / 'previous-expected')
payload.set('TEXT', base64.b64encode(previous.getvalue()).decode('ascii'))
version.set('VALUE', '0.1.0-alpha.1')
tree.write(base / 'previous.addon.mm', encoding='utf-8', xml_declaration=False)
PYTHON
if ! "$jdk/bin/javac" -Xlint:deprecation -d "$base/classes" \
  -cp "$app/freeplanelauncher.jar:$app/framework.jar:$app/core/org.freeplane.core/lib/freeplaneapi_viewer.jar" \
  "$base/InstallProbe.java" >"$base/compile.log" 2>&1; then
  cat "$base/compile.log" >&2
  exit 1
fi
set -- -Djava.security.manager=allow --add-exports=java.desktop/sun.awt=ALL-UNNAMED \
  --add-exports=java.desktop/sun.swing=ALL-UNNAMED --add-opens=java.desktop/javax.swing.text.html=ALL-UNNAMED
if [ "$(uname -s)" = Darwin ]; then
  set -- "$@" -XX:-IgnoreUnrecognizedVMOptions -XX:MaxRAM=20g -XX:MaxRAMPercentage=15.0 \
    -Dapple.laf.useScreenMenuBar=false -Xdock:name=Freeplane \
    --add-exports=java.desktop/com.apple.eawt=ALL-UNNAMED \
    --add-exports=java.desktop/com.apple.eawt.event=ALL-UNNAMED \
    --add-exports=java.desktop/com.apple.laf=ALL-UNNAMED
fi
run_phase() {
  package=${package-current.addon.mm}
  log="$base/$scenario-$phase-$expected.log"
  if "$jdk/bin/java" "$@" -Duser.home="$base/home" -Djava.io.tmpdir="$base/tmp" \
    -cp "$base/classes:$app/freeplanelauncher.jar:$app/framework.jar:$app/core/org.freeplane.core/lib/freeplaneapi_viewer.jar" \
    InstallProbe "$base" "$app" "$phase" "$expected" "$package" >"$log" 2>&1; then
    cat "$log"
  else
    status=$?
    cat "$log" >&2
    exit "$status"
  fi
}
# Keep VM options in positional parameters; each phase starts a separate JVM.
version=$(cat "$base/version.txt")
scenario=fresh
phase=install expected=0.1.0-alpha.1 package=previous.addon.mm run_phase "$@"
phase=verify expected=0.1.0-alpha.1 run_phase "$@"
phase=install expected="$version" package=current.addon.mm run_phase "$@"
phase=verify expected="$version" run_phase "$@"
# An unrelated file within the private addon folder must survive native removal.
for profile in "$base"/config/*; do
  mkdir -p "$profile/addons/interactive-html"
  printf '%s\n' 'preserve private sentinel' > "$profile/addons/interactive-html/unrelated.txt"
done
phase=uninstall expected="$version" run_phase "$@"
phase=absent expected="$version" run_phase "$@"
mv "$base/config" "$base/fresh-config"
scenario=migration
if [ -n "${LEGACY_ZIP-}" ]; then
  python3 - "$LEGACY_ZIP" "$base/legacy" <<'PYTHON'
import sys
from zipfile import ZipFile
with ZipFile(sys.argv[1]) as archive:
    assert all(not p.startswith("/") and ".." not in p.split("/") for p in archive.namelist())
    archive.extractall(sys.argv[2])
PYTHON
else
  cp -R "$base/expected" "$base/legacy"
fi
for profile in 1.12.x 1.13.x; do
  mkdir -p "$base/config/$profile"
  cp -R "$base/legacy/." "$base/config/$profile/"
done
phase=manual expected="$version" run_phase "$@"
phase=install expected="$version" package=current.addon.mm run_phase "$@"
phase=verify expected="$version" run_phase "$@"
for profile in "$base"/config/*; do
  printf '%s\n' 'preserve private sentinel' > "$profile/addons/interactive-html/unrelated.txt"
done
phase=uninstall expected="$version" run_phase "$@"
phase=absent expected="$version" run_phase "$@"
printf '%s\n' 'INSTALL_LIFECYCLE_OK fresh update migration uninstall restarts'
