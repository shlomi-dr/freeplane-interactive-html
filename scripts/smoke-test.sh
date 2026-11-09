#!/bin/sh
# Requires a graphical desktop, a Freeplane distribution and a JDK 21 or later.
set -eu

mode=smoke
case "${1-}" in
  --demo) mode=demo; shift ;;
  --help|-h)
    printf '%s\n' 'Usage: FREEPLANE_HOME=/path/to/distribution JAVA_HOME=/path/to/jdk scripts/smoke-test.sh [--demo]'
    exit 0 ;;
esac
if [ "$#" -ne 0 ]; then
  printf '%s\n' 'Only --demo is supported.' >&2
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
cp "$repo/src/InteractiveHtmlAddon.groovy" "$repo/src/viewer-template.html" "$repo/src/init.groovy" "$base/"
cp "$repo/examples/Clockwork Garden Festival.mm" "$base/"
cp "$repo/tests/Probe.java" "$repo/tests/prepare.groovy" "$repo/tests/exercise.groovy" "$repo/tests/export-demo.groovy" "$base/"
compile_cp="$app/plugins/org.freeplane.plugin.script/lib/*:$app/core/org.freeplane.core/lib/*:$app/framework.jar:$app/freeplanelauncher.jar"
if ! "$jdk/bin/java" -cp "$compile_cp" org.codehaus.groovy.tools.FileSystemCompiler -d "$base/classes" \
  "$base/InteractiveHtmlAddon.groovy" "$base/init.groovy" "$base/prepare.groovy" "$base/exercise.groovy" "$base/export-demo.groovy" >"$base/compile.log" 2>&1; then
  cat "$base/compile.log" >&2
  exit 1
fi
if ! "$jdk/bin/javac" -Xlint:deprecation -d "$base/classes" \
  -cp "$app/freeplanelauncher.jar:$app/framework.jar:$app/core/org.freeplane.core/lib/freeplaneapi_viewer.jar" \
  "$base/Probe.java" >>"$base/compile.log" 2>&1; then
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
if "$jdk/bin/java" "$@" -Duser.home="$base/home" -Djava.io.tmpdir="$base/tmp" \
  -cp "$base/classes:$app/freeplanelauncher.jar:$app/framework.jar:$app/core/org.freeplane.core/lib/freeplaneapi_viewer.jar" \
  Probe "$base" "$app" "$mode" >"$base/probe-run.log" 2>&1; then
  cat "$base/probe-run.log"
else
  status=$?
  cat "$base/probe-run.log" >&2
  exit "$status"
fi
