#!/usr/bin/env python3
"""Quiet windows: the hours a person is not to be messaged by a scheduled job.

    quiet_windows.py list
    quiet_windows.py add weekly <days> <from> <to> [what ...]    e.g. add weekly sat,sun 00:00 24:00 weekend
    quiet_windows.py add weekly mon-fri 19:00 08:00 evenings     (from after to = overnight)
    quiet_windows.py add dates <from> <to> [what ...]            e.g. add dates 2026-11-26 2026-11-27 Thanksgiving
    quiet_windows.py remove <id>
    quiet_windows.py tz <zone>                                   e.g. tz America/Chicago

An observance calendar (``jewish_time.py``, beside this file, for people who
keep one) is built from where a person lives. This file is everyone's: the
evenings, weekends, days off and personal hours a person states out loud
("don't message me before nine", "I'm off next Thursday and Friday"). The
assistant records them here with the quiet-windows skill the moment they are
said, and the one gate that holds a scheduled job shut for a calendar window
holds it shut for these. Nothing here is
guessed: an empty file means no quiet hours beyond the calendar, and a person
who never states one is messaged on the pack's ordinary rules.

The file is ``<HERMES_HOME>/quiet/windows.json``:

    {"tz": "America/New_York",
     "weekly": [{"id": "w-3f9a1c", "days": ["sat", "sun"], "from": "00:00", "to": "24:00", "what": "weekend"},
                {"id": "w-8b02e7", "days": ["mon", "tue", "wed", "thu", "fri"], "from": "19:00", "to": "08:00", "what": "evenings"}],
     "dates": [{"id": "d-c41d90", "from": "2026-11-26", "to": "2026-11-27", "what": "Thanksgiving"}]}

A weekly window whose ``to`` is earlier than its ``from`` runs overnight and
belongs to the day it starts. ``to`` may be ``24:00``. A dates window covers
whole days, both ends inclusive, in the person's own zone. The zone is the
file's ``tz``, else the assistant's own ``timezone:`` line in its config, else
the box's TZ, else New York.

Stdlib only. Never raises out of ``load_windows``: an unreadable row is counted
and the readable ones still hold, the same rule the calendar keeps.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover - a box without tzdata reads UTC
    ZoneInfo = None  # type: ignore[assignment]

DAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
FILE = ("quiet", "windows.json")


# --- where things are --------------------------------------------------------

def hermes_home() -> Path:
    env = (os.environ.get("HERMES_HOME") or "").strip()
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent


def windows_path(home: Path | None = None) -> Path:
    return (home or hermes_home()).joinpath(*FILE)


def profile_timezone(home: Path | None = None) -> str:
    """The assistant's own clock: its config's ``timezone:`` line, else TZ, else New York."""
    home = home or hermes_home()
    try:
        text = (home / "config.yaml").read_text(encoding="utf-8")
        hit = re.search(r"^timezone:\s*['\"]?([A-Za-z_]+/[A-Za-z_+\-/]+|UTC)['\"]?\s*$", text, re.M)
        if hit:
            return hit.group(1)
    except OSError:
        pass
    env = (os.environ.get("TZ") or "").strip()
    return env or "America/New_York"


def _zone(name: str):
    try:
        return ZoneInfo(name) if ZoneInfo else timezone.utc
    except Exception:  # noqa: BLE001
        return ZoneInfo("America/New_York") if ZoneInfo else timezone.utc


# --- the windows ---------------------------------------------------------------

def _minutes(text: str) -> int:
    hit = re.fullmatch(r"(\d{1,2}):(\d{2})", str(text).strip())
    if not hit:
        raise ValueError(f"not a time of day: {text!r}")
    h, m = int(hit.group(1)), int(hit.group(2))
    if h == 24 and m == 0:
        return 24 * 60
    if not (0 <= h < 24 and 0 <= m < 60):
        raise ValueError(f"not a time of day: {text!r}")
    return h * 60 + m


def _clock(minutes: int) -> str:
    return "24:00" if minutes >= 24 * 60 else f"{minutes // 60:02d}:{minutes % 60:02d}"


def _days(value) -> set[int]:
    """``sat,sun``, ``mon-fri``, a list of names; weekday numbers, Monday 0."""
    if isinstance(value, str):
        parts = [p.strip().lower() for p in value.split(",") if p.strip()]
    else:
        parts = [str(p).strip().lower() for p in (value or [])]
    out: set[int] = set()
    for part in parts:
        if "-" in part:
            a, b = part.split("-", 1)
            ia, ib = DAY_NAMES.index(a[:3]), DAY_NAMES.index(b[:3])
            out.update(range(ia, ib + 1) if ia <= ib else list(range(ia, 7)) + list(range(0, ib + 1)))
        else:
            out.add(DAY_NAMES.index(part[:3]))
    if not out:
        raise ValueError("no days")
    return out


def _ident(kind: str, *fields) -> str:
    return f"{kind[0]}-" + hashlib.sha1("|".join(str(f) for f in fields).encode()).hexdigest()[:6]


class Windows:
    """One person's stated quiet hours."""

    def __init__(self, data: dict | None, tz_name: str, problem: str = ""):
        self.problem = problem
        self.data = data or {}
        self.tz_name = str(self.data.get("tz") or tz_name)
        self.tz = _zone(self.tz_name)
        self.weekly: list[dict] = []
        self.dates: list[dict] = []
        self.bad_rows = 0
        for row in self.data.get("weekly") or []:
            try:
                days = _days(row["days"])
                start, end = _minutes(row["from"]), _minutes(row["to"])
                if start == end:
                    raise ValueError("a window with no length")
                self.weekly.append({"id": str(row.get("id") or _ident("weekly", sorted(days), start, end)),
                                    "days": days, "from": start, "to": end,
                                    "what": str(row.get("what") or "quiet hours")})
            except (KeyError, TypeError, ValueError):
                self.bad_rows += 1
        for row in self.data.get("dates") or []:
            try:
                first, last = date.fromisoformat(str(row["from"])), date.fromisoformat(str(row["to"]))
                if last < first:
                    first, last = last, first
                self.dates.append({"id": str(row.get("id") or _ident("dates", first, last)),
                                   "from": first, "to": last, "what": str(row.get("what") or "days off")})
            except (KeyError, TypeError, ValueError):
                self.bad_rows += 1
        self.dates.sort(key=lambda r: r["from"])

    def __bool__(self) -> bool:
        return bool(self.weekly or self.dates)

    # -- reading -------------------------------------------------------------------

    def _weekly_span(self, row: dict, day: date) -> tuple[datetime, datetime] | None:
        """The concrete span of a weekly row that begins on ``day``, or None."""
        if day.weekday() not in row["days"]:
            return None
        start = datetime.combine(day, time(0, 0), tzinfo=self.tz) + timedelta(minutes=row["from"])
        if row["to"] > row["from"]:
            end = datetime.combine(day, time(0, 0), tzinfo=self.tz) + timedelta(minutes=row["to"])
        else:
            end = datetime.combine(day + timedelta(days=1), time(0, 0), tzinfo=self.tz) + timedelta(minutes=row["to"])
        return start, end

    def window_at(self, moment: datetime) -> dict | None:
        """The stated window this moment is inside, if any."""
        local = moment.astimezone(self.tz)
        today = local.date()
        for row in self.dates:
            if row["from"] <= today <= row["to"]:
                start = datetime.combine(row["from"], time(0, 0), tzinfo=self.tz)
                end = datetime.combine(row["to"] + timedelta(days=1), time(0, 0), tzinfo=self.tz)
                return {"start": start, "end": end, "what": row["what"], "id": row["id"]}
        for row in self.weekly:
            for day in (today - timedelta(days=1), today):
                span = self._weekly_span(row, day)
                if span and span[0] <= local < span[1]:
                    return {"start": span[0], "end": span[1], "what": row["what"], "id": row["id"]}
        return None

    def next_window_after(self, moment: datetime, horizon_days: int = 14) -> dict | None:
        local = moment.astimezone(self.tz)
        best: dict | None = None
        for row in self.dates:
            start = datetime.combine(row["from"], time(0, 0), tzinfo=self.tz)
            if start > local and (best is None or start < best["start"]):
                end = datetime.combine(row["to"] + timedelta(days=1), time(0, 0), tzinfo=self.tz)
                best = {"start": start, "end": end, "what": row["what"], "id": row["id"]}
        for offset in range(0, horizon_days):
            day = local.date() + timedelta(days=offset)
            for row in self.weekly:
                span = self._weekly_span(row, day)
                if span and span[0] > local and (best is None or span[0] < best["start"]):
                    best = {"start": span[0], "end": span[1], "what": row["what"], "id": row["id"]}
        return best

    def describe(self) -> list[str]:
        lines = []
        for row in self.weekly:
            days = ",".join(DAY_NAMES[d] for d in sorted(row["days"]))
            lines.append(f"{row['id']}  weekly  {days}  {_clock(row['from'])}-{_clock(row['to'])}  {row['what']}")
        for row in self.dates:
            lines.append(f"{row['id']}  dates   {row['from'].isoformat()} to {row['to'].isoformat()}  {row['what']}")
        return lines

    # -- writing ---------------------------------------------------------------------

    def to_json(self) -> dict:
        return {
            "tz": self.tz_name,
            "weekly": [{"id": r["id"], "days": [DAY_NAMES[d] for d in sorted(r["days"])],
                        "from": _clock(r["from"]), "to": _clock(r["to"]), "what": r["what"]} for r in self.weekly],
            "dates": [{"id": r["id"], "from": r["from"].isoformat(), "to": r["to"].isoformat(), "what": r["what"]}
                      for r in self.dates],
        }


def load_windows(home: Path | None = None) -> Windows | None:
    """None when this person has stated no quiet hours; a Windows otherwise."""
    path = windows_path(home)
    if not path.exists():
        return None
    tz_name = profile_timezone(home)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return Windows(None, tz_name, f"the quiet windows file could not be read ({type(exc).__name__})")
    if not isinstance(data, dict):
        return Windows(None, tz_name, "the quiet windows file is not a list of windows")
    return Windows(data, tz_name)


def save_windows(windows: Windows, home: Path | None = None) -> Path:
    path = windows_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(windows.to_json(), indent=1) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def _when(moment: datetime, tz) -> str:
    local = moment.astimezone(tz)
    return f"{local.strftime('%a')} {local.day} {local.strftime('%b')} {local.strftime('%I:%M%p').lstrip('0').lower()}"


def lines_for(windows: Windows | None, moment: datetime) -> list[str]:
    """What a scheduled job's reading says about the person's stated quiet hours."""
    if windows is None or not windows:
        return []
    inside = windows.window_at(moment)
    if inside is not None:
        return [f"Inside the person's quiet hours ({inside['what']}) until {_when(inside['end'], windows.tz)}. "
                "Nothing unprompted goes out; a scheduled job answers exactly [SILENT]."]
    upcoming = windows.next_window_after(moment)
    if upcoming is None:
        return ["Not inside the person's quiet hours."]
    return [f"Not inside the person's quiet hours. Their next: {_when(upcoming['start'], windows.tz)} to "
            f"{_when(upcoming['end'], windows.tz)} ({upcoming['what']})."]


# --- the command ---------------------------------------------------------------

def main(argv: list[str]) -> int:
    home = hermes_home()
    if not argv or argv[0] == "list":
        windows = load_windows(home)
        if windows is None or not windows:
            print(f"No quiet hours kept beyond the calendar. Clock: {profile_timezone(home)}.")
            return 0
        print(f"Clock: {windows.tz_name}")
        print("\n".join(windows.describe()))
        if windows.bad_rows:
            print(f"({windows.bad_rows} unreadable row(s) ignored)")
        return 0
    command, rest = argv[0], argv[1:]
    windows = load_windows(home) or Windows(None, profile_timezone(home))
    try:
        if command == "add" and rest[:1] == ["weekly"] and len(rest) >= 4:
            days, start, end = _days(rest[1]), _minutes(rest[2]), _minutes(rest[3])
            if start == end:
                raise ValueError("a window with no length")
            what = " ".join(rest[4:]).strip() or "quiet hours"
            row = {"id": _ident("weekly", sorted(days), start, end), "days": days, "from": start, "to": end, "what": what}
            windows.weekly = [r for r in windows.weekly if r["id"] != row["id"]] + [row]
        elif command == "add" and rest[:1] == ["dates"] and len(rest) >= 3:
            first, last = date.fromisoformat(rest[1]), date.fromisoformat(rest[2])
            if last < first:
                first, last = last, first
            what = " ".join(rest[3:]).strip() or "days off"
            row = {"id": _ident("dates", first, last), "from": first, "to": last, "what": what}
            windows.dates = [r for r in windows.dates if r["id"] != row["id"]] + [row]
            windows.dates.sort(key=lambda r: r["from"])
        elif command == "remove" and len(rest) == 1:
            before = len(windows.weekly) + len(windows.dates)
            windows.weekly = [r for r in windows.weekly if r["id"] != rest[0]]
            windows.dates = [r for r in windows.dates if r["id"] != rest[0]]
            if len(windows.weekly) + len(windows.dates) == before:
                print(f"no window called {rest[0]}", file=sys.stderr)
                return 2
        elif command == "tz" and len(rest) == 1:
            if ZoneInfo:
                ZoneInfo(rest[0])
            windows.tz_name = rest[0]
            windows.tz = _zone(rest[0])
        else:
            print(__doc__.split("\n\n", 2)[1], file=sys.stderr)
            return 2
    except Exception as exc:  # noqa: BLE001 - one plain line, the way the person would hear it
        print(f"could not do that: {exc}", file=sys.stderr)
        return 2
    save_windows(windows, home)
    print("\n".join(windows.describe()) or "No quiet hours kept beyond the calendar.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
