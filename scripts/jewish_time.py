#!/usr/bin/env python3
"""Jewish time for one person: when to be silent, and what kind of day it is.

    jewish_time.py                  the gate a scheduled job runs before its model
    jewish_time.py now              the same reading, for the assistant in chat
    jewish_time.py on YYYY-MM-DD    one day: quiet windows, fasts, chol hamoed
    jewish_time.py status           for staff: the dates covered, and exit 1 inside 60 days of the end
    jewish_time.py build --zip Z [--tz TZ] [--start D] [--months N] [--out FILE]
                                    fetch a person's calendar from hebcal.com (24 months)

WHY A SCRIPT. On 14 Sep 2026 one assistant's three scheduled jobs were taught
to answer a single word inside Shabbat and yom tov, by a paragraph at the top
of each prompt. That holds only as long as the model reads the paragraph, finds
the right row in a 57-row table, and spells the silence word the way the engine
listens for it (it was spelled wrong on the first night, and would have
delivered that word to her phone every half hour of Shabbat). So the gate is
code: the engine runs a job's ``script`` BEFORE the model, and a last stdout
line of ``{"wakeAgent": false}`` skips the model entirely, with nothing
delivered and nothing spent. The model never has to be right about the clock.

WHOSE DATA. The RULES are the pack's and the same for everyone. The TIMES are
one person's: which city, which minhag. They live in
``<HERMES_HOME>/jewish-time/calendar.json``, a path the pack never names, so a
pack upgrade never touches it. No file means this person does not keep it, and
every command says so in one neutral line and gates nothing.

WHERE THE TIMES COME FROM. ``build`` asks hebcal.com for diaspora holidays with
candle lighting at a set number of minutes before sunset (18, the Lakewood
custom) and havdalah at a fixed number of minutes after sunset (72). A quiet
window runs from 40 minutes before the first candle lighting to the havdalah
that closes the run, so a yom tov that touches Shabbat is one window with no
gap. Nobody on a pod computes a zman; the file is built once and read.

A CALENDAR RUNS OUT. Past its last date nobody can know which weekday is yom
tov, so ``build`` reaches 24 months and ``status`` exits non-zero inside
EXPIRY_WARN_DAYS of the end, for whoever checks the fleet. The model is never
the one told: it is instructed never to repeat any of this.

IT NEVER FAILS A JOB. The engine reports a crashed script to the person as a
broken job. Every path out of the gate prints something and exits 0. A calendar
that cannot be read, or a day past its last date, is treated the careful way:
Friday noon to Saturday midnight is quiet, because an hour late costs nothing
and a message inside Shabbat is remembered.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - every interpreter the fleet runs has it
    ZoneInfo = None  # type: ignore[assignment]

#: Quiet starts this long before candle lighting.
QUIET_BEFORE_CANDLES_MIN = 40
#: Candle lighting before sunset, and havdalah after it, as asked of hebcal.
CANDLES_BEFORE_SUNSET_MIN = 18
HAVDALAH_AFTER_SUNSET_MIN = 72
#: After a window ends, a watch that interrupts stays held until this hour of
#: the next morning, so nothing waiting flushes the minute it opens.
HOLD_UNTIL_HOUR = 9
#: How far back a build reaches, so the first morning after a long yom tov
#: can still see where it began.
BUILD_LOOKBACK_DAYS = 14
#: How far ahead a build reaches by default, and how much further it asks
#: hebcal for, so a window that opens on the last covered day still has its end.
BUILD_MONTHS = 24
FETCH_MARGIN_DAYS = 14
#: ``status`` fails this many days before the calendar's last date.
EXPIRY_WARN_DAYS = 60
HEBCAL = "https://www.hebcal.com/hebcal"

CALENDAR_VERSION = 1

GATE_CLOSED = '{"wakeAgent": false}'
GATE_OPEN = '{"wakeAgent": true}'

NONE_KEPT = ("QUIET CALENDAR. None is kept for this person: nothing about their week "
             "changes, and none of this is ever mentioned to them.")

# What each kind of day means for how the assistant writes. The words are the
# model's instructions, so they are plain, and none of them is ever repeated
# to the person.
DAY_NOTES = {
    "fast": ("A fast day, {what}, {span}. They have not eaten since before dawn: "
             "shorter than usual, nothing about food or coffee, nothing heavy in the "
             "afternoon, no voice note, and not a word about the fast."),
    "chol_hamoed": ("Chol hamoed {what}: a working day that is not one. Messages are "
                    "fine, but expect half days and people out, and ask for no big decision."),
    "chanukah": ("Chanukah: a normal working day, but the evening is family from "
                 "nightfall, so nothing routine after late afternoon."),
    "erev_purim": "Erev Purim: Purim begins at nightfall, so nothing routine late in the day.",
    "purim": "Purim: a working day on paper and gone in practice. Half a day at best, nothing routine.",
    "erev_pesach": ("Erev Pesach: the most compressed day of the year. Routine scheduled "
                    "messages stay silent; only something that truly cannot wait."),
    "tisha_bav": ("Tisha B'Av: not a yom tov, and the heaviest day of the year. Routine "
                  "scheduled messages stay silent; urgent only, and never a voice note."),
    "nine_days": ("The Nine Days: subdued. No celebratory framing, and no voice note."),
}
#: Days on which a routine scheduled message stays silent although it is not
#: a quiet window. A watch that only speaks for the urgent may still run.
ROUTINE_QUIET = {"erev_pesach", "tisha_bav"}


# --- reading the calendar ---------------------------------------------------

def hermes_home() -> Path:
    env = (os.environ.get("HERMES_HOME") or "").strip()
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent


def calendar_path(home: Path | None = None) -> Path:
    return (home or hermes_home()) / "jewish-time" / "calendar.json"


class Calendar:
    """One person's calendar, or the careful stand-in when it cannot be read."""

    def __init__(self, data: dict | None, problem: str = ""):
        self.problem = problem
        self.data = data or {}
        tz_name = str(self.data.get("tz") or os.environ.get("TZ") or "America/New_York")
        try:
            self.tz = ZoneInfo(tz_name) if ZoneInfo else timezone.utc
        except Exception:  # noqa: BLE001 - an unknown zone is the careful path, not a crash
            self.tz = ZoneInfo("America/New_York") if ZoneInfo else timezone.utc
            self.problem = self.problem or f"unknown time zone {tz_name!r}"
        self.windows = []
        self.bad_rows = 0
        for row in self.data.get("windows") or []:
            try:
                self.windows.append({
                    "start": _parse(row["start"]), "end": _parse(row["end"]),
                    "what": str(row.get("what") or "Shabbat")})
            except (KeyError, TypeError, ValueError):
                # One bad row must not throw away every good one: the readable
                # windows still hold, and the careful Friday-to-Saturday rule
                # is laid over them in window_at.
                self.bad_rows += 1
        self.windows.sort(key=lambda w: w["start"])
        self.days: dict[str, list[dict]] = {}
        for row in self.data.get("days") or []:
            if isinstance(row, dict) and row.get("date") and row.get("kind"):
                self.days.setdefault(str(row["date"]), []).append(row)
        covers = self.data.get("covers") or {}
        try:
            self.first = date.fromisoformat(str(covers["from"]))
            self.last = date.fromisoformat(str(covers["to"]))
        except (KeyError, TypeError, ValueError):
            self.first = self.last = None
            self.problem = self.problem or "the calendar does not say which dates it covers"

    def covers(self, day: date) -> bool:
        return not self.problem and self.first is not None and self.first <= day <= self.last

    def window_at(self, moment: datetime) -> dict | None:
        """The quiet window this moment is inside, if any.

        Past the calendar's last date, and whenever the calendar is unreadable,
        the careful stand-in answers instead: Friday noon to Saturday midnight.
        A calendar with an unreadable row keeps its good windows and gets the
        careful stand-in as well.
        """
        if not self.covers(moment.astimezone(self.tz).date()):
            return _careful_window(moment.astimezone(self.tz))
        for window in self.windows:
            if window["start"] <= moment < window["end"]:
                return window
        if self.bad_rows:
            return _careful_window(moment.astimezone(self.tz))
        return None

    def last_window_before(self, moment: datetime) -> dict | None:
        ended = [w for w in self.windows if w["end"] <= moment]
        return ended[-1] if ended else None

    def next_window_after(self, moment: datetime) -> dict | None:
        for window in self.windows:
            if window["start"] > moment:
                return window
        return None

    def day_rows(self, day: date) -> list[dict]:
        return self.days.get(day.isoformat(), [])

    def routine_quiet(self, day: date) -> dict | None:
        for row in self.day_rows(day):
            if row.get("kind") in ROUTINE_QUIET:
                return row
        return None

    def is_working_day(self, day: date) -> bool:
        """Monday to Friday, not inside a window at noon, not a routine-quiet day."""
        if day.weekday() > 4:
            return False
        noon = datetime.combine(day, time(12, 0), tzinfo=self.tz)
        return self.window_at(noon) is None and self.routine_quiet(day) is None


def _careful_window(local: datetime) -> dict | None:
    friday = local.date() - timedelta(days=(local.weekday() - 4) % 7)
    start = datetime.combine(friday, time(12, 0), tzinfo=local.tzinfo)
    end = datetime.combine(friday + timedelta(days=2), time(0, 0), tzinfo=local.tzinfo)
    if start <= local < end:
        return {"start": start, "end": end, "what": "possibly Shabbat", "careful": True}
    return None


def _parse(stamp: str) -> datetime:
    moment = datetime.fromisoformat(str(stamp))
    if moment.tzinfo is None:
        raise ValueError("a time in the calendar has no offset")
    return moment


def load_calendar(home: Path | None = None) -> Calendar | None:
    """None when this person keeps no calendar; a Calendar otherwise, flagged
    with its problem when the file is there and cannot be trusted."""
    path = calendar_path(home)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return Calendar(None, f"the calendar file could not be read ({type(exc).__name__})")
    if not isinstance(data, dict):
        return Calendar(None, "the calendar file is not a calendar")
    return Calendar(data)


def load_windows(home: Path | None = None):
    """The person's stated quiet hours (evenings, weekends, days off), kept by
    ``quiet_windows.py`` beside this file. None when they have stated none, or
    when the keeper is not installed: the calendar alone then decides."""
    try:
        import importlib.util  # noqa: PLC0415
        keeper = Path(__file__).resolve().parent / "quiet_windows.py"
        spec = importlib.util.spec_from_file_location("quiet_windows", keeper)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        return module.load_windows(home or hermes_home())
    except Exception:  # noqa: BLE001 - a broken keeper must not break the gate
        return None


def windows_lines(windows, moment: datetime) -> list[str]:
    """The reading's lines about stated quiet hours; empty when there are none."""
    if windows is None:
        return []
    try:
        import importlib.util  # noqa: PLC0415
        keeper = Path(__file__).resolve().parent / "quiet_windows.py"
        spec = importlib.util.spec_from_file_location("quiet_windows", keeper)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        return module.lines_for(windows, moment)
    except Exception:  # noqa: BLE001
        return []


def now() -> datetime:
    """The present moment. JEWISH_TIME_NOW pins it, for tests and for asking
    what a job would have done at a given minute."""
    pinned = (os.environ.get("JEWISH_TIME_NOW") or "").strip()
    if pinned:
        return _parse(pinned)
    return datetime.now(timezone.utc)


# --- what the reading says --------------------------------------------------

def _clock(moment: datetime) -> str:
    return moment.strftime("%I:%M%p").lstrip("0").lower()


def _when(moment: datetime, tz) -> str:
    local = moment.astimezone(tz)
    return f"{local.strftime('%a')} {local.day} {local.strftime('%b %Y')} {_clock(local)}"


def _day_name(day: date) -> str:
    return f"{day.strftime('%a')} {day.day} {day.strftime('%b %Y')}"


def held_after_window(cal: Calendar, moment: datetime) -> dict | None:
    """The window just closed, while the hold after it lasts: from its end until
    HOLD_UNTIL_HOUR on the following morning. Only an interrupting watch uses it."""
    last = cal.last_window_before(moment)
    if last is None:
        return None
    end_local = last["end"].astimezone(cal.tz)
    release = datetime.combine(end_local.date() + timedelta(days=1), time(HOLD_UNTIL_HOUR, 0),
                               tzinfo=cal.tz)
    return last if moment < release else None


def quiet_reason(cal: Calendar | None, moment: datetime, *, routine: bool, hold: bool,
                 windows=None) -> str:
    """Why a scheduled job must stay silent right now, or "" when it may run.

    ``routine`` also silences the days a routine message never goes out on
    (erev Pesach, Tisha B'Av). ``hold`` keeps an interrupting watch shut from the
    end of a window until the next morning. ``windows`` is the person's stated
    quiet hours (``load_windows``); inside one, every scheduled job is silent."""
    if windows is not None:
        try:
            stated = windows.window_at(moment)
        except Exception:  # noqa: BLE001
            stated = None
        if stated is not None:
            return f"inside the person's quiet hours ({stated['what']})"
    if cal is None:
        return ""
    window = cal.window_at(moment)
    if window is not None:
        return f"inside a quiet window ({window['what']})"
    local_day = moment.astimezone(cal.tz).date()
    if routine:
        row = cal.routine_quiet(local_day)
        if row is not None:
            return f"a day routine messages stay silent ({row.get('what') or row['kind']})"
    if hold and held_after_window(cal, moment) is not None:
        return "held until the morning after a quiet window"
    return ""


def describe_day(cal: Calendar, day: date) -> list[str]:
    lines = []
    for row in cal.day_rows(day):
        template = DAY_NOTES.get(str(row.get("kind")))
        if not template:
            continue
        begins, ends = row.get("begins"), row.get("ends")
        span = ""
        try:
            if begins and ends:
                span = f"from {_clock(_parse(begins).astimezone(cal.tz))} to {_clock(_parse(ends).astimezone(cal.tz))}"
            elif begins:
                span = f"from {_clock(_parse(begins).astimezone(cal.tz))} until yom tov begins"
        except ValueError:
            span = ""
        lines.append(template.format(what=row.get("what") or row["kind"], span=span or "all day")
                     .replace(", all day.", "."))
    return lines


def reading(cal: Calendar | None, moment: datetime, windows=None) -> list[str]:
    """The lines a model reads: where the person is in their week, right now."""
    if cal is None:
        extra = windows_lines(windows, moment)
        if not extra:
            return [NONE_KEPT]
        return ["QUIET CALENDAR. This person keeps quiet hours. Read this before you write "
                "anything, act on it, and never repeat any of it to them."] + extra
    lines = _calendar_reading(cal, moment)
    return lines + windows_lines(windows, moment)


def _calendar_reading(cal: Calendar, moment: datetime) -> list[str]:
    local = moment.astimezone(cal.tz)
    today = local.date()
    lines = ["QUIET CALENDAR. This person keeps Shabbat and yom tov. Read this before you "
             "write anything, act on it, and never repeat any of it to them."]
    lines.append(f"Now: {_when(moment, cal.tz)}.")
    if not cal.covers(today):
        lines.append("The calendar does not cover today, so timing is unknown: treat Friday "
                     "from noon to the end of Saturday as quiet, say nothing about timing, "
                     "and never work out a time yourself.")
    window = cal.window_at(moment)
    if window is not None:
        until = "" if window.get("careful") else f" until {_when(window['end'], cal.tz)}"
        lines.append(f"Inside a quiet window ({window['what']}){until}. Nothing unprompted "
                     "goes out; a scheduled job answers exactly [SILENT].")
    else:
        lines.append("Not inside a quiet window.")
    row = cal.routine_quiet(today)
    if row is not None:
        lines.append("Routine scheduled messages stay silent today.")
    lines.extend(describe_day(cal, today))
    if cal.covers(today) and window is None:
        upcoming = cal.next_window_after(moment)
        if upcoming is not None:
            lines.append(f"Next quiet window: {_when(upcoming['start'], cal.tz)} to "
                         f"{_when(upcoming['end'], cal.tz)} ({upcoming['what']}).")
            days_off = (upcoming["end"].astimezone(cal.tz).date()
                        - upcoming["start"].astimezone(cal.tz).date()).days
            starts = upcoming["start"].astimezone(cal.tz).date()
            if starts == today:
                lines.append("It begins today: anything that needs them before it has to "
                             "reach them well before then, in one message, not a trickle.")
            elif starts == today + timedelta(days=1) and days_off >= 2:
                lines.append(f"It begins tomorrow and they are gone about {days_off + 1} days: "
                             "today is the day to help them get ahead of it.")
        previous = _last_working_day(cal, today)
        if previous is not None and (today - previous).days > 1 and cal.is_working_day(today):
            closed = [w for w in cal.windows
                      if w["start"].astimezone(cal.tz).date() == previous]
            began = f" (quiet began {_clock(closed[0]['start'].astimezone(cal.tz))})" if closed else ""
            lines.append(f"Their last working day before today was {_day_name(previous)}{began}. "
                         "Look back to then, not to yesterday: the oldest thing that is "
                         "genuinely theirs outranks anything on today's calendar.")
    return lines


def _last_working_day(cal: Calendar, today: date) -> date | None:
    day = today - timedelta(days=1)
    for _ in range(10):
        if cal.first is not None and day < cal.first:
            return None
        if cal.is_working_day(day):
            return day
        day -= timedelta(days=1)
    return None


def day_reading(cal: Calendar | None, day: date) -> list[str]:
    if cal is None:
        return [NONE_KEPT]
    lines = [f"QUIET CALENDAR for {_day_name(day)}. Never repeat any of it to them."]
    if not cal.covers(day):
        lines.append("The calendar does not cover this date: say nothing about timing, and "
                     "treat Friday from noon to the end of Saturday as quiet.")
        return lines
    start = datetime.combine(day, time(0, 0), tzinfo=cal.tz)
    end = start + timedelta(days=1)
    touching = [w for w in cal.windows if w["start"] < end and w["end"] > start]
    for window in touching:
        lines.append(f"Quiet window: {_when(window['start'], cal.tz)} to "
                     f"{_when(window['end'], cal.tz)} ({window['what']}).")
    if not touching:
        lines.append("No quiet window touches this date.")
    if cal.routine_quiet(day) is not None:
        lines.append("Routine scheduled messages stay silent on this date.")
    lines.extend(describe_day(cal, day))
    return lines


# --- the gate ---------------------------------------------------------------

def gate(home: Path | None = None, moment: datetime | None = None) -> str:
    """What a scheduled job's script prints. Never raises."""
    try:
        cal = load_calendar(home)
        windows = load_windows(home)
        moment = moment or now()
        if quiet_reason(cal, moment, routine=True, hold=False, windows=windows):
            return GATE_CLOSED
        return "\n".join(reading(cal, moment, windows) + [GATE_OPEN])
    except Exception:  # noqa: BLE001 - a crashed gate reads as a broken job to the person
        return "\n".join([
            "QUIET CALENDAR. It could not be read this run, so timing is unknown: if today is "
            "a Friday afternoon or a Saturday, answer exactly [SILENT]; otherwise carry on and "
            "say nothing about timing.",
            GATE_OPEN])


# --- building a person's calendar from hebcal -------------------------------

def _plain(text: str) -> str:
    return str(text or "").replace("’", "'").replace("‘", "'").strip()


def fetch_hebcal(zip_code: str, start: date, end: date) -> dict:
    query = urllib.parse.urlencode({
        "v": 1, "cfg": "json", "maj": "on", "min": "on", "nx": "on", "mod": "off",
        "ss": "off", "mf": "on", "c": "on", "s": "on", "i": "off", "geo": "zip",
        "zip": zip_code, "b": CANDLES_BEFORE_SUNSET_MIN, "m": HAVDALAH_AFTER_SUNSET_MIN,
        "start": start.isoformat(), "end": end.isoformat()})
    with urllib.request.urlopen(f"{HEBCAL}?{query}", timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def build_calendar(payload: dict, start: date, end: date, *, zip_code: str = "",
                   tz: str = "") -> dict:
    """Turn one hebcal answer into the calendar file. Pure, so it is testable
    against a saved answer."""
    items = [i for i in payload.get("items") or [] if isinstance(i, dict)]
    location = payload.get("location") or {}
    tz = tz or str(location.get("tzid") or "America/New_York")

    def when(item):
        return _parse(item["date"]) if "T" in str(item.get("date")) else None

    marks = sorted(((when(i), i) for i in items if i.get("category") in ("candles", "havdalah")
                    and when(i) is not None), key=lambda pair: pair[0])
    windows = []
    open_at = candles_at = None
    for moment, item in marks:
        if item["category"] == "candles" and open_at is None:
            candles_at = moment
            open_at = moment - timedelta(minutes=QUIET_BEFORE_CANDLES_MIN)
        elif item["category"] == "havdalah" and open_at is not None:
            windows.append({"start": open_at, "candles": candles_at, "end": moment})
            open_at = candles_at = None
    windows = [w for w in windows if w["start"].date() <= end]
    if open_at is not None and open_at.date() <= end:
        # A candle lighting with no havdalah after it: the answer stopped
        # mid-window. The calendar must not claim a day it cannot close.
        end = open_at.date() - timedelta(days=1)

    by_date: dict[str, list[dict]] = {}
    for item in items:
        by_date.setdefault(str(item.get("date"))[:10], []).append(item)

    rows = []
    for window in windows:
        names = []
        day = window["start"].date() + timedelta(days=1)
        while day <= window["end"].date():
            todays = by_date.get(day.isoformat(), [])
            yomtov = [_plain(i["title"]) for i in todays
                      if i.get("category") == "holiday" and i.get("yomtov")]
            parsha = [_plain(i["title"]).replace("Parashat ", "") for i in todays
                      if i.get("category") == "parashat"]
            if yomtov:
                for name in yomtov:
                    names.append(name + (" (on Shabbat)" if day.weekday() == 5 else ""))
            elif day.weekday() == 5:
                names.append("Shabbat" + (f" {parsha[0]}" if parsha else ""))
            day += timedelta(days=1)
        rows.append({"start": window["start"].isoformat(), "candles": window["candles"].isoformat(),
                     "end": window["end"].isoformat(), "what": " + ".join(names) or "Shabbat"})

    days = []
    # A fast's begin and end are separate items, and the same fast comes round
    # every year, so they pair in time order: an end closes the open begin of
    # the same name. A begin with no end (Ta'anit Bechorot runs into yom tov)
    # stands alone.
    fasts: list[tuple[str, dict]] = []
    open_fasts: dict[str, dict] = {}
    zmanim = sorted((i for i in items if i.get("category") == "zmanim" and i.get("subcat") == "fast"),
                    key=lambda i: str(i.get("date")))
    for item in zmanim:
        name = _plain(item.get("memo")).replace("Erev ", "").replace(" (observed)", "")
        if _plain(item["title"]).lower().startswith("fast begins"):
            entry = {"begins": item["date"]}
            open_fasts[name] = entry
            fasts.append((name, entry))
        elif name in open_fasts:
            open_fasts.pop(name)["ends"] = item["date"]
        else:
            fasts.append((name, {"ends": item["date"]}))
    for name, entry in fasts:
        if name == "Yom Kippur":
            continue
        anchor = entry.get("ends") or entry.get("begins")
        row = {"date": str(anchor)[:10], "kind": "fast", "what": name}
        row.update(entry)
        days.append(row)

    nine_days_from = None
    for item in sorted(items, key=lambda i: str(i.get("date"))):
        title = _plain(item.get("title"))
        on = str(item.get("date"))[:10]
        if item.get("category") == "holiday" and ("CH''M" in title or "Hoshana Raba" in title):
            days.append({"date": on, "kind": "chol_hamoed", "what": title.split(" ")[0]})
        elif item.get("category") == "holiday" and title.startswith("Chanukah"):
            if not any(d["date"] == on and d["kind"] == "chanukah" for d in days):
                days.append({"date": on, "kind": "chanukah", "what": "Chanukah"})
        elif title == "Erev Purim":
            days.append({"date": on, "kind": "erev_purim", "what": title})
        elif title == "Purim":
            days.append({"date": on, "kind": "purim", "what": title})
        elif title == "Erev Pesach":
            days.append({"date": on, "kind": "erev_pesach", "what": title})
        elif title.startswith("Tish'a B'Av"):
            days.append({"date": on, "kind": "tisha_bav", "what": "Tisha B'Av"})
            if nine_days_from:
                day = date.fromisoformat(nine_days_from)
                while day < date.fromisoformat(on):
                    days.append({"date": day.isoformat(), "kind": "nine_days",
                                 "what": "the Nine Days"})
                    day += timedelta(days=1)
                nine_days_from = None
        elif item.get("category") == "roshchodesh" and title == "Rosh Chodesh Av":
            nine_days_from = on
    days.sort(key=lambda d: (d["date"], d["kind"]))

    return {
        "version": CALENDAR_VERSION,
        "keeps": "shabbat and yom tov",
        "place": str(location.get("title") or zip_code),
        "zip": zip_code,
        "tz": tz,
        "rules": {"quiet_before_candles_min": QUIET_BEFORE_CANDLES_MIN,
                  "candles_before_sunset_min": CANDLES_BEFORE_SUNSET_MIN,
                  "havdalah_after_sunset_min": HAVDALAH_AFTER_SUNSET_MIN,
                  "diaspora": True},
        "source": "hebcal.com",
        "built": datetime.now(timezone.utc).date().isoformat(),
        "covers": {"from": start.isoformat(), "to": end.isoformat()},
        "windows": rows,
        "days": days,
    }


def _build_main(args: list[str]) -> int:
    opts = {"--zip": "", "--tz": "", "--start": "", "--months": str(BUILD_MONTHS), "--out": ""}
    it = iter(args)
    for flag in it:
        if flag not in opts:
            print(f"unknown option {flag}", file=sys.stderr)
            return 2
        opts[flag] = next(it, "")
    if not opts["--zip"]:
        print("build needs --zip", file=sys.stderr)
        return 2
    today = datetime.now(timezone.utc).date()
    start = date.fromisoformat(opts["--start"]) if opts["--start"] else today - timedelta(days=BUILD_LOOKBACK_DAYS)
    end = start + timedelta(days=int(opts["--months"]) * 31)
    payload = fetch_hebcal(opts["--zip"], start, end + timedelta(days=FETCH_MARGIN_DAYS))
    calendar = build_calendar(payload, start, end, zip_code=opts["--zip"], tz=opts["--tz"])
    text = json.dumps(calendar, indent=1, ensure_ascii=False) + "\n"
    if opts["--out"]:
        out = Path(opts["--out"])
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(".json.tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(out)
        print(f"{len(calendar['windows'])} quiet windows and {len(calendar['days'])} marked days, "
              f"{calendar['covers']['from']} to {calendar['covers']['to']}, written to {opts['--out']}")
    else:
        sys.stdout.write(text)
    return 0


def _status_main() -> int:
    """For staff and fleet checks, never for the person: what is covered, and
    whether it is about to run out."""
    cal = load_calendar()
    if cal is None:
        print("no calendar: this person does not keep one")
        return 0
    if cal.first is None or cal.problem:
        print(f"calendar present but not usable: {cal.problem or 'no dates'}")
        return 1
    left = (cal.last - datetime.now(cal.tz).date()).days
    note = f", {cal.bad_rows} unreadable window row(s)" if cal.bad_rows else ""
    print(f"covers {cal.first} to {cal.last}, {left} days left, {len(cal.windows)} windows{note}")
    return 1 if left < EXPIRY_WARN_DAYS or cal.bad_rows else 0


def main(argv: list[str]) -> int:
    if not argv:
        print(gate())
        return 0
    command, rest = argv[0], argv[1:]
    if command == "build":
        return _build_main(rest)
    if command == "status":
        return _status_main()
    try:
        cal = load_calendar()
        if command == "now":
            print("\n".join(reading(cal, now(), load_windows())))
            return 0
        if command == "on" and rest:
            print("\n".join(day_reading(cal, date.fromisoformat(rest[0]))))
            return 0
    except ValueError as exc:
        print(f"could not read that: {exc}", file=sys.stderr)
        return 2
    print(__doc__.split("\n\n", 2)[1], file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
