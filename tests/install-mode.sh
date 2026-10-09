#!/usr/bin/env bash
# Checks how install-toolchain.sh picks full or no-xcode: flag, environment, saved choice, default, bad value.
# It runs only the mode block of the installer (no install steps, no sudo). The prompt needs a terminal and is
# checked by hand: `./install-toolchain.sh --mode-help` prints its text.
set -euo pipefail
here=$(dirname "$(readlink -f "$0")")
script=$here/../install-toolchain.sh
block=$(mktemp)
sed -n '/^# Install mode:/,/^if \[ "\${1:-}" = "--mode-help" \]/p' "$script" | sed '$d' >"$block"
fail=0
# check NAME WANT SAVED ENVVAR ARGS...: WANT is the mode, or "error" for a refused value
check() {
  local name=$1 want=$2 saved_before=$3 envvar=$4
  shift 4
  local home got saved
  home=$(mktemp -d)
  if [ -n "$saved_before" ]; then
    mkdir -p "$home/.config/omarchy-apple-dev"
    printf '%s\n' "$saved_before" >"$home/.config/omarchy-apple-dev/mode"
  fi
  got=$(env -u OMARCHY_APPLE_MODE ${envvar:+OMARCHY_APPLE_MODE="$envvar"} HOME="$home" bash -c '
    set -euo pipefail
    block=$1; shift
    source "$block" "$@"
    resolve_mode >/dev/null
    echo "$MODE rest=${mode_args[*]-}"' _ "$block" "$@" 2>&1 </dev/null || true)
  saved=$(cat "$home/.config/omarchy-apple-dev/mode" 2>/dev/null || echo none)
  if [ "$want" = error ]; then
    case "$got" in "Unknown mode"*) echo "ok   $name -> refused"; return ;; esac
  elif [ "${got%% *}" = "$want" ] && [ "$saved" = "$want" ]; then
    echo "ok   $name -> $got (saved: $saved)"; return
  fi
  echo "FAIL $name: wanted $want, got '$got', saved '$saved'"
  fail=1
}
check "no input, no terminal: full" full "" ""
check "--mode no-xcode" no-xcode "" "" --mode no-xcode
check "--mode=no-xcode keeps other arguments" no-xcode "" "" --mode=no-xcode --user-only
check "environment" no-xcode "" no-xcode
check "saved choice is reused" no-xcode no-xcode ""
check "flag beats the saved choice" full no-xcode "" --mode full
check "flag beats the environment" full "" no-xcode --mode full
check "bad value is refused" error "" "" --mode bananas
rm -f "$block"
exit $fail
