#!/usr/bin/env python3
"""The engine's name must not be in text an assistant could repeat to a person.

Run from the repo root with `python3 tests/check_engine_name.py`.

WHY. The product is "an assistant". A customer buys an assistant from Pulse and
must never be told which engine it is built on, because that is our supplier
and not their business. The persona already says "never name a vendor", but a
persona is one file and this pack ships sixty-odd others straight onto every
pod. Every one of them is text a model reads, and a model repeats what it
reads. So the rule has to be checked, not trusted.

WHAT IS CHECKED. Every file the pack actually ships -- the `distribution_owned`
list in distribution.yaml, which is the exact set `_copy_dist_payload` copies
onto a pod -- is read, its CODE is removed, and what is left is prose. The
engine's name in that prose is a failure.

WHAT IS NOT CHECKED, AND WHY NOT.
  - Fenced code blocks, indented code blocks and inline `code spans` in
    markdown. A path, a module or a command is an identifier: the assistant
    runs it, it does not say it in a sentence.
  - The KEY half of a frontmatter line. `metadata.hermes.requires_tools` is the
    engine's own schema for the block; the engine reads that key by name and a
    skill whose frontmatter it cannot parse silently does not exist. The VALUE
    half is content and is checked.
  - `#` comments in shipped Python and shell. Those are developer comments,
    which the ticket keeps on purpose.
  - Identifier tokens anywhere: `HERMES_TIMEZONE`, `hermes-standard`,
    `hermes_fleet`, `/etc/hermes/lane`, a namespace, a pod name, an image tag.
    Renaming those is a coordinated rename across every script and every live
    cluster object, and it is deliberately a separate decision (HYG-03 item 4).
    The line between the two is the one thing this check draws: a name inside
    an identifier is infrastructure, the same name inside a sentence is a leak.

So a green run here means: nothing in the shipped pack SAYS the engine's name.
It does not mean the name is gone from the pack.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The engine, in every form somebody might write it in a sentence.
ENGINE = re.compile(r"\bhermes\b", re.I)

# An identifier that merely CONTAINS the name. Checked before the sentence
# rule, so `HERMES_HOME` in running prose is allowed and "Hermes v0.21" is not.
IDENTIFIER = re.compile(
    r"""
      HERMES_[A-Z0-9_]+            # env vars: HERMES_HOME, HERMES_TIMEZONE
    | hermes[-_][A-Za-z0-9][\w.-]* # hermes-standard, hermes_fleet, hermes-pvc,
                                   # hermes-susan-0, hermes_time.py
    | [\w./~-]*/hermes(?:[/\w.-]*)? # /etc/hermes/lane, ~/.hermes/hermes-agent
    | \.hermes\b                   # ~/.hermes
    """,
    re.X,
)

FENCE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE = re.compile(r"`[^`\n]*`")
INDENTED = re.compile(r"^(?: {4,}|\t)")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
FRONTMATTER_KEY = re.compile(r"^(\s*-?\s*[\w.\"'-]+:)(.*)$")

TEXT_SUFFIXES = {".md", ".txt"}
HASH_COMMENT_SUFFIXES = {".py", ".sh", ".yaml", ".yml", ".base", ""}
DATA_SUFFIXES = {".json", ".jsonl", ".tsv", ".patch", ".example"}


def shipped_files() -> list[Path]:
    """The paths distribution.yaml owns: exactly what reaches a pod."""
    text = (ROOT / "distribution.yaml").read_text(encoding="utf-8")
    body = text.split("distribution_owned:", 1)
    if len(body) != 2:
        raise SystemExit("distribution.yaml has no distribution_owned: list")
    out = []
    for line in body[1].splitlines():
        if not line.startswith("  - "):
            if line.strip() and not line.startswith((" ", "\t", "#")):
                break  # next top-level key
            continue
        rel = line[4:].strip().strip('"').strip("'")
        if rel:
            out.append(ROOT / rel)
    return out


def prose_lines(path: Path) -> list[tuple[int, str]]:
    """The file with its code removed, as (line number, text) pairs."""
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    suffix = path.suffix.lower()
    if suffix in TEXT_SUFFIXES:
        raw = HTML_COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), raw)

    lines = raw.splitlines()
    # A leading `---` block in markdown is YAML frontmatter: keys are the
    # engine's schema, values are content.
    frontmatter_end = 0
    if suffix in TEXT_SUFFIXES and lines and lines[0].strip() == "---":
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                frontmatter_end = i
                break

    out: list[tuple[int, str]] = []
    in_fence = False
    for n, line in enumerate(lines, 1):
        if n <= frontmatter_end:
            m = FRONTMATTER_KEY.match(line)
            out.append((n, m.group(2) if m else line))
            continue
        if suffix in TEXT_SUFFIXES:
            if FENCE.match(line):
                in_fence = not in_fence
                continue
            if in_fence or INDENTED.match(line):
                continue
            line = INLINE_CODE.sub(" ", line)
        elif suffix in HASH_COMMENT_SUFFIXES or path.name in ("login", "keeper", "reach", "ecw"):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            line = re.sub(r"(?<!\\)#.*$", " ", line)
        elif suffix in DATA_SUFFIXES:
            pass  # every byte of a data file is read as-is
        out.append((n, line))
    return out


def main() -> int:
    findings: list[str] = []
    checked = 0
    for path in shipped_files():
        if not path.exists():
            findings.append(f"{path.relative_to(ROOT)}: listed in distribution.yaml, not on disk")
            continue
        checked += 1
        for n, line in prose_lines(path):
            bare = IDENTIFIER.sub(" ", line)
            if ENGINE.search(bare):
                findings.append(f"{path.relative_to(ROOT)}:{n}: {line.strip()}")

    if findings:
        print("The engine's name is in text an assistant reads as a sentence:")
        for f in findings:
            print(f"  {f}")
        print()
        print("Say 'the engine' or 'the agent software' instead. If it really is an")
        print("identifier -- an env var, a path, a module, a namespace -- put it in a")
        print("code span so it reads as one.")
        return 1

    print(f"ok: {checked} shipped files, none of them say the engine's name")
    return 0


if __name__ == "__main__":
    sys.exit(main())
