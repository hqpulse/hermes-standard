"""The commitment watch's monitor source: every open promise, one line each.

WHY A MONITOR SOURCE AND NOT A PRE-RUN SCRIPT. The preset names this file as
``monitor_script``, not ``script``. The engine runs it FIRST on every tick
(cron/monitor.py, check_monitor), hashes its exact stdout, and when the hash
matches the last tick that woke the model it records a silent ``no_change``
run: no model, no delivery, no cost. When the hash differs it hands the model
a unified diff of old against new. So the state wakes the model, not the clock,
and nothing here has to remember what it showed before; the engine does.

EXACT BYTES, SO NO CLOCK. Anything that moves on its own makes every tick look
like a change. The output carries no timestamp, no "as of", no count of days:
"due in 4 days" becomes "due in 3 days" overnight and would wake the model
daily with nothing moved. Days-to-due is therefore a BUCKET (overdue, due
today, due tomorrow, due within a week, due later, no due date), which changes
only on the day a promise actually crosses a line, and that crossing is exactly
the change worth judging. Lines are sorted on their full text.

WHAT IT READS. Every note under the vault with ``type: commitment`` whose
status is open (or unset), and the rows of the vault root ``Commitments.md``
table. A row whose source link points at a commitment note is skipped: the note
is the promise and the row is a pointer to it. ``Open commitments.md`` is the
nightly preset's rewrite of the same notes and is never read, or the watch
would see its own reflection change every night.

A FAILURE IS AN ERROR, NEVER A CHANGE. A missing vault exits non-zero. The
engine then records the tick as a source failure and leaves its stored hash
alone, so when the vault comes back unchanged the watch stays silent.

QUIET WINDOWS HOLD THE LAST ANSWER. The engine persists the new hash before any
pre-run gate could close, so a change seen inside Shabbat or a person's quiet
hours would be spent on a tick nobody may hear. Instead, while
``jewish_time.py`` says the person is held, this prints the last output it gave
outside a window, byte for byte: the engine sees no change, and everything that
moved meanwhile arrives as one diff when the hold lifts.
"""
from __future__ import annotations

import os
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

DEFAULT_VAULT = "/opt/data/workspace/Notes"
CLOSED = {"done", "dropped", "closed", "cancelled", "canceled", "complete", "completed"}
NOT_SET = {"", "not set", "none", "tbd", "n/a", "-"}
FIELD_LIMIT = 120
LINK = re.compile(r"\[\[([^\]|#]*)(?:#[^\]|]*)?(?:\|([^\]]*))?\]\]")


def _home() -> Path:
    env = (os.environ.get("HERMES_HOME") or "").strip()
    return Path(env) if env else Path(__file__).resolve().parent.parent


def _beside(name: str, path: Path):
    import importlib.util  # noqa: PLC0415
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _now() -> datetime:
    # The same test pin the quiet calendar and the mail watch read.
    pinned = (os.environ.get("JEWISH_TIME_NOW") or "").strip()
    if pinned:
        return datetime.fromisoformat(pinned).astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def _held(home: Path, now: datetime) -> bool:
    try:
        jt = _beside("jewish_time", Path(__file__).resolve().parent / "jewish_time.py")
        return bool(jt.quiet_reason(jt.load_calendar(home), now, routine=False, hold=True,
                                    windows=jt.load_windows(home)))
    except Exception:  # noqa: BLE001 - same careful fallback as the mail watch
        if not (home / "jewish-time" / "calendar.json").exists():
            return False
        local = now.astimezone()
        return (local.weekday() == 4 and local.hour >= 12) or local.weekday() == 5


def _today(home: Path, now: datetime) -> date:
    try:
        from zoneinfo import ZoneInfo  # noqa: PLC0415
        qw = _beside("quiet_windows", Path(__file__).resolve().parent / "quiet_windows.py")
        return now.astimezone(ZoneInfo(qw.profile_timezone(home))).date()
    except Exception:  # noqa: BLE001
        return now.astimezone().date()


def _plain(value) -> str:
    if isinstance(value, (list, tuple)):
        value = ", ".join(_plain(v) for v in value if _plain(v))
    text = LINK.sub(lambda m: (m.group(2) or m.group(1)).strip(), str(value if value is not None else ""))
    text = " ".join(text.replace("|", "/").replace("[[", "").replace("]]", "").split())
    return text[:FIELD_LIMIT]


def _when(due: str, today: date) -> str:
    try:
        days = (date.fromisoformat(due[:10]) - today).days
    except ValueError:
        return "no due date"
    if days < 0:
        return "overdue"
    return {0: "due today", 1: "due tomorrow"}.get(days, "due within a week" if days <= 7 else "due later")


def _line(owner, owed_to, what, due, status, today: date) -> str:
    due = _plain(due)
    due = "" if due.lower() in NOT_SET else due
    return " | ".join((_plain(owner) or "no owner", _plain(owed_to) or "not set", _plain(what),
                       due or "not set",
                       _plain(status).lower() or "open", _when(due, today)))


def collect(vault: Path, today: date, entity_note) -> list[str]:
    # A list, not a set: two identical promises are two, and one closing is a move.
    lines, note_names = [], set()
    for dirpath, dirnames, filenames in os.walk(vault):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for filename in filenames:
            if not filename.endswith(".md"):
                continue
            path = Path(dirpath) / filename
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                # A dangling link, a locked file or a note renamed mid-walk. One
                # odd file must not turn every tick into a source failure.
                continue
            if "commitment" not in text.lower():
                continue
            try:
                fm, _body = entity_note.parse_frontmatter(text)
            except entity_note.Refusal:
                if re.search(r"^type:\s*commitment\s*$", text, re.M | re.I):
                    lines.append(f"unreadable commitment note | {_plain(path.stem)}")
                continue
            if str(fm.get("type") or "").strip().lower() != "commitment":
                continue
            note_names.add(path.stem.lower())
            if _plain(fm.get("status")).lower() in CLOSED:
                continue
            what = fm.get("what") or path.stem.split(" - ", 1)[-1]
            lines.append(_line(fm.get("owner"), fm.get("owed_to"), what, fm.get("due"),
                               fm.get("status"), today))
    table = vault / "Commitments.md"
    if table.is_file():
        header = None
        for raw in table.read_text(encoding="utf-8", errors="replace").splitlines():
            if not raw.strip().startswith("|"):
                header = None
                continue
            # A wikilink alias ([[Note|shown]]) carries a pipe that is not a column.
            masked = LINK.sub(lambda m: m.group(0).replace("|", "\x00"), raw.strip().strip("|"))
            cells = [c.strip().replace("\x00", "|") for c in masked.split("|")]
            if header is None:
                header = [c.lower() for c in cells]
                continue
            if all(set(c) <= set("-: ") for c in cells):
                continue
            row = dict(zip(header, cells))
            what = row.get("what") or row.get("promise") or row.get("commitment") or ""
            source = LINK.search(row.get("source") or row.get("from") or "")
            target = source.group(1).strip().rsplit("/", 1)[-1].lower() if source else ""
            if not what.strip() or target in note_names:
                continue
            if _plain(row.get("status")).lower() in CLOSED or what.strip().startswith("~~"):
                continue
            lines.append(_line(row.get("owner"), row.get("owed to") or row.get("owed_to"), what,
                               row.get("due"), row.get("status"), today))
    return sorted(lines)


def main() -> int:
    home = _home()
    now = _now()
    snapshot = home / "commitment-watch" / "last-output.txt"
    if _held(home, now) and snapshot.is_file():
        sys.stdout.write(snapshot.read_text(encoding="utf-8"))
        return 0
    vault = Path((os.environ.get("OBSIDIAN_VAULT_PATH") or "").strip() or DEFAULT_VAULT)
    if not vault.is_dir():
        print(f"The notes folder {vault} is not there, so open commitments could not be read.",
              file=sys.stderr)
        return 2
    # The pack's own frontmatter reader, one directory over from scripts/.
    entity_note = _beside("entity_note", Path(__file__).resolve().parent.parent
                          / "skills" / "entity-notes" / "entity_note.py")
    lines = collect(vault, _today(home, now), entity_note)
    output = "\n".join([f"open commitments: {len(lines)}", *lines]) + "\n"
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    tmp = snapshot.with_suffix(".tmp")
    tmp.write_text(output, encoding="utf-8")
    tmp.replace(snapshot)
    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
