"""What the commitment watch's monitor source prints, and when it must not change.

Run: python3 tests/test_commitments_state.py

The engine hashes this script's exact stdout and wakes the model only when the
hash moves. So the two ways it can go wrong quietly are opposite: output that
drifts on its own (a clock, an unstable order) wakes the model every tick for
nothing, and output that misses a real move keeps a promise going overdue in
silence. Each case below is one of those.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "commitments_state.py"

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  ok   {name}")
    else:
        failures.append(f"{name}{': ' + detail if detail else ''}")
        print(f"  FAIL {name}{': ' + detail if detail else ''}")


def run(home: Path, vault: Path, now: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in ("JEWISH_TIME_NOW", "TZ")}
    env.update(HERMES_HOME=str(home), OBSIDIAN_VAULT_PATH=str(vault), JEWISH_TIME_NOW=now,
               TZ="America/New_York")
    return subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, env=env)


def note(vault: Path, name: str, **fm) -> Path:
    body = "\n".join(f"{k}: {v}" for k, v in fm.items())
    path = vault / "Commitments" / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{body}\n---\n\n# {name}\n", encoding="utf-8")
    return path


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        home, vault = Path(tmp) / "home", Path(tmp) / "Notes"
        home.mkdir()
        (home / "config.yaml").write_text("timezone: America/New_York\n", encoding="utf-8")
        mark = note(vault, "Mark Josephson - gather the info request", type="commitment",
                    owner="[[Mark Josephson]]", owed_to="[[Frank Cid]]", due="2026-09-22",
                    status="open", **{"from": "[[2026-09-08 Frank meet]]"})
        note(vault, "Lisa Chubb - clinical dashboard", type="commitment", owner="[[Lisa Chubb]]",
             due="2026-11-12", status="open")
        note(vault, "Esther Kohn - invitations", type="commitment", owner="[[Esther Kohn]]",
             due="2026-09-10", status="done", done="2026-09-09")
        (vault / "Sara Westfall.md").write_text("---\ntype: person\n---\nMentions a commitment.\n")
        (vault / "Open commitments.md").write_text(
            "| owner | owed to | what | due | since |\n|---|---|---|---|---|\n"
            "| Ghost | Nobody | a reflection of the notes | 2026-09-01 | 2026-09-01 |\n")
        (vault / "Commitments.md").write_text(
            "---\ntags: [commitments]\n---\n\n# Commitments\n\n"
            "| Owner | Promise | Due | Source |\n|---|---|---|---|\n"
            "| Mark Josephson | Gather the info request | 2026-09-22 | [[Commitments/Mark Josephson - gather the info request]] |\n"
            "| Fred Rowe | Venue for the holiday party | not set | [[2026-09-07 Party|party call]] |\n"
            "| Adam Madison | Replace the administrator | 2026-09-30 | [[2026-09-06 Adam call]] |\n"
            "| Joe Frustaci | An old promise | 2026-09-01 | [[x]] | \n", encoding="utf-8")
        (vault / "Commitments" / "Gone.md").symlink_to(vault / "nowhere.md")
        note(vault, "Rae Pike - sign the lease", type="Commitment", owner="Rae Pike",
             due="2026-10-30", status="open")
        (vault / ".obsidian").mkdir()
        (vault / ".obsidian" / "hidden.md").write_text("---\ntype: commitment\nowner: Hidden\n---\n")

        print("the list")
        first = run(home, vault, "2026-09-15T10:00:00-04:00")
        check("exits cleanly", first.returncode == 0, first.stderr)
        lines = first.stdout.splitlines()
        check("a header with the count, then one line per open promise",
              lines[:1] == ["open commitments: 6"], first.stdout)
        check("lines are sorted", lines[1:] == sorted(lines[1:]))
        check("a note's owner comes out without the link brackets",
              "Mark Josephson | Frank Cid | gather the info request | 2026-09-22 | open | due within a week" in lines,
              first.stdout)
        check("a table row that points at a commitment note is not counted twice",
              sum("Mark Josephson" in l for l in lines) == 1, first.stdout)
        check("a met promise is left out", "Esther Kohn" not in first.stdout)
        check("a row with no due date says so",
              "Fred Rowe | not set | Venue for the holiday party | not set | open | no due date" in lines,
              first.stdout)
        check("a link alias in a table row does not shift the columns",
              "party call" not in first.stdout and "Fred Rowe" in first.stdout)
        check("the nightly rewrite and hidden folders are never read",
              "Ghost" not in first.stdout and "Hidden" not in first.stdout)
        check("a dangling link in the vault is skipped, not a failure", "Gone" not in first.stdout)
        check("a capitalised type still counts", "Rae Pike" in first.stdout, first.stdout)
        check("an overdue row reads overdue", "Joe Frustaci | not set | An old promise | 2026-09-01 | open | overdue" in lines)
        check("no clock in the output", not re.search(r"\d{1,2}:\d{2}|2026-09-15", first.stdout),
              first.stdout)

        print("nothing moved means the same bytes")
        again = run(home, vault, "2026-09-15T16:00:00-04:00")
        check("a later tick the same day prints identical bytes", again.stdout == first.stdout)
        next_day = run(home, vault, "2026-09-16T10:00:00-04:00")
        check("the next day prints identical bytes when no promise crossed a line",
              next_day.stdout == first.stdout, next_day.stdout)

        print("a real move changes the output")
        crossed = run(home, vault, "2026-09-22T10:00:00-04:00")
        check("the day a promise comes due, its line changes",
              "Mark Josephson | Frank Cid | gather the info request | 2026-09-22 | open | due today" in crossed.stdout,
              crossed.stdout)
        mark.write_text(mark.read_text().replace("status: open", "status: done"), encoding="utf-8")
        closed = run(home, vault, "2026-09-16T10:00:00-04:00")
        check("a promise that closes leaves the list",
              "Mark Josephson" not in closed.stdout and closed.stdout.startswith("open commitments: 5"),
              closed.stdout)

        print("a missing vault is an error, never a change")
        gone = run(home, Path(tmp) / "nope", "2026-09-16T10:00:00-04:00")
        check("exits non-zero", gone.returncode != 0)
        check("prints nothing the engine could hash", gone.stdout == "")
        check("says why in one plain line", "could not be read" in gone.stderr, gone.stderr)

        print("inside Shabbat the last answer holds")
        (home / "jewish-time").mkdir()
        (home / "jewish-time" / "calendar.json").write_text(json.dumps({
            "version": 1, "tz": "America/New_York",
            "covers": {"from": "2026-09-01", "to": "2026-10-31"},
            "windows": [{"start": "2026-09-18T18:02:00-04:00", "candles": "2026-09-18T18:42:00-04:00",
                         "end": "2026-09-19T20:11:00-04:00", "what": "Shabbat"}],
            "days": []}), encoding="utf-8")
        before = run(home, vault, "2026-09-18T12:00:00-04:00")
        mark.write_text(mark.read_text().replace("status: done", "status: open"), encoding="utf-8")
        held = run(home, vault, "2026-09-19T11:00:00-04:00")
        check("a promise reopened on Shabbat does not change the output yet",
              held.returncode == 0 and held.stdout == before.stdout, held.stdout)
        after = run(home, vault, "2026-09-20T10:00:00-04:00")
        check("after the hold lifts, the change arrives",
              "Mark Josephson" in after.stdout and after.stdout != before.stdout, after.stdout)

    if failures:
        print(f"\n{len(failures)} failure(s)")
        return 1
    print("\nall commitment watch checks pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
