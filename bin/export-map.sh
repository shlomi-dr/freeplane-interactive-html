#!/bin/bash
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
Usage: export-map.sh INPUT.mm OUTPUT.html
Export a Freeplane mind map as interactive HTML using the installed Freeplane app.
Set FREEPLANE_HOME to the app's Contents/app directory to select another install.
EOF
}

fail() { printf 'export-map: %s\n' "$*" >&2; exit 2; }

[[ $# -eq 2 ]] || { usage; exit 2; }
input=$1
output=$2
[[ -f "$input" && -r "$input" ]] || fail "input must be an existing readable .mm file: $input"
[[ ${input##*.} == mm ]] || fail "input must have the .mm extension: $input"
input_dir=$(cd -- "$(dirname -- "$input")" 2>/dev/null && pwd -P) || fail "input directory is unavailable: $(dirname -- "$input")"
input="$input_dir/$(basename -- "$input")"
[[ ${output##*.} == html || ${output##*.} == htm ]] || fail "output must have the .html or .htm extension: $output"
[[ ! -d "$output" ]] || fail "output path is a directory: $output"
out_dir=$(cd -- "$(dirname -- "$output")" 2>/dev/null && pwd -P) || fail "output directory does not exist: $(dirname -- "$output")"
output="$out_dir/$(basename -- "$output")"
if [[ -e "$output" || -L "$output" ]]; then
  [[ ! "$input" -ef "$output" ]] || fail 'input and output refer to the same file'
fi

app=${FREEPLANE_HOME:-/Applications/Freeplane.app/Contents/app}
if [[ -d "$app/Contents/app" ]]; then app="$app/Contents/app"; fi
launcher="$app/freeplanelauncher.jar"
[[ -f "$launcher" ]] || fail "Freeplane launcher not found under: $app"
native_dir=$(cd -- "$app/../MacOS" && pwd -P) || fail "Freeplane application launcher not found under: $app/../MacOS"
app_launcher="$native_dir/Freeplane"
[[ -x "$app_launcher" ]] || fail "Freeplane application launcher not found under: $native_dir"

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../src" && pwd -P)
addon="$script_dir/InteractiveHtmlAddon.groovy"
template="$script_dir/viewer-template.html"
runner="$script_dir/companion-export.groovy"
[[ -r "$addon" && -r "$template" && -r "$runner" ]] || fail 'companion export resources are missing'

timeout_seconds=${FREEPLANE_EXPORT_TIMEOUT:-180}
[[ $timeout_seconds =~ ^[1-9][0-9]*$ ]] || fail 'FREEPLANE_EXPORT_TIMEOUT must be a positive integer'
[[ -x /usr/bin/perl ]] || fail 'Perl is required for the bounded Freeplane timeout'
work=$(mktemp -d "${TMPDIR:-/tmp}/freeplane-companion.XXXXXX") || fail 'could not create a temporary profile'
child=''
watchdog=''
stage=''
log="$work/freeplane.log"
marker="$work/export.ok"
retain_log() {
  [[ -f "$log" ]] || return 0
  local retained="${TMPDIR:-/tmp}/freeplane-export-$(date +%s)-$$.log"
  if cp "$log" "$retained" 2>/dev/null; then
    printf 'Freeplane log: %s\n' "$retained" >&2
  else
    tail -n 12 "$log" >&2 || true
  fi
}
stop_child() {
  if [[ -n "$child" ]] && kill -0 "$child" 2>/dev/null; then
    kill -TERM "$child" 2>/dev/null || true
    sleep 1
    kill -KILL "$child" 2>/dev/null || true
    wait "$child" 2>/dev/null || true
  fi
  child=''
}
cleanup() {
  stop_child
  if [[ -n "${watchdog:-}" ]]; then kill "$watchdog" 2>/dev/null || true; wait "$watchdog" 2>/dev/null || true; fi
  if [[ -n "${stage:-}" ]]; then rm -f -- "$stage"; fi
  rm -rf -- "$work"
}
terminate() {
  trap - INT TERM HUP
  stop_child
  printf 'export-map: interrupted; the owned Freeplane process was stopped.\n' >&2
  retain_log
  exit 130
}
timed_out() {
  trap - USR1
  printf 'export-map: Freeplane export exceeded its %s-second time limit.\n' "$timeout_seconds" >&2
  stop_child
  retain_log
  exit 124
}
trap cleanup EXIT
trap terminate INT TERM HUP
trap timed_out USR1

mkdir -p "$work/profile/1.12.x" "$work/profile/1.13.x"
for profile in "$work/profile/1.12.x" "$work/profile/1.13.x"; do
  cat >"$profile/auto.properties" <<'EOF'
single_instance=false
formula_disable_plugin=true
EOF
done

stage=$(mktemp "$out_dir/.freeplane-html-export.XXXXXX") || fail "could not create a staging file in: $out_dir"
set +e
env -u FREEPLANE_HOME COMPANION_ADDON="$addon" COMPANION_TEMPLATE="$template" \
  COMPANION_INPUT="$input" COMPANION_OUTPUT="$stage" COMPANION_MARKER="$marker" \
  "$app_launcher" \
  "-U$work/profile" -R"$runner" -S "$input" >"$log" 2>&1 &
child=$!
/usr/bin/perl -e 'sleep $ARGV[0]; kill "USR1", $ARGV[1]' "$timeout_seconds" "$$" &
watchdog=$!
wait "$child"
status=$?
child=''
kill "$watchdog" 2>/dev/null || true
wait "$watchdog" 2>/dev/null || true
watchdog=''
set -e

if [[ $status -ne 0 || ! -f "$marker" || ! -s "$stage" ]]; then
  printf 'export-map: Freeplane did not complete the export (exit %d).\n' "$status" >&2
  if [[ -f "$log" ]]; then
    if ! grep -E -i -m 1 'Exception|ERROR|Error|Unsupported captured|AssertionError|failed' "$log" >&2; then
      tail -n 12 "$log" >&2 || true
    fi
    retain_log
  fi
  exit 1
fi

if ! mv -f -- "$stage" "$output"; then
  fail "could not atomically move the completed export into place: $output"
fi
stage=''

printf '%s\n' "$output"
