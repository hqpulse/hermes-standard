#!/usr/bin/env python3
"""The entity-notes helper, checked without installing anything.

Run: python3 tests/check_entity_notes.py

What is checked, in the order it would hurt:

  1. THE FILENAME. Every nasty name a real record system hands over - commas, apostrophes, slashes,
     accents, invisible characters, a name that is only punctuation, a sixty-word legal entity - and
     the two properties the whole design rests on: the key comes back out of the filename exactly,
     and two entities with the SAME NAME never collide.
  2. THE FRONTMATTER. A key this parser has never heard of survives a read and a write by an older
     writer, byte for byte, in its place.
  3. THE WRITE. A process killed between the write and the rename leaves the old note intact and
     nothing in the folder that reads as a note.
  4. THE FOLDER. No notes folder anywhere means a refusal in words, not a folder invented in $HOME.
  5. The rest of the substrate: sections and the append-only rule, the regenerated block, the diff
     that has a row for every field including the unchanged ones, and the index.

Known gaps, so a green run is not read as more than it is:
  - The frontmatter parser is checked against what we write, plus a handful of shapes somebody else
    might. It is not a YAML conformance suite and does not pretend to be.
  - The interrupted-write check kills a real child process, but only at the one point that matters
    (between the temp write and the rename). A disk that lies about fsync is not simulated.
"""
import json
import os
import shutil
import pathlib
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HELPER_DIR = ROOT / "skills" / "entity-notes"
sys.path.insert(0, str(HELPER_DIR))
# No __pycache__ next to the helper: everything under skills/ has to be a file the pack
# ships, and check_pack.py fails on anything there that is not in distribution_owned.
sys.dont_write_bytecode = True

import entity_note as E  # noqa: E402

failures = []
checks = 0


def check(condition, label):
    global checks
    checks += 1
    if not condition:
        failures.append(label)
    return bool(condition)


def refuses(fn, label, reason=None):
    global checks
    checks += 1
    try:
        fn()
    except E.Refusal as refusal:
        if reason and refusal.reason != reason:
            failures.append("%s (refused with %r, wanted %r)" % (label, refusal.reason, reason))
        elif not str(refusal).strip():
            failures.append("%s (refused with an empty sentence)" % label)
        return True
    except Exception as exc:                      # noqa: BLE001 - any other exception is the bug
        failures.append("%s (raised %s instead of a refusal)" % (label, exc.__class__.__name__))
        return False
    failures.append("%s (did not refuse)" % label)
    return False


# ------------------------------------------------------------------ 1. the filename

KEY = "PCC-CHCC-C4471902"
NASTY = [
    ("Camacho, Rosa", "Camacho Rosa", "a comma is dropped, family name stays first"),
    ("O'Brien, Mary Kate", "O'Brien Mary Kate", "an apostrophe survives"),
    ("Vandermeer-Katz, Teresa", "Vandermeer-Katz Teresa", "a hyphen survives"),
    ("Muñoz, Ana", "Muñoz Ana", "an accent survives"),
    ("Acme / Tooling: GmbH", "Acme Tooling GmbH", "a slash and a colon become one space each"),
    ("Back\\slash Ltd", "Back slash Ltd", "a backslash becomes a space"),
    ("Star*Mark ?Co", "Star Mark Co", "a star and a question mark become spaces"),
    ('Quote"Co <Ltd>', "Quote Co Ltd", "quotes and angle brackets go"),
    ("Pipe|Hash# Co", "Pipe Hash Co", "a pipe and a hash would break a wikilink"),
    ("Caret^ Bracket[s] 100%", "Caret Bracket s 100", "caret, brackets and percent go"),
    ("   Trailing   spaces   ", "Trailing spaces", "whitespace runs collapse and trim"),
    ("Ivy​League Supplies", "Ivy League Supplies", "a zero-width character becomes a space"),
    ("Tab\tand\nnewline", "Tab and newline", "a tab and a newline become spaces"),
    (".hidden name", "hidden name", "a leading dot would hide the note"),
    ("山田 太郎", "山田 太郎", "CJK survives untouched"),
    ("ACME GMBH", "ACME GMBH", "case is not touched: only the caller knows its record system"),
]
for raw, want, why in NASTY:
    got = E.clean_name(raw)
    check(got == want, "clean_name(%r) -> %r, wanted %r (%s)" % (raw, got, want, why))

# The same name in two unicode spellings must be ONE filename, or one entity gets two files.
decomposed = unicodedata.normalize("NFD", "Muñoz, Ana")
check(E.clean_name(decomposed) == E.clean_name("Muñoz, Ana"),
      "a decomposed accent normalises to the same filename as the composed one")

long_name = "Kensington and Chelsea Community Vascular Associates of Greater London Limited"
cut = E.clean_name(long_name)
check(len(cut) <= 60 and cut == "Kensington and Chelsea Community Vascular Associates of",
      "a long name is cut to 60 characters on a word boundary (got %r)" % cut)
one_word = "B" * 90
check(len(E.clean_name(one_word)) == 60, "a single word longer than the limit is cut hard")
check(E.clean_name("*" * 20) == "", "a name that is only illegal characters leaves nothing")
refuses(lambda: E.note_filename("*" * 20, KEY),
        "a name that leaves nothing refuses rather than writing ' - KEY.md'")
refuses(lambda: E.note_filename("", KEY), "an empty name refuses")

# Reversibility: the key comes back out of every one of those filenames, with no parsing.
for raw, _want, _why in NASTY + [(long_name, "", ""), (one_word, "", "")]:
    filename = E.note_filename(raw, KEY)
    check(E.key_from_filename(filename) == KEY,
          "the key survives a round trip through the filename for %r" % raw)
check(E.key_from_filename("Vandermeer - Katz Teresa - PCC-GRND-C1.md") == "PCC-GRND-C1",
      "a name containing ' - ' still splits at the last one")
check(E.key_from_filename("no key here.md") == "", "a filename with no key answers with nothing")

check(E.entity_key("pcc", "chcc", "C4471902") == "PCC-CHCC-C4471902", "the key is built as agreed")
check(E.entity_key("sap  erp", "acme_co", "44/71") == "SAP-ERP-ACME-CO-44-71",
      "runs of anything but letters and digits become one hyphen")
refuses(lambda: E.entity_key("pcc", "UNKNOWN", "C1"), "an unknown tenant refuses", "needs-a-person")
refuses(lambda: E.entity_key("pcc", "chcc", ""), "a missing record number refuses", "needs-a-person")
refuses(lambda: E.entity_key("pcc", "chcc", "   "), "a blank record number refuses")

# ------------------------------------------------------------------ 2. same name, two entities

work = Path(tempfile.mkdtemp(prefix="entity-notes-check."))
folder = work / "Suppliers"
folder.mkdir(parents=True)

KEY_A, KEY_B = "SAP-ACME-4471", "SAP-ACME-9902"
name_a = E.note_filename("Fisher, Jordan", KEY_A)
name_b = E.note_filename("Fisher, Jordan", KEY_B)
check(name_a != name_b, "two entities with the same name get two filenames")
for key, filename in ((KEY_A, name_a), (KEY_B, name_b)):
    fm = E.starter_frontmatter("supplier", key, "Fisher, Jordan", "company", "record", "sap")
    fm.set("registered", "2019-04-02" if key == KEY_A else "2021-11-30")
    E.write_note(folder / filename, E.Note(fm, "# Fisher, Jordan — %s\n" % key))
check(len(list(folder.glob("*.md"))) == 2, "both files exist side by side")
made = E.entity_folder("Customers", root=str(work))
check(oct(os.stat(made).st_mode)[-3:] == "700", "a folder this layer creates is 0700")
written = E.read_note(folder / name_a)
check(written.fm.get("entity_key") == KEY_A and written.body.startswith("# Fisher, Jordan"),
      "a note reads back as what was written")
nothing_yet = E.locate(str(folder), "SAP-ACME-0000", "Nobody, At All")
check(not nothing_yet.exists and nothing_yet.how == "new"
      and os.path.basename(nothing_yet.path) == "Nobody At All - SAP-ACME-0000.md",
      "an entity we have never met resolves to the filename it would get, and no file")

index, problems = E.rebuild_index(str(folder), identity_fields=("display", "registered"))
E.save_index(str(folder), index)
check(not problems, "a clean folder rebuilds with no problems (%s)" % problems)
check(index["by_key"][KEY_A] == name_a and index["by_key"][KEY_B] == name_b,
      "the index maps each key to its own file")

found_a = E.locate(str(folder), KEY_A, "Fisher, Jordan")
found_b = E.locate(str(folder), KEY_B, "Fisher, Jordan")
check(found_a.exists and os.path.basename(found_a.path) == name_a, "locate finds the first Fisher")
check(found_b.exists and os.path.basename(found_b.path) == name_b, "locate finds the second Fisher")
check(found_a.path != found_b.path, "the two lookups do not land on one file")
refuses(lambda: E.verify_note(E.read_note(folder / name_a), KEY_B),
        "opening one Fisher's file for the other Fisher's key refuses", "wrong-file")
refuses(lambda: E.verify_note(E.read_note(folder / name_a), KEY_A,
                              {"registered": "2021-11-30"}, ("registered",)),
        "the right key with the wrong identity field refuses", "identity-mismatch")
check(E.verify_note(E.read_note(folder / name_a), KEY_A,
                    {"registered": "2019-04-02"}, ("registered",)),
      "the right key with the right identity passes")

# A stale index must not be able to point a fact anywhere. Break it and watch the folder heal.
broken = E.load_index(str(folder))
broken["by_key"][KEY_A] = "Someone Else - SAP-ACME-0001.md"
E.save_index(str(folder), broken)
healed = E.locate(str(folder), KEY_A, "Fisher, Jordan")
check(healed.exists and healed.how == "filename" and os.path.basename(healed.path) == name_a,
      "a stale index falls through to the filename and finds the right file")

# The name on the record changed. Same key, so the same file, renamed rather than duplicated.
E.save_index(str(folder), E.rebuild_index(str(folder))[0])
renamed = E.locate(str(folder), KEY_A, "Fisher, Jordan M.")
check(renamed.exists and renamed.rename_from and
      os.path.basename(renamed.rename_from) == name_a and
      os.path.basename(renamed.path) == "Fisher Jordan M. - SAP-ACME-4471.md",
      "a changed spelling is a rename of the same file, not a second file")

# Two files claiming one key is a problem a person settles, not something to pick a winner for.
shutil.copyfile(folder / name_a, folder / ("Copy of - %s.md" % KEY_A))
_index, problems = E.rebuild_index(str(folder))
check(any("two files claim" in p for p in problems), "a duplicate key is reported (%s)" % problems)
os.unlink(folder / ("Copy of - %s.md" % KEY_A))

# ------------------------------------------------------------------ 3. frontmatter round trip

ORIGINAL = """---
type: entity
entity_kind: supplier
entity_key: SAP-ACME-4471
entity_keys: [SAP-ACME-4471, SAP-ACME-9902]
display: "Fisher, Jordan"
aliases: []
class: company
created: 2026-06-14
updated: 2026-06-14
read_at: 2026-09-07T18:22:41-0400
read_on: 2026-09-07
last_read_complete: true
encounters: 3
rating: 4.5
# a comment somebody left on the line below
terms:
  - "Net 30"
  - "FOB origin"
future_key_nobody_here_knows: kept
nested_thing_this_parser_cannot_read:
  depth: 2
  who: "someone later"
---

# Fisher, Jordan — SAP-ACME-4471

body text
"""
note = E.parse_note(ORIGINAL)
check(note.fm.get("entity_keys") == ["SAP-ACME-4471", "SAP-ACME-9902"], "an inline list parses")
check(note.fm.get("terms") == ["Net 30", "FOB origin"], "a block list parses")
check(note.fm.get("display") == "Fisher, Jordan", "a quoted string keeps its comma")
check(note.fm.get("encounters") == 3 and note.fm.get("rating") == 4.5, "numbers parse as numbers")
check(note.fm.get("last_read_complete") is True, "a boolean parses as a boolean")
check(note.fm.get("read_on") == "2026-09-07" and note.fm.get("read_at").endswith("-0400"),
      "a date and a stamp stay strings")
check(note.fm.is_opaque("nested_thing_this_parser_cannot_read"),
      "a nested mapping is marked as not understood rather than mangled")
check(note.fm.get("future_key_nobody_here_knows") == "kept", "an unknown scalar key parses")

note.fm.set("updated", "2026-09-08")
round_tripped = E.render_note(note)
for line in ("future_key_nobody_here_knows: kept",
             "nested_thing_this_parser_cannot_read:", "  depth: 2", '  who: "someone later"',
             "# a comment somebody left on the line below",
             '  - "Net 30"', "rating: 4.5", 'display: "Fisher, Jordan"',
             "read_at: 2026-09-07T18:22:41-0400", "entity_keys: [SAP-ACME-4471, SAP-ACME-9902]"):
    check(line in round_tripped, "an older writer keeps %r exactly as it found it" % line)
check("updated: 2026-09-08" in round_tripped and "updated: 2026-06-14" not in round_tripped,
      "the one key that was set is the one key that changed")
check(round_tripped.replace("updated: 2026-09-08", "updated: 2026-06-14") == ORIGINAL,
      "everything else is byte for byte what it was")
check(list(E.parse_note(round_tripped).fm.keys()) == list(note.fm.keys()),
      "the key order survives the round trip")

# What we write must read back as what we meant, quoting included.
fm = E.Frontmatter()
fm.set("room", "308-B")
fm.set("home", "Fort Tryon")
fm.set("display", "Camacho, Rosa")
fm.set("dob", "1948-03-02")
fm.set("bims_on", "2026-08")
fm.set("code_status", "DNR")
fm.set("providers", ["[[Bridgette Calderon, NP]]"])
fm.set("aliases", [])
fm.set("wound_active", True)
fm.set("abi_left", 0.91)
fm.set("count", 12)
rendered = fm.render()
for want in ('room: "308-B"', "home: Fort Tryon", 'display: "Camacho, Rosa"', "dob: 1948-03-02",
             'bims_on: "2026-08"', "code_status: DNR", 'providers: ["[[Bridgette Calderon, NP]]"]',
             "aliases: []", "wound_active: true", "abi_left: 0.91", "count: 12"):
    check(want in rendered, "renders %r" % want)
back = E.parse_note("---\n%s---\n" % rendered).fm
for key in ("room", "home", "display", "dob", "bims_on", "code_status", "wound_active",
            "abi_left", "count", "providers", "aliases"):
    check(back.get(key) == fm.get(key), "%s survives its own round trip (%r vs %r)"
          % (key, back.get(key), fm.get(key)))
long_list = ["Aspirin 81 mg - once daily", "Atorvastatin 40 mg - nightly", "Eliquis 5 mg - twice daily"]
fm.set("meds", long_list)
check("meds:\n  - " in fm.render(), "a list too long for one line renders as a block")
check(E.parse_note("---\n%s---\n" % fm.render()).fm.get("meds") == long_list,
      "the block list reads back as the same list")
fm.set("names", ["Camacho, Rosa", "O'Brien, Mary"])
check(E.parse_note("---\n%s---\n" % fm.render()).fm.get("names") == ["Camacho, Rosa", "O'Brien, Mary"],
      "a list item containing a comma does not read back as two items")
check(E.parse_note("no frontmatter here\n").fm.keys() == [], "a note with no frontmatter is not an error")
refuses(lambda: E.parse_note("---\nopen: yes\nand never closed\n"),
        "a frontmatter block that never closes refuses", "bad-note")

# ------------------------------------------------------------------ 4. the interrupted write

target = folder / name_a
before_bytes = target.read_bytes()
killer = work / "killer.py"
killer.write_text(
    "import os, signal, sys\n"
    "sys.path.insert(0, %r)\n"
    "import entity_note as E\n"
    "os.replace = lambda a, b: os.kill(os.getpid(), signal.SIGKILL)\n"
    "E.atomic_write(%r, 'THIS MUST NEVER BE VISIBLE\\n' * 500)\n" % (str(HELPER_DIR), str(target)),
    encoding="utf-8")
killed = subprocess.run([sys.executable, str(killer)], capture_output=True,
                       env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
check(killed.returncode == -9, "the child really was killed mid-write (rc=%s)" % killed.returncode)
check(target.read_bytes() == before_bytes, "the note is exactly what it was before the interrupted write")
leftovers = [p.name for p in folder.iterdir() if p.name.startswith(".entity-note.")]
check(leftovers, "the half-written file did exist (it is the temp, %s)" % leftovers)
check(all(not p.name.endswith(".md") for p in folder.iterdir() if p.name.startswith(".")),
      "nothing left behind reads as a note")
_index, problems = E.rebuild_index(str(folder))
check(not problems, "the rebuild ignores the leftover temp file (%s)" % problems)
for name in leftovers:
    os.unlink(folder / name)

check(oct(os.stat(target).st_mode)[-3:] == "600", "a note is written 0600, like the rest of the repo")

# ------------------------------------------------------------------ 5. no notes folder at all

empty_env = {"HOME": str(work / "nobody")}
refuses(lambda: E.notes_root(empty_env), "no notes folder anywhere refuses in words", "needs-a-person")
try:
    E.notes_root(empty_env)
except E.Refusal as refusal:
    check("OBSIDIAN_VAULT_PATH" in refusal.error and "nothing was written" in refusal.error,
          "the refusal names the key that is missing and says nothing was written")
check(not (work / "nobody").exists(), "a refusal creates no folder anywhere")

not_a_folder = work / "a-file"
not_a_folder.write_text("x", encoding="utf-8")
refuses(lambda: E.notes_root({"OBSIDIAN_VAULT_PATH": str(not_a_folder), "HOME": str(work / "nobody")}),
        "OBSIDIAN_VAULT_PATH pointing at something that is not a folder refuses")
resolved = E.notes_root({"OBSIDIAN_VAULT_PATH": str(work)})
check(resolved.path == str(work) and resolved.source == "OBSIDIAN_VAULT_PATH" and not resolved.note,
      "the configured notes folder is used with nothing to say about it")
workspace = work / "workspace"
workspace.mkdir()
resolved = E.notes_root({"ISTA_WORKSPACE": str(workspace), "HOME": str(work / "nobody")})
check(resolved.path == str(workspace / "Notes") and "OBSIDIAN_VAULT_PATH is not set" in resolved.note,
      "the workspace fallback says out loud that it was a fallback")

# ------------------------------------------------------------------ 6. sections, blocks, diff

body = "# Fisher, Jordan\n\n## Encounters\n"
body, added = E.append_section(body, "2026-06-14 — first look", "**Terms** — Net 30.")
check(added, "the first section is added")
body, added_again = E.append_section(body, "2026-06-14 — first look", "**Terms** — Net 60.")
check(not added_again, "appending the same heading twice does nothing")
check(body.count("Net 30") == 1 and "Net 60" not in body, "and it does not overwrite what was there")
body, _ = E.append_section(body, "2026-09-07 — second look", "**Terms** — Net 30.",
                           section_id="read-2026-09-07")
body, again = E.append_section(body, "2026-09-07 — second look (again)", "different heading",
                               section_id="read-2026-09-07")
check(not again, "a repeated section id is refused even under a different heading")
titles = [s.title for s in E.sections(body)]
check(titles == ["2026-06-14 — first look", "2026-09-07 — second look"],
      "the sections are in file order, oldest first (%s)" % titles)
check(E.section_dates(body) == ["2026-06-14", "2026-09-07"], "the section dates read off the headings")
check(body.index("first look") < body.index("second look"), "a new section goes at the end")

fenced = body + "\n### 2026-09-08 — with a code sample\n\n```\n### not a heading\n```\n"
check(len(E.sections(fenced)) == 3, "a heading inside a code fence is not a section")

body, _ = E.set_block(body, "carry-forward", "Line one.", start_note="regenerated on every write",
                      insert_before="## Encounters")
check(body.index("carry-forward:start") < body.index("## Encounters"),
      "the block goes where it was asked to go")
body, replaced = E.set_block(body, "carry-forward", "Line two.")
check(replaced and "Line two." in body and "Line one." not in body, "the block regenerates")
check("regenerated on every write" in body, "the prose in the opening marker survives regeneration")
check(body.count("first look") == 1 and body.index("first look") > body.index("carry-forward:end"),
      "everything after the end marker is untouched")

fm = E.starter_frontmatter("supplier", KEY_A, "Fisher, Jordan", "company", "record", "sap")
E.set_read(fm, "2026-09-07T18:22:41-0400")
check(fm.get("read_on") == "2026-09-07" and fm.get("read_at") == "2026-09-07T18:22:41-0400",
      "read_on is the first ten characters of the stamp, never typed by hand")
refuses(lambda: E.set_read(fm, "sometime yesterday"), "a stamp that is not a stamp refuses", "bad-note")
E.sync_counters(fm, body)
check(fm.get("encounters") == 2 and fm.get("first_encounter") == "2026-06-14"
      and fm.get("last_encounter") == "2026-09-07", "the counters are counted off the body")

rows = {c.field: c for c in E.changes(
    {"terms": "Net 30", "contact": "Ana", "rating": 4.5, "sites": []},
    {"terms": "Net 45", "rating": 4.5, "insurer": "Zurich", "sites": []})}
check(rows["terms"].kind == "changed" and rows["terms"].was == "Net 30", "a changed field says both values")
check(rows["contact"].kind == "removed", "a field that went away says removed")
check(rows["insurer"].kind == "added", "a new field says added")
check(rows["rating"].kind == "same", "a field that did not change still gets a row")
check(rows["sites"].kind == "same", "an empty list is a value, not an absence")
check([c.field for c in E.changes({}, {}, fields=["a", "b"])] == ["a", "b"],
      "asking for fields gives a row per field even when both sides are silent")
check(E.days_between("2026-06-12", "2026-08-26") == 75, "the interval arithmetic is right")
check(E.days_between("last June", "2026-08-26") is None, "an unparsable date is not comparable")

banner = E.staleness_banner("2026-09-07", "the supplier portal", today_="2026-09-08")
check(banner.startswith("> [!warning]") and "2026-09-07" in banner, "a fresh read gets a warning callout")
old = E.staleness_banner("2026-06-01", "the supplier portal", today_="2026-09-08")
check(old.startswith("> [!danger]") and "99 days ago" in old,
      "a read older than thirty days names the number of days in a danger callout")

# ------------------------------------------------------------------ 7. the command line

def cli(*args):
    return subprocess.run([sys.executable, str(HELPER_DIR / "entity_note.py"), *args],
                          capture_output=True, text=True,
                          env={**os.environ, "OBSIDIAN_VAULT_PATH": str(work),
                               "PYTHONDONTWRITEBYTECODE": "1"})

out = cli("filename", "Camacho, Rosa", KEY, "--json")
check(out.returncode == 0 and json.loads(out.stdout)["filename"] == "Camacho Rosa - %s.md" % KEY,
      "the command line builds a filename")
out = cli("key", "pcc", "UNKNOWN", "C1", "--json")
check(out.returncode == 0 and json.loads(out.stdout)["ok"] is False,
      "a refusal on the command line still exits 0, like every other tool here")
out = cli("where", "--json")
check(json.loads(out.stdout)["path"] == str(work), "the command line resolves the notes folder")

# --- the board ------------------------------------------------------------------------------
# The renderer draws a page from a spec, and the spec is where every word from a subject lives. The
# grep below is the check that keeps that true, and it is the one most likely to be deleted by
# somebody in a hurry to ship a column: if it fails, the fix is to move the word into your own
# spec, never to widen this list.
board_dir = pathlib.Path(tempfile.mkdtemp(prefix="entity-board-"))
# The checks themselves run in a temp folder, which is exactly the place the renderer refuses to
# write to. The escape hatch is set for the runs that are only proving the drawing; the refusal
# itself is checked below with the hatch deliberately removed from the environment.
BOARD_ENV = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "ENTITY_BOARD_ALLOW_TMP": "1"}
out_html = board_dir / "demo.html"
run = subprocess.run([sys.executable, str(HELPER_DIR / "board.py"), "--demo",
                      "--out", str(out_html), "--as-of", "2026-09-08"],
                     capture_output=True, text=True,
                     env=BOARD_ENV)
check(run.returncode == 0 and out_html.exists(),
      "board.py --demo writes a page and exits 0 (%s)" % run.stdout.strip())
page = out_html.read_text(encoding="utf-8") if out_html.exists() else ""
check("Content-Security-Policy" in page, "the page carries the CSP that keeps it offline")
body = page.replace('<meta http-equiv="Content-Security-Policy"', "")
body = body[:body.index("content=\"default-src")] + body[body.index("base-uri 'none'\">"):] if "default-src" in body else body
check("http://" not in body and "https://" not in body,
      "nothing in the page reaches a network origin")
for word in ("localStorage", "sessionStorage", "indexedDB"):
    check(word not in page, "the page keeps nothing in the browser (%s)" % word)
check(oct(out_html.stat().st_mode)[-3:] == "600", "the page is written 0600")

# A group head the filter hides must actually go. An author rule beats the browser's own
# [hidden]{display:none} whatever the specificity, so .grp{display:flex} kept every emptied group
# heading on the page with nothing under it, over a stale row count.
check("[hidden]{display:none!important}" in page,
      "an author [hidden] rule outranks the display rules the filter has to beat")
check('class="gcount"' in page and 'c.dataset.total' in page,
      "a group head's row count is rewritten by the filter rather than frozen at render time")

refused = subprocess.run([sys.executable, str(HELPER_DIR / "board.py"), "--demo",
                          "--out", "/tmp/entity-board-should-refuse.html"],
                         capture_output=True, text=True,
                         env={k: v for k, v in os.environ.items() if k != "ENTITY_BOARD_ALLOW_TMP"})
check(refused.returncode == 0 and refused.stdout.startswith("ERROR:")
      and not os.path.exists("/tmp/entity-board-should-refuse.html"),
      "an --out under /tmp is refused in words, and nothing is written")

bad_spec = board_dir / "spec2.json"
bad_spec.write_text(json.dumps({"spec": 2, "title": "x"}))
out = subprocess.run([sys.executable, str(HELPER_DIR / "board.py"), "--spec", str(bad_spec),
                      "--vault", str(board_dir), "--out", str(board_dir / "x.html")],
                     capture_output=True, text=True, env=BOARD_ENV)
check(out.stdout.startswith("ERROR:") and "2" in out.stdout and "1" in out.stdout,
      "a spec integer this renderer does not know is a refusal naming both numbers")
out = subprocess.run([sys.executable, str(HELPER_DIR / "board.py"), "--spec-version"],
                     capture_output=True, text=True)
check(out.stdout.strip() == "1", "--spec-version prints what this copy draws")

empty = board_dir / "empty"
empty.mkdir()
out = subprocess.run([sys.executable, str(HELPER_DIR / "board.py"), "--spec",
                      str(HELPER_DIR / "boards" / "entities.board.json"), "--vault", str(empty),
                      "--out", str(board_dir / "none.html")], capture_output=True, text=True,
                     env=BOARD_ENV)
check(out.returncode == 0 and (board_dir / "none.html").exists(),
      "an empty folder still draws a page rather than failing")

SUBJECT_WORDS = ("wound", "patient", "resident", "anticoagul", "medication", "diagnos",
                 "clinical", "pcc", "pointclickcare", "icd", "provider", "chart")
for rel in ["board.py", "references/BOARD-SPEC.md", "boards/entities.board.json"] + \
           ["boards/demo/Suppliers/" + f for f in sorted(os.listdir(HELPER_DIR / "boards" / "demo" / "Suppliers"))]:
    text = (HELPER_DIR / rel).read_text(encoding="utf-8").lower()
    hit = [w for w in SUBJECT_WORDS if w in text]
    check(not hit, "%s carries no word from any one subject (%s)" % (rel, ", ".join(hit)))

shutil.rmtree(board_dir, ignore_errors=True)
shutil.rmtree(HELPER_DIR / "__pycache__", ignore_errors=True)

shutil.rmtree(work, ignore_errors=True)
shutil.rmtree(HELPER_DIR / "__pycache__", ignore_errors=True)   # nothing under skills/ but shipped files
check(not (HELPER_DIR / "__pycache__").exists(), "the checks leave no __pycache__ beside the helper")

if failures:
    print("\n".join("FAIL %s" % f for f in failures))
    print("%d of %d checks failed" % (len(failures), checks))
    sys.exit(1)
print("ok: entity-notes helper, %d checks" % checks)
