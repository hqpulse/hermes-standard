"""The quiet calendar: built from a saved hebcal answer, read at the minutes that matter.

Run: python3 tests/test_jewish_time.py

Every case is a morning or an evening a real person would have been messaged
into, or not told about. The fixture is hebcal.com's own answer for Lakewood NJ
08701 across three stretches (Rosh Hashana to Simchat Torah 2026, Pesach 2027,
the Nine Days 2027), trimmed to the fields the build reads. The times asserted
here were checked on 14 Sep 2026 against the 57-window table hand-built for the
first person who keeps it, and all 57 agreed.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "jewish_time.py"
FIXTURE = ROOT / "tests" / "fixtures" / "hebcal-08701.json"
sys.path.insert(0, str(ROOT / "scripts"))

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


def run(home: Path, stamp: str, *args: str) -> str:
    env = dict(os.environ)
    env.update({"HERMES_HOME": str(home), "JEWISH_TIME_NOW": stamp})
    done = subprocess.run([sys.executable, str(SCRIPT), *args], env=env,
                          capture_output=True, text=True, timeout=60)
    if done.returncode != 0:
        raise AssertionError(f"exit {done.returncode}: {done.stderr[-400:]}")
    return done.stdout


def last_line(out: str) -> str:
    lines = [ln for ln in out.splitlines() if ln.strip()]
    return lines[-1].strip() if lines else ""


def main() -> int:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    built = jt.build_calendar(payload, date(2026, 9, 8), date(2027, 8, 14), zip_code="08701")
    windows = {w["start"][:16]: w for w in built["windows"]}

    print("the build turns candles and havdalah into quiet windows")
    rh = windows.get("2026-09-11T18:14")
    check("Rosh Hashana on Shabbat is one window, Friday to Sunday night",
          bool(rh) and rh["end"].startswith("2026-09-13T20:21"), str(rh))
    yk = windows.get("2026-09-20T17:59")
    check("Yom Kippur runs Sunday 5:59pm to Monday 8:07pm",
          bool(yk) and yk["end"].startswith("2026-09-21T20:07") and "Yom Kippur" in yk["what"], str(yk))
    sukkot = windows.get("2026-09-25T17:50")
    check("Sukkot I on Shabbat and Sukkot II is one window with no gap",
          bool(sukkot) and sukkot["end"].startswith("2026-09-27T19:58"), str(sukkot))
    check("the second night's candles never open a second window",
          not any(k.startswith("2026-09-26") for k in windows))
    pesach = windows.get("2027-04-21T18:43")
    check("Pesach I, II and the Shabbat after are one four-day window",
          bool(pesach) and pesach["end"].startswith("2027-04-24T20:56"), str(pesach))
    check("quiet starts forty minutes before candle lighting",
          all((at(w["candles"]) - at(w["start"])).total_seconds() == 2400 for w in built["windows"]))

    kinds = {(d["date"], d["kind"]) for d in built["days"]}
    fast = [d for d in built["days"] if d["kind"] == "fast" and d["date"] == "2026-09-14"]
    check("Tzom Gedaliah is a fast day with both times",
          bool(fast) and fast[0].get("begins", "").startswith("2026-09-14T05:15")
          and fast[0].get("ends", "").startswith("2026-09-14T19:40"), str(fast))
    check("chol hamoed Sukkot is Monday to Friday, Hoshana Raba included",
          all((f"2026-09-{d:02d}", "chol_hamoed") in kinds for d in (28, 29, 30))
          and ("2026-10-02", "chol_hamoed") in kinds)
    check("erev Pesach and Tisha B'Av are marked", ("2027-04-21", "erev_pesach") in kinds
          and ("2027-08-12", "tisha_bav") in kinds)
    check("the Nine Days run up to Tisha B'Av", ("2027-08-11", "nine_days") in kinds
          and ("2027-08-12", "nine_days") not in kinds)
    bechorot = [d for d in built["days"] if d["what"].startswith("Ta'anit Bechorot")]
    check("a fast that runs into yom tov has a start and no end",
          bool(bechorot) and "begins" in bechorot[0] and "ends" not in bechorot[0], str(bechorot))

    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp)
        (home / "jewish-time").mkdir()
        (home / "jewish-time" / "calendar.json").write_text(json.dumps(built), encoding="utf-8")

        print("the gate a scheduled job runs")
        out = run(home, "2026-09-21T07:30:00-04:00")
        check("the Yom Kippur morning brief never wakes the model",
              out.strip() == '{"wakeAgent": false}', out)
        out = run(home, "2026-09-18T18:30:00-04:00")
        check("Friday after the cutoff is closed", last_line(out) == '{"wakeAgent": false}')
        out = run(home, "2026-09-18T17:30:00-04:00")
        check("Friday before the cutoff is open", last_line(out) == '{"wakeAgent": true}')
        check("and it says the window begins today", "It begins today" in out, out)
        out = run(home, "2026-09-19T20:30:00-04:00")
        check("Saturday night after havdalah a brief may run", last_line(out) == '{"wakeAgent": true}')
        out = run(home, "2027-04-21T08:00:00-04:00")
        check("erev Pesach keeps a routine job silent though it is no window",
              out.strip() == '{"wakeAgent": false}', out)

        print("what the brief is told")
        out = run(home, "2026-09-14T07:30:00-04:00")
        check("the fast is named with its times", "Tzom Gedaliah, from 5:15am to 7:40pm" in out, out)
        check("the fast is never to be mentioned", "not a word about the fast" in out)
        check("the look-back reaches the Friday before Rosh Hashana",
              "last working day before today was Fri 11 Sep 2026" in out, out)
        out = run(home, "2026-09-22T07:30:00-04:00")
        check("after Yom Kippur on a Monday the look-back is the Friday",
              "Fri 18 Sep 2026" in out, out)
        out = run(home, "2026-09-16T07:30:00-04:00")
        check("an ordinary Wednesday carries no look-back line", "last working day" not in out, out)
        out = run(home, "2026-09-24T07:30:00-04:00")
        check("the Thursday before a three-day window says to get ahead of it",
              "begins tomorrow" in out and "3 days" in out, out)
        out = run(home, "2026-09-29T07:30:00-04:00")
        check("chol hamoed is a working day that is not one", "Chol hamoed Sukkot" in out, out)
        check("no reading uses a dash a phone would print",
              all("—" not in run(home, s) and "–" not in run(home, s)
                  for s in ("2026-09-14T07:30:00-04:00", "2026-09-29T07:30:00-04:00")))

        print("the careful answer when the calendar cannot be trusted")
        out = run(home, "2028-01-07T13:00:00-05:00")
        check("a Friday afternoon past the calendar's end is closed",
              out.strip() == '{"wakeAgent": false}', out)
        out = run(home, "2028-01-05T08:00:00-05:00")
        check("a Wednesday past the end runs, and says timing is unknown",
              last_line(out) == '{"wakeAgent": true}' and "does not cover today" in out, out)
        broken = home / "broken"
        (broken / "jewish-time").mkdir(parents=True)
        (broken / "jewish-time" / "calendar.json").write_text("{not json", encoding="utf-8")
        out = run(broken, "2026-09-18T13:00:00-04:00")
        check("an unreadable calendar on a Friday afternoon is closed",
              out.strip() == '{"wakeAgent": false}', out)
        out = run(broken, "2026-09-16T08:00:00-04:00")
        check("an unreadable calendar midweek never crashes the job",
              last_line(out) == '{"wakeAgent": true}', out)

        print("somebody who does not keep it")
        nobody = home / "nobody"
        nobody.mkdir()
        out = run(nobody, "2026-09-19T11:00:00-04:00")
        check("no calendar never closes the gate, even on a Saturday",
              last_line(out) == '{"wakeAgent": true}', out)
        check("and the model is told nothing about it applies", "None is kept" in out, out)
        check("the reading is never empty, or the engine would skip the brief",
              len(out.strip().splitlines()) >= 2)

        print("the interrupting watch is also held the morning after")
        cal = jt.load_calendar(home)
        check("Saturday 8:30pm, after havdalah, the watch is still held",
              bool(jt.quiet_reason(cal, at("2026-09-19T20:30:00-04:00"), routine=False, hold=True)))
        check("Sunday 9:30am the hold has lifted",
              not jt.quiet_reason(cal, at("2026-09-20T09:30:00-04:00"), routine=False, hold=True))
        check("Tisha B'Av does not hold a watch that only speaks for the urgent",
              not jt.quiet_reason(jt.Calendar(built), at("2027-08-12T11:00:00-04:00"),
                                  routine=False, hold=True))

        print("the chat commands")
        out = run(home, "2026-09-14T07:30:00-04:00", "on", "2026-09-25")
        check("one day names its window", "Fri 25 Sep 2026 5:50pm to Sun 27 Sep 2026 7:58pm" in out, out)
        out = run(home, "2026-09-19T12:00:00-04:00", "now")
        check("now inside a window prints no gate line and says SILENT",
              "[SILENT]" in out and "wakeAgent" not in out, out)

    if failures:
        print(f"\n{len(failures)} failure(s)")
        return 1
    print("\nok: jewish time")
    return 0


if __name__ == "__main__":
    sys.exit(main())
