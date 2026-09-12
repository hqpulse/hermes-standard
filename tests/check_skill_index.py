#!/usr/bin/env python3
"""What the model actually sees: the skills index line, one per skill.

Run from the repo root with `python3 tests/check_skill_index.py`.

WHY THIS EXISTS

The engine puts one line per skill into the system prompt, under a heading
that tells the model to load anything even partially relevant:

    <available_skills>
      browser:
        - browser: Drive a real web browser - open a page, read it, click, t...

That line is the whole retrieval signal. The description on it is cut hard at
60 characters (`SKILL_PROMPT_DESC_LIMIT` in the engine's
`agent/skill_utils.py`): a description longer than 60 is served as its first
57 characters plus "...", and everything after that is invisible until
something else has already made the model open the skill. `browser`'s real
description is 279 characters, so 78% of it is never read at retrieval time.

So: a skill whose own name is not in those first characters cannot be found by
name. A model looking for the mail watch, scanning an index line that says
"Deciding whether something that just arrived in the perso...", has nothing to
match on.

THE RULE

Every word of a skill's name must appear in the part of its description the
index actually shows. Words, not the hyphenated slug, because that is how the
match happens: "Obsidian Flavored Markdown" names obsidian-markdown perfectly
well. A word counts when it appears at the start of a word in the visible
text, so "note" is found by "notes" and "mail" by "mailbox".

Nothing here judges whether a description is good. It only refuses one
specific failure: a skill the index cannot name.

This script uses the engine's own parser and its own truncation function when
HERMES_SRC (or ~/.hermes/hermes-agent) is there, and reimplements both from
the same constants when it is not. The two agree; CI pins the engine so the
answer comes from the code that ships.
"""
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERMES = Path(os.environ.get("HERMES_SRC", Path.home() / ".hermes" / "hermes-agent"))

# agent/skill_utils.py: SKILL_PROMPT_DESC_LIMIT = 60, and a longer description
# is served as desc[:LIMIT - 3] + "...". Kept here as the fallback for a run
# with no engine on disk; the import below wins when there is one.
DESC_LIMIT = 60
_engine = "a local copy of its truncation rule (no engine source on disk)"

parse_frontmatter = None
extract_skill_description = None
if (HERMES / "agent" / "skill_utils.py").exists():
    sys.path.insert(0, str(HERMES))
    try:
        from agent.skill_utils import (  # noqa: E402
            SKILL_PROMPT_DESC_LIMIT,
            extract_skill_description,
            parse_frontmatter,
        )
        DESC_LIMIT = SKILL_PROMPT_DESC_LIMIT
        _engine = f"the engine at {HERMES}"
    except Exception as e:  # pragma: no cover
        print(f"note: engine helpers unavailable ({e}); using the local copy")
        parse_frontmatter = extract_skill_description = None


def _plain_frontmatter(text):
    """Frontmatter without the engine, parsed the way the engine parses it.

    agent/skill_utils.py:parse_frontmatter tries YAML and, when YAML raises,
    falls back to splitting each line on its first colon. That fallback is not
    a nicety: an unquoted description containing ": " is not valid YAML, and
    the pack has shipped ones that only load because of it. Mirroring both
    halves is what makes a run with no engine on disk give the same answer as
    a run with one.
    """
    import yaml
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}, text
    block, body = m.group(1), text[m.end():]
    try:
        parsed = yaml.safe_load(block)
        if isinstance(parsed, dict):
            return parsed, body
    except Exception:
        pass
    fm = {}
    for line in block.strip().split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            fm[key.strip()] = value.strip()
    return fm, body


def _plain_visible(fm):
    """The index line's description, exactly as extract_skill_description makes it."""
    raw = fm.get("description", "")
    desc = str(raw).strip().strip("'\"") if raw else ""
    if len(desc) > DESC_LIMIT:
        return desc[:DESC_LIMIT - 3] + "..."
    return desc


def missing_name_words(name, visible):
    """The words of `name` the visible description does not carry."""
    haystack = re.sub(r"[^a-z0-9]+", " ", visible.lower())
    out = []
    for word in re.split(r"[-_]", name.lower()):
        if not word:
            continue
        if not re.search(r"(?:^| )" + re.escape(word), haystack):
            out.append(word)
    return out


def main():
    read_fm = parse_frontmatter or _plain_frontmatter
    visible_of = extract_skill_description or _plain_visible

    errors = []
    rows = []
    for skill_md in sorted(ROOT.glob("skills/**/SKILL.md")):
        rel = skill_md.relative_to(ROOT)
        text = skill_md.read_text()
        fm, _ = read_fm(text)
        name = (fm.get("name") or skill_md.parent.name).strip()
        raw = str(fm.get("description", "") or "").strip().strip("'\"")
        visible = visible_of(fm)
        missing = missing_name_words(name, visible)
        rows.append((name, len(raw), visible, missing))
        if not raw:
            # check_pack.py owns the missing-description failure; nothing to
            # lint here, and reporting it twice helps nobody.
            continue
        if missing:
            errors.append(
                f"{rel}: the index shows {visible!r}, which never says "
                f"{', '.join(missing)!r}. The first {DESC_LIMIT - 3} characters "
                f"are the whole retrieval signal, so put the skill's own name in "
                f"them and let the rest of the sentence run on."
            )

    width = max(len(r[0]) for r in rows) if rows else 4
    print(f"skills index, cut at {DESC_LIMIT}, built with {_engine}:")
    for name, raw_len, visible, missing in rows:
        mark = "FAIL" if missing else "ok  "
        lost = f"  [{raw_len - len(visible)} chars never shown]" if raw_len > len(visible) else ""
        print(f"  {mark} {name:<{width}}  {visible!r}{lost}")

    if errors:
        print()
        print("\n".join(f"FAIL {e}" for e in errors))
        return 1
    print(f"ok: {len(rows)} skills, every one named in its own index line")
    return 0


if __name__ == "__main__":
    sys.exit(main())
