#!/bin/bash
# THE BOOT HOOK for the eCW session (PUL-217).
#
# The session guard runs on a clock (05:45 ET weekdays). That leaves a hole: a pod or
# browser that comes back at 9pm has no eCW session until the next morning, and the
# first job that needs the application pays for it with a sign-in attempt on a live
# clinical account.
#
# There is no boot event to hang a script on -- Hermes' shell hooks are tool-call
# events, and the init container finishes before the browser is reachable -- so this
# runs on a short cron and decides for itself whether this is a new start. Almost
# every run is two cheap reads and an exit with no output.
#
# WHAT COUNTS AS A NEW START, and why both halves are needed:
#   the pod    -- PID 1's own start time (node boot time plus its start ticks). A new
#                 pod, or a restarted hermes container, changes it.
#   the browser -- the UUID in the sidecar's CDP address. Chromium hands out a new one
#                 every time it starts, and the eCW session lives in THAT process: on
#                 2026-09-14 the sidecar alone exited and took the session with it
#                 while the pod stayed up, so the pod's own clock cannot see it.
#
# THE MARKER IS WRITTEN BEFORE THE GUARD RUNS, on purpose. One restart buys exactly
# one guard run. A guard run that fails must not be retried every few minutes: that is
# how an account gets locked. The 05:45 job and a person are the backstop.
set -u

STATE_DIR="${ECW_STATE_DIR:-/opt/data/state/ecw}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GUARD="${ECW_GUARD:-$SCRIPT_DIR/ecw_guard.sh}"
MARKER="$STATE_DIR/boot.id"
LOG="$STATE_DIR/boot-guard.log"
CDP="${BROWSER_CDP_URL:-http://127.0.0.1:9222}"

mkdir -p "$STATE_DIR" || exit 0

btime=$(awk '/^btime/{print $2}' /proc/stat 2>/dev/null)
ticks=$(awk '{print $22}' /proc/1/stat 2>/dev/null)
hz=$(getconf CLK_TCK 2>/dev/null || echo 100)
[ -n "${btime:-}" ] && [ -n "${ticks:-}" ] || exit 0
started=$(( btime + ticks / hz ))

# One HTTP read, no page, no navigation: this must never disturb work in flight.
browser=$(curl -fsS --max-time 5 "$CDP/json/version" 2>/dev/null \
          | sed -n 's|.*devtools/browser/\([0-9a-fA-F-]\{8,\}\)".*|\1|p')
# No browser yet is not a new start -- it is a pod still coming up. Say nothing and
# let the next tick decide, so the guard never runs at a Chromium that is not there.
[ -n "$browser" ] || exit 0

id="pod:$started browser:$browser"
[ -f "$MARKER" ] && [ "$(cat "$MARKER" 2>/dev/null)" = "$id" ] && exit 0

# A marker that cannot be written would make every tick look like a new start, and run the
# guard every five minutes. Say nothing and do nothing instead.
printf '%s' "$id" > "$MARKER" 2>/dev/null || exit 0
{
  echo "=== $(date -u +%FT%TZ) first look at a new start -- $id"
  "$GUARD" 2>&1
  echo "=== $(date -u +%FT%TZ) done"
} >> "$LOG" 2>&1

echo "eCW boot guard: a new start ($id). What it did:"
sed -n '/^=== .* first look at a new start -- '"$id"'$/,$p' "$LOG" | tail -n 25
