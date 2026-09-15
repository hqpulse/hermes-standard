"""A scheduled preset never speaks only to introduce itself.

Run: python3 tests/test_presets_never_announce.py

The night of 14 Sept 2026 the nightly commitments preset shipped enabled in
the pack, fired on seven assistants at once, and its whole message was an
announcement about a file nobody had asked for. Nothing in it was worth a
person's attention. This test is the guard.

The rule it enforces has two halves:

  1. A preset that has nothing to report says nothing, on its first run like
     every other run. "Nothing to say" is a complete answer, and it is never
     an excuse to introduce the feature.
  2. A preset may ask whether to keep going ONLY on the back of a message it
     was going to send anyway. The question rides on real content; it is
     never the content.

A preset that is silent by design therefore carries no keep/change/stop
question at all, because it has no message to ride on.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRESETS = ROOT / "skills" / "assistant-standard" / "presets"

# Presets whose whole job is to stay quiet unless something needs saying.
# These may never carry a first-run announcement of any kind.
SILENT_BY_DESIGN = {"open-commitments", "mail-watch"}

ASK = re.compile(r"keep,\s*change,\s*or\s*stop", re.I)
# "except on your first run, ... reply with one line saying ..." and friends:
# an instruction to break silence purely because it is the first run.
BREAKS_SILENCE = re.compile(
    r"except on (?:your|the) first run|"
    r"on the first run only[^.]*reply with one line saying",
    re.I,
)


def prompts():
    for path in sorted(PRESETS.glob("*.json")):
        yield path.stem, json.loads(path.read_text()).get("prompt", "")


def main() -> int:
    failures = []

    for name, prompt in prompts():
        if BREAKS_SILENCE.search(prompt):
            failures.append(
                f"{name}: breaks its own silence on the first run to introduce "
                f"itself. Nothing to say means say nothing, first run included."
            )
        if name in SILENT_BY_DESIGN and ASK.search(prompt):
            failures.append(
                f"{name}: is silent by design and still carries a "
                f"keep/change/stop question. It has no message for that "
                f"question to ride on, so the question IS the message."
            )

    checked = [n for n, _ in prompts()]
    if not checked:
        print("no presets found, nothing checked", file=sys.stderr)
        return 1

    for f in failures:
        print(f"FAIL  {f}")
    if failures:
        return 1

    print(f"ok  {len(checked)} presets: none speaks only to announce itself")
    print(f"    silent by design and confirmed silent: "
          f"{', '.join(sorted(SILENT_BY_DESIGN & set(checked)))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
