#!/bin/bash
# eCW session guard. Runs with no model. Put the saved session back first; only spend a password
# if that session is dead. Widen the browser window first: eCW's login page refuses to advance
# below its own resolution floor, and the sidecar's Chromium reported 0 x 0 to an adopted page
# (PUL-217).
#
# Called on a clock (05:45 ET weekdays) and by ecw_boot_guard.sh after a pod or browser restart.
set -u

# THE WINDOW THIS GUARD ASKS FOR. Well over the login page's 1600 x 900 floor and over the
# 1600 x 1000 the scribe's own adapter holds a page at, so nothing this guard does ever makes
# a page smaller than a client that comes after it wants. Measured 2026-09-15: the sign-in
# that failed at 1600 x 1000 on a stale page went through first try on a fresh page at this size.
WIN_W=2200
WIN_H=1400

for f in "${ECW_LANE_ENV:-}" /etc/hermes/lane/lane.env /etc/ista-andrew/lane.env; do
  [ -n "$f" ] && [ -f "$f" ] && { set -a; . "$f"; set +a; break; }
done
STATE_DIR="${ECW_STATE_DIR:-/opt/data/state/ecw}"
# THE SIGN-IN BUDGET IS THE SEAT'S, never this file's. The skill's default is 2. A seat whose
# owners have accepted more lockout risk writes the number into attempt-budget in its own state
# folder (PVC: 6, Eli, 2026-09-15). A default here would hand that risk to every seat that
# registers this job.
if [ -z "${ECW_ATTEMPT_BUDGET:-}" ] && [ -f "$STATE_DIR/attempt-budget" ]; then
  ECW_ATTEMPT_BUDGET=$(tr -dc '0-9' < "$STATE_DIR/attempt-budget")
fi
[ -n "${ECW_ATTEMPT_BUDGET:-}" ] && export ECW_ATTEMPT_BUDGET
export PYTHONPATH="${PYTHONPATH:-/opt/vendor/site-packages}"

# ONE GUARD AT A TIME. The 05:45 job and the boot job can fire on the same tick, and two
# guards facing one dead session would each spend a password. The second waits here, and
# by the time it goes on the first has restored or signed in, so it finds the app working.
mkdir -p "$STATE_DIR"
[ -e "$STATE_DIR/guard.lock" ] || { : > "$STATE_DIR/guard.lock"; chmod 666 "$STATE_DIR/guard.lock"; } 2>/dev/null
if exec 9>>"$STATE_DIR/guard.lock"; then
  flock -w 900 9 || { echo "another eCW guard has run for 15 minutes; leaving it to that one"; exit 0; }
else
  echo "could not open the guard lock; going on without it"
fi

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
# `|| echo 0`: a lock that vanishes between the test and the stat is simply gone. Without it the
# arithmetic is empty and bash exits here, before any restore.
while [ "$waited" -lt 30 ] && [ -f "$L" ] && [ $(( $(date +%s) - $(stat -c %Y "$L" 2>/dev/null || echo 0) )) -lt 3600 ]; do
  [ "$waited" -eq 0 ] && echo "another job holds the browser lock; waiting up to 10 minutes"
  waited=$(( waited + 1 )); sleep 20
done
[ "$waited" -gt 0 ] && echo "waited $(( waited * 20 ))s for the browser lock"
echo "ecw-guard $(date -u +%FT%TZ)" > "$L"
# A guard killed mid-run (the sign-in has a 7-minute timeout) must not leave the browser locked.
trap 'rm -f "$L"' EXIT

# WIDEN THE ECW WINDOW, not whatever page happens to be first. Every target on this Chromium
# has its own window id, and the shared browser also holds PointClickCare pages opened at
# 950 x 600; resizing one of those does nothing for eCW and reads in the log as if it had
# worked. Measured 2026-09-15 (PUL-217).
#
# Called AFTER the restore as well as before it. On a cold start there is no eCW page until the
# restore opens one, so a widen that only runs first widens nothing (17:45Z, 15 Sep). And it
# reports the page's own size next to the window's, because they can differ on purpose: the
# scribe's eCW adapter holds the page at 1600 x 1000 with a viewport setting for as long as its
# client is attached, and no window size overrides that. Above the floor is all this needs.
widen() {
  "${ECW_PYTHON:-/opt/hermes/.venv/bin/python3}" - "${ECW_WEB_BASE:-}" "$1" "$WIN_W" "$WIN_H" <<'PY'
import sys, urllib.parse
from playwright.sync_api import sync_playwright
host = urllib.parse.urlsplit(sys.argv[1]).netloc if len(sys.argv) > 1 else ""
when = sys.argv[2] if len(sys.argv) > 2 else ""
WIN = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (2200, 1400)
FLOOR = (1600, 900)   # the login page's own resolution floor
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = b.contexts[0]
    pages = [pg for pg in ctx.pages if host and host in pg.url]
    if not pages:
        print(f"window ({when}): no eCW page open yet")
        raise SystemExit(0)
    pg = pages[0]
    s = ctx.new_cdp_session(pg)
    wid = s.send("Browser.getWindowForTarget")["windowId"]
    s.send("Browser.setWindowBounds", {"windowId": wid, "bounds": {"left": 0, "top": 0,
                                       "width": WIN[0], "height": WIN[1], "windowState": "normal"}})
    bounds = s.send("Browser.getWindowBounds", {"windowId": wid})["bounds"]
    w, h = pg.evaluate("[window.innerWidth, window.innerHeight]")
    note = "at or over the floor" if w >= FLOOR[0] and h >= FLOOR[1] else "UNDER the login page's floor"
    held = "" if w >= bounds["width"] - 40 else "; the page is held smaller by a viewport setting from another client"
    print(f"window ({when}): {bounds['width']}x{bounds['height']}, page {w}x{h}, {note}{held}")
PY
}

# A STALE eCW PAGE IS THE THING THAT ACTUALLY BREAKS A SIGN-IN. The login page keeps its own
# state, and a page left sitting on it reports a screen of 800 x 600 whatever the window says,
# never advances past screen one, and reads back as "the username was not recognized". Widening
# the window around it does not help: this morning's 05:46 run (2026-09-15) widened, restored,
# signed in at 1600 x 1000 on the old page and was STILL SIGNED OUT. The same credential signed
# in first try once the old pages were closed and a fresh one opened (06:03 ET, by hand). So when
# the session is not working: close every page on the practice host, open one fresh page, drop
# any page-size override a previous client left on it, size the window, and land on the login
# page. The restore and the sign-in then run on that clean page.
#
# Only when the session is NOT working. A working session is left exactly as it is: closing its
# pages and putting the saved file back over live cookies could turn a good session into a dead
# one and then spend a password on it.
fresh_page() {
  "${ECW_PYTHON:-/opt/hermes/.venv/bin/python3}" - "${ECW_WEB_BASE:-}" "fresh page" "$WIN_W" "$WIN_H" <<'PY'
import sys, urllib.parse
from playwright.sync_api import sync_playwright
base = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else ""
host = urllib.parse.urlsplit(base).netloc
WIN = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (2200, 1400)
LOGIN = "/mobiledoc/jsp/webemr/login/newLogin.jsp"
if not host:
    print("fresh page: the lane names no practice site (ECW_WEB_BASE); leaving the pages as they are")
    raise SystemExit(0)
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = b.contexts[0]
    closed = 0
    for pg in list(ctx.pages):
        if urllib.parse.urlsplit(pg.url or "").netloc == host:
            try:
                pg.close(); closed += 1
            except Exception:
                pass
    pg = ctx.new_page()
    s = ctx.new_cdp_session(pg)
    try:
        s.send("Emulation.clearDeviceMetricsOverride")
    except Exception:
        pass
    wid = s.send("Browser.getWindowForTarget")["windowId"]
    s.send("Browser.setWindowBounds", {"windowId": wid, "bounds": {"left": 0, "top": 0,
                                       "width": WIN[0], "height": WIN[1], "windowState": "normal"}})
    pg.goto(base + LOGIN, wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(3000)
    w, h = pg.evaluate("[window.innerWidth, window.innerHeight]")
    print(f"fresh page: closed {closed} old page(s) on {host}, opened the login page, page {w}x{h}")
PY
}

widen "before restore"
W=$(where_now)
echo "where before: $W"
if [ "$W" != "in-the-app" ]; then
  fresh_page
  echo "putting the saved session back"
  "$E" session restore 2>&1 | grep -vE "^\s+(at |File )" | tail -3
  widen "after restore"
  W=$(where_now); echo "where after restore: $W"
fi
if [ "$W" != "in-the-app" ]; then
  echo "the saved session is gone; signing in"
  widen "before sign-in"
  timeout 420 "$E" signin 2>&1 | grep -vE "^\s+(at |File |\^|~)" | tail -6
  W=$(where_now); echo "where after signin: $W"
fi
if [ "$W" = "in-the-app" ]; then "$E" session save 2>&1 | tail -1; else echo "STILL SIGNED OUT: a person is needed"; fi
# A person running this by hand through kubectl exec is root, and the save above then leaves a
# root-only session file the scheduled run (uid 10000) cannot read: its restore fails and it
# spends a password on a session that was fine. Hand the files back to the directory's owner.
if [ "$(id -u)" -eq 0 ] && [ -d "$STATE_DIR" ]; then chown -R --reference="$STATE_DIR/.." "$STATE_DIR" 2>/dev/null; fi
exit 0
