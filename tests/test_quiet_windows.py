"""Quiet hours for everyone: the file, the gate, the mail watch, the command.

Run: python3 tests/test_quiet_windows.py

Every case is an hour a real person named and expects kept: evenings, a
weekend, two days off, an overnight window across midnight, and the clock
changing under it. The calendar cases stay in test_jewish_time.py; here only
the stated hours are exercised, alone and beside a calendar.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GATE = ROOT / "scripts" / "jewish_time.py"
KEEPER = ROOT / "scripts" / "quiet_windows.py"
DOOR = ROOT / "skills" / "quiet-windows" / "scripts" / "quiet-windows"
sys.path.insert(0, str(ROOT / "scripts"))

import quiet_windows as qw  # noqa: E402
import jewish_time as jt  # noqa: E402

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  ok   {name}")
    else:
        failures.append(f"{name}{': ' + detail if detail else ''}")
        print(f"  FAIL {name}{': ' + detail if detail else ''}")


def at(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp)


def run(script: Path, home: Path, stamp: str, *args: str) -> tuple[int, str, str]:
    env = dict(os.environ)
    env.update({"HERMES_HOME": str(home), "JEWISH_TIME_NOW": stamp})
    done = subprocess.run([sys.executable, str(script), *args], env=env,
                          capture_output=True, text=True, timeout=60)
    return done.returncode, done.stdout, done.stderr


def last_line(out: str) -> str:
    lines = [ln for ln in out.splitlines() if ln.strip()]
    return lines[-1].strip() if lines else ""


def main() -> int:
    tmp = Path(tempfile.mkdtemp())
    home = tmp / "profile"
    (home / "quiet").mkdir(parents=True)
    (home / "config.yaml").write_text("timezone: America/New_York\nmodel: x\n", encoding="utf-8")
    (home / "quiet" / "windows.json").write_text(json.dumps({
        "weekly": [{"days": ["sat", "sun"], "from": "00:00", "to": "24:00", "what": "weekend"},
                   {"days": "mon-fri", "from": "19:00", "to": "08:00", "what": "evenings"}],
        "dates": [{"from": "2026-11-26", "to": "2026-11-27", "what": "days off"}],
    }), encoding="utf-8")

    print("the file is read in the person's own clock")
    w = qw.load_windows(home)
    check("the clock comes from the assistant's config", w is not None and w.tz_name == "America/New_York")
    check("two weekly rows and one dates row", len(w.weekly) == 2 and len(w.dates) == 1)
    check("Tuesday 8pm New York is inside the evenings", (w.window_at(at("2026-09-15T20:00:00-04:00")) or {}).get("what") == "evenings")
    check("Wednesday 7:30am is still inside last night's window", (w.window_at(at("2026-09-16T07:30:00-04:00")) or {}).get("what") == "evenings")
    check("Wednesday 8am is out", w.window_at(at("2026-09-16T08:00:00-04:00")) is None)
    check("Wednesday noon is out", w.window_at(at("2026-09-16T12:00:00-04:00")) is None)
    check("Saturday noon is the weekend", (w.window_at(at("2026-09-19T12:00:00-04:00")) or {}).get("what") == "weekend")
    check("Friday 11:59pm is Friday evening, not yet the weekend", (w.window_at(at("2026-09-18T23:59:00-04:00")) or {}).get("what") == "evenings")
    check("Monday 6am is not the weekend (Sunday's row does not run into Monday)",
          (w.window_at(at("2026-09-21T06:00:00-04:00")) or {}).get("what") is None)
    check("the day off is a whole day", (w.window_at(at("2026-11-27T15:00:00-05:00")) or {}).get("what") == "days off")
    check("the day after the days off is open at noon", w.window_at(at("2026-11-28T12:00:00-05:00")) is None or
          w.window_at(at("2026-11-28T12:00:00-05:00"))["what"] == "weekend")
    nxt = w.next_window_after(at("2026-09-16T12:00:00-04:00"))
    check("the next window from Wednesday noon is Wednesday evening", nxt is not None and nxt["what"] == "evenings"
          and nxt["start"].isoformat().startswith("2026-09-16T19:00"))
    check("a moment given in UTC is read in the person's clock",
          (w.window_at(at("2026-09-16T00:30:00+00:00")) or {}).get("what") == "evenings")   # 8:30pm Tuesday New York

    print("the gate holds a scheduled job shut inside stated hours")
    rc, out, err = run(GATE, home, "2026-09-15T20:00:00-04:00")
    check("inside the evenings the gate answers wakeAgent false", rc == 0 and last_line(out) == jt.GATE_CLOSED, err[-200:])
    rc, out, err = run(GATE, home, "2026-09-16T12:00:00-04:00")
    check("at noon the gate opens", rc == 0 and last_line(out) == jt.GATE_OPEN, err[-200:])
    check("and the reading names the person's next quiet hours",
          "QUIET CALENDAR" in out and "next:" in out and "evenings" in out, out[:300])
    check("and it never names a religion for a person with none", "Shabbat" not in out and "yom tov" not in out.lower())
    rc, out, err = run(GATE, home, "2026-09-19T12:00:00-04:00")
    check("Saturday noon is held for a weekend window", last_line(out) == jt.GATE_CLOSED)

    print("the calendar and the stated hours hold together")
    cal_home = tmp / "both"
    (cal_home / "quiet").mkdir(parents=True)
    (cal_home / "jewish-time").mkdir(parents=True)
    (cal_home / "quiet" / "windows.json").write_text(json.dumps({
        "weekly": [{"days": "mon-fri", "from": "20:00", "to": "07:00", "what": "evenings"}]}), encoding="utf-8")
    (cal_home / "jewish-time" / "calendar.json").write_text(json.dumps({
        "version": 1, "tz": "America/New_York", "covers": {"from": "2026-09-01", "to": "2026-12-31"},
        "windows": [{"start": "2026-09-18T18:45:00-04:00", "end": "2026-09-19T19:50:00-04:00", "what": "Shabbat"}],
        "days": []}), encoding="utf-8")
    rc, out, err = run(GATE, cal_home, "2026-09-18T19:00:00-04:00")
    check("inside the calendar's window the gate is shut", last_line(out) == jt.GATE_CLOSED)
    rc, out, err = run(GATE, cal_home, "2026-09-16T21:00:00-04:00")
    check("inside the stated evening the gate is shut", last_line(out) == jt.GATE_CLOSED)
    rc, out, err = run(GATE, cal_home, "2026-09-16T12:00:00-04:00")
    check("at noon it is open and the reading carries both", last_line(out) == jt.GATE_OPEN
          and "Next quiet window" in out and "quiet hours" in out, out[:400])

    print("the mail watch reads the stated hours too")
    cal = jt.load_calendar(cal_home)
    win = jt.load_windows(cal_home)
    check("the reason names the stated hours", "quiet hours" in jt.quiet_reason(cal, at("2026-09-16T21:00:00-04:00"),
                                                                                routine=False, hold=True, windows=win))
    check("and is empty at noon", jt.quiet_reason(cal, at("2026-09-16T12:00:00-04:00"), routine=False, hold=True, windows=win) == "")

    print("no file, no quiet hours")
    bare = tmp / "bare"
    bare.mkdir()
    check("a person who stated nothing has none", qw.load_windows(bare) is None)
    rc, out, err = run(GATE, bare, "2026-09-15T20:00:00-04:00")
    check("the gate opens for them on a Tuesday evening", last_line(out) == jt.GATE_OPEN)
    (bare / "quiet").mkdir()
    (bare / "quiet" / "windows.json").write_text("not json", encoding="utf-8")
    check("an unreadable file is a problem, not a crash", qw.load_windows(bare) is not None and qw.load_windows(bare).problem)
    rc, out, err = run(GATE, bare, "2026-09-15T20:00:00-04:00")
    check("and the gate still opens", rc == 0 and last_line(out) == jt.GATE_OPEN)
    (bare / "quiet" / "windows.json").write_text(json.dumps({"weekly": [{"days": "xyz", "from": "1", "to": "2"},
                                                                          {"days": "sun", "from": "00:00", "to": "24:00"}]}),
                                                 encoding="utf-8")
    w2 = qw.load_windows(bare)
    check("one bad row is counted and the good one holds", w2.bad_rows == 1 and len(w2.weekly) == 1)

    print("the command keeps the file")
    kept = tmp / "kept"
    (kept / "skills" / "quiet-windows" / "scripts").mkdir(parents=True)
    (kept / "scripts").mkdir()
    (kept / "config.yaml").write_text("timezone: America/Chicago\n", encoding="utf-8")
    (kept / "scripts" / "quiet_windows.py").write_bytes(KEEPER.read_bytes())
    door = kept / "skills" / "quiet-windows" / "scripts" / "quiet-windows"
    door.write_bytes(DOOR.read_bytes())
    door.chmod(0o755)

    def cmd(*args: str) -> tuple[int, str, str]:
        done = subprocess.run([sys.executable, str(door), *args], capture_output=True, text=True, timeout=60,
                              env={k: v for k, v in os.environ.items() if k != "HERMES_HOME"})
        return done.returncode, done.stdout, done.stderr

    rc, out, _ = cmd("list")
    check("nothing kept yet, and the clock is the assistant's", rc == 0 and "No quiet hours" in out and "America/Chicago" in out, out)
    rc, out, err = cmd("add", "weekly", "mon-fri", "19:00", "08:00", "evenings")
    check("a weekly window is added", rc == 0 and "evenings" in out and "19:00-08:00" in out, err[-200:])
    rc, out, err = cmd("add", "dates", "2026-11-26", "2026-11-27", "days", "off")
    check("a dates window is added", rc == 0 and "days off" in out, err[-200:])
    saved = json.loads((kept / "quiet" / "windows.json").read_text(encoding="utf-8"))
    check("the file carries the assistant's clock and both rows", saved["tz"] == "America/Chicago"
          and len(saved["weekly"]) == 1 and len(saved["dates"]) == 1, json.dumps(saved))
    check("the file never names a religion", "Shabbat" not in json.dumps(saved) and "ewish" not in json.dumps(saved))
    wid = saved["weekly"][0]["id"]
    rc, out, _ = cmd("remove", wid)
    check("a window is removed by id", rc == 0 and "evenings" not in out)
    rc, _, err = cmd("remove", "w-nope")
    check("removing what is not there says so", rc == 2 and "no window" in err)
    rc, _, err = cmd("add", "weekly", "mon", "25:00", "08:00")
    check("a bad time is refused in one plain line", rc == 2 and "could not do that" in err)
    rc, out, _ = cmd("tz", "Europe/London")
    check("the clock can be set", rc == 0 and json.loads((kept / "quiet" / "windows.json").read_text())["tz"] == "Europe/London")

    if failures:
        print("\n" + "\n".join(f"FAIL {f}" for f in failures))
        print(f"\n{len(failures)} failure(s)")
        return 1
    print("\nok: quiet windows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
