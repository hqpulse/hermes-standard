#!/bin/bash
# eCW session guard. Runs with no model. Put the saved session back first; only spend a password
# if that session is dead. Widen the browser window first: eCW's login page refuses to advance
# below its own resolution floor, and the sidecar's Chromium reported 0 x 0 to an adopted page
# (PUL-217).
#
# Called on a clock (05:45 ET weekdays) and by ecw_boot_guard.sh after a pod or browser restart.
set -u

for f in "${ECW_LANE_ENV:-}" /etc/hermes/lane/lane.env /etc/ista-andrew/lane.env; do
  [ -n "$f" ] && [ -f "$f" ] && { set -a; . "$f"; set +a; break; }
done
# PVC raised the budget from 2 to 6 on 2026-09-15 having accepted the lockout risk; a lane
# that wants a different number sets ECW_ATTEMPT_BUDGET in its own lane file.
: "${ECW_ATTEMPT_BUDGET:=6}"
export ECW_ATTEMPT_BUDGET
export PYTHONPATH="${PYTHONPATH:-/opt/vendor/site-packages}"

E="${ECW_BIN:-/opt/data/profiles/hermes-standard/skills/ecw/scripts/ecw}"
L="${ECW_BROWSER_LOCK:-/opt/data/workspace/scribe/state/.browser-lock}"

# WHERE, READ PROPERLY. `ecw where` prints what the ADDRESS means and returns 0 only when the
# application is really on the screen: a shell whose session has gone sits on the in-the-app
# address and answers with the login form, so the word alone says "in-the-app" on a dead
# session. Reading the word and ignoring the exit code is how this guard would skip the restore
# AND then save the dead jar over the good one (PUL-217, 2026-09-15).
where_now() {
  local out rc word
  out=$("$E" where 2>&1); rc=$?
  word=$(printf '%s\n' "$out" | head -1)
  printf '%s\n' "$out" | head -3 | sed 's/^/  where: /' >&2
  if [ "$rc" -eq 0 ] && [ "$word" = "in-the-app" ]; then echo "in-the-app"
  elif [ "$word" = "in-the-app" ]; then echo "in-the-app-address-but-not-working"
  else echo "$word"; fi
}

waited=0
while [ "$waited" -lt 30 ] && [ -f "$L" ] && [ $(( $(date +%s) - $(stat -c %Y "$L") )) -lt 3600 ]; do
  [ "$waited" -eq 0 ] && echo "another job holds the browser lock; waiting up to 10 minutes"
  waited=$(( waited + 1 )); sleep 20
done
[ "$waited" -gt 0 ] && echo "waited $(( waited * 20 ))s for the browser lock"
echo "ecw-guard $(date -u +%FT%TZ)" > "$L"

# WIDEN THE ECW WINDOW, not whatever page happens to be first. Every target on this Chromium
# has its own window id, and the shared browser also holds PointClickCare pages opened at
# 950 x 600; resizing one of those does nothing for eCW and reads in the log as if it had
# worked. Measured 2026-09-15 (PUL-217).
/opt/hermes/.venv/bin/python3 - "${ECW_WEB_BASE:-}" <<'PY'
import sys, urllib.parse
from playwright.sync_api import sync_playwright
host = urllib.parse.urlsplit(sys.argv[1]).netloc if len(sys.argv) > 1 else ""
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = b.contexts[0]
    pages = [pg for pg in ctx.pages if host and host in pg.url]
    if not pages:
        # Nothing on the practice site yet. A page the skill opens next inherits the
        # browser's launch size (--window-size=1920,1200), so there is nothing to fix.
        print("window: no eCW page open yet; nothing to widen")
        raise SystemExit(0)
    pg = pages[0]
    s = ctx.new_cdp_session(pg)
    wid = s.send("Browser.getWindowForTarget")["windowId"]
    s.send("Browser.setWindowBounds", {"windowId": wid, "bounds": {"left": 0, "top": 0,
                                       "width": 1920, "height": 1200, "windowState": "normal"}})
    print("window:", pg.evaluate("[window.innerWidth, window.innerHeight]"))
PY

W=$(where_now)
echo "where before: $W"
if [ "$W" != "in-the-app" ]; then
  echo "putting the saved session back"
  "$E" session restore 2>&1 | grep -vE "^\s+(at |File )" | tail -3
  W=$(where_now); echo "where after restore: $W"
fi
if [ "$W" != "in-the-app" ]; then
  echo "the saved session is gone; signing in"
  timeout 420 "$E" signin 2>&1 | grep -vE "^\s+(at |File |\^|~)" | tail -6
  W=$(where_now); echo "where after signin: $W"
fi
if [ "$W" = "in-the-app" ]; then "$E" session save 2>&1 | tail -1; else echo "STILL SIGNED OUT: a person is needed"; fi
# A person running this by hand through kubectl exec is root, and the save above then leaves a
# root-only session file the scheduled run (uid 10000) cannot read: its restore fails and it
# spends a password on a session that was fine. Hand the files back to the directory's owner.
STATE_DIR="${ECW_STATE_DIR:-/opt/data/state/ecw}"
[ "$(id -u)" -eq 0 ] && [ -d "$STATE_DIR" ] && chown -R --reference="$STATE_DIR/.." "$STATE_DIR" 2>/dev/null
rm -f "$L"
