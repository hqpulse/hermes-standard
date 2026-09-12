---
name: entity-notes
description: "Entity notes: one running file per thing you meet more than once - a supplier, a customer, a site, a candidate, a machine, a case - with frontmatter, a dated section per encounter, and a what-changed-since-last-time. Use when you are about to look something up that you have looked up before, or when the person asks what has changed since last time."
---

# Entity notes

An entity note is one markdown file per THING you deal with again and again, so the second time
starts with what happened the first time instead of a blank page.

The note types the assistant-standard skill lists cover things that happen once: a meeting, a
decision, a commitment. An entity note is for a thing that keeps coming back and whose history is the point.
Same file, appended to, for years.

Use it when all three are true: you meet this thing repeatedly, you read it from a system rather
than being told about it, and last time's detail changes what you do this time. One-off? Write an
ordinary note instead.

## Five rules. None of them is negotiable.

1. **The note is a memory, never a source.** A cached record is a stale record. Always read the live
   system for today's facts; the note supplies continuity only - what we did last time, the trend,
   what moved. Every fact in the file carries the date it was true and where it came from. If the
   note and the system disagree, the system wins and the note is corrected forward.
2. **Retrieval is an exact lookup, never a search.** Key in, file out. No embeddings, no vector
   search, no fuzzy match, no `grep` for a name, not even the Obsidian search: two things that look
   alike to a search are exactly the pair you must never confuse, and writing one entity's fact into
   another's file is the worst thing this can do.
3. **One file per thing, and a fact only ever goes in the file it came from.** Every write takes the
   entity's key and verifies it against the open file first. Every time, including when the index
   said so.
4. **The file goes where its class says and nowhere else.** An entity note carries a `class` like
   every other note. It is never mirrored, posted, summarised into a shared note, or put into memory
   above what the class allows. See the confidentiality table in the assistant-standard skill.
5. **Nothing is invented.** A thing the record does not have is written as absent, with the date we
   looked. "We could not look" and "the record does not say" are two different facts and live in two
   different blocks. Never a guessed value, never a zero standing in for a missing number.

## Where the files live

The notes folder is `OBSIDIAN_VAULT_PATH` - the same folder the engine's Obsidian skill uses, set on
every pod. The helper resolves it: that variable, then the workspace's `Notes` folder, then `~/Notes`
on a development box, and if none of those is there it refuses in words rather than inventing a
folder somewhere nobody will look.

One folder per kind, named by you in plain English - `Suppliers/`, `Customers/`, `Sites/`. The helper
does not pluralise a kind for you, because guessing that a "facility" lives in "Facilitys" is how one
set of notes ends up split across two folders.

A filename is `<Name> - <KEY>.md`, for example `Fisher Jordan - SAP-ACME-4471.md`. The name half is
for humans; the KEY half is what makes it unique and is recovered from the filename with one split.
The whole rule is in `references/SCHEMA.md`.

Say "the notes folder", not "the vault", in anything you write or print. On some cells "the vault" is
the credential store, and a refusal that says vault reads as a password problem.

## The shape of the file

Frontmatter, then a regenerated block at the top, then dated sections appended for ever.
`references/SCHEMA.md` has every field and what it means. The short version:

- **Frontmatter** carries `type: entity`, `entity_kind`, `entity_key`, `entity_keys`, `display`,
  `class`, `source`, `source_system`, the dates, and whatever facts your kind of thing has. The
  contract: **every field is as of `read_on`, unless it is paired with its own `*_on` date.** A fact
  whose age matters and that has no `*_on` partner does not belong in frontmatter at all.
- **The banner** is the first prose in the file: a callout saying this is a memory and not the
  record, naming the date of the last read. Past thirty days it turns into a danger callout that
  opens with the number of days. Regenerated on every write.
- **Carry forward** is the only body text a writer may overwrite. It holds what we handed over last
  time, verbatim, and a short "worth a look before the next time" list, every line carrying a date.
  It sits between `<!-- carry-forward:start -->` and `<!-- carry-forward:end -->`.
- **Encounters** are `###` sections, oldest first, appended to the end and **never edited**. That is
  what makes the file an audit trail rather than a cache: a wrong write stays visible and dated, and
  two appends cannot corrupt each other. Each section says where it was read and when, then the
  facts, then **What changed since <date>**, then **Not recorded** and **Could not be read**.
- **Corrects this file** is appended when today's read contradicts what the file says. The old
  section is left exactly as written. Only the frontmatter, the banner and Carry forward move. A
  memory that quietly rewrites its own past cannot be audited.

Every line in the body either carries a date or opens with where it came from. A body line in the
bare present tense is a defect: it is the line that gets read out of context in six months and
believed.

Links point OUT of the stricter file into the looser one - an entity note links to the person and
site notes, and those never name the entity back. Obsidian's backlinks give you the reverse edge for
nothing, without spreading a confidential detail into files that are not held as tightly.

## The helper

`entity_note.py`, next to this file. Standard library only, importable or runnable:

    python3 entity_note.py where
    python3 entity_note.py key sap acme 4471
    python3 entity_note.py filename "Fisher, Jordan" SAP-ACME-4471
    python3 entity_note.py show "<folder>/Fisher Jordan - SAP-ACME-4471.md"
    python3 entity_note.py rebuild-index "<folder>"

It refuses in words and still exits 0, like every other tool here. What it owns, so that nobody
writes a second version of it:

| Function | What it settles |
|---|---|
| `notes_root()`, `entity_folder()` | where the notes are, once, for everybody |
| `clean_name()`, `entity_key()`, `note_filename()`, `key_from_filename()` | the filename rule, total and reversible |
| `parse_note()`, `render_note()`, `read_note()`, `write_note()` | frontmatter that keeps keys it has never heard of |
| `atomic_write()` | temp file plus rename, 0600, so a note is never half written |
| `sections()`, `find_section()`, `append_section()`, `section_dates()` | reading a note back into its parts, appending without touching what is above |
| `set_block()`, `make_block()`, `staleness_banner()` | the regenerated block and the banner |
| `changes()` | added, removed, changed, and **same** - a row per field, always |
| `locate()`, `verify_note()`, `load_index()`, `rebuild_index()` | exact lookup, and the guard that stops a fact landing in the wrong file |
| `starter_frontmatter()`, `set_read()`, `sync_counters()`, `days_between()` | the frontmatter contract in one place |

Two habits worth copying. `changes()` returns a `same` row rather than nothing, so your "what
changed" list can never be silent about something nobody looked at - write the line either way.
`set_read()` copies the record's own read stamp verbatim and derives the date from it, because a
writer that stamps its own clock claims a freshness the read did not have.

**Calling it from a plugin.** A plugin installed alongside this pack sits at
`<pack>/plugins/<name>/`, so from anywhere inside the plugin the helper is up the tree at
`<pack>/skills/entity-notes/entity_note.py` - on a pod,
`/opt/data/profiles/hermes-standard/skills/entity-notes/entity_note.py`. Walk up, then fall back:

    import os, sys
    REL = os.path.join("skills", "entity-notes", "entity_note.py")

    def _helper():
        here = os.path.dirname(os.path.abspath(__file__))
        for _ in range(8):                       # plugins/<name>/tools/<role>/ is four up from a tool
            if os.path.isfile(os.path.join(here, REL)):
                return os.path.join(here, REL)
            parent = os.path.dirname(here)
            if parent == here:
                break
            here = parent
        for cand in (os.environ.get("ENTITY_NOTE_HELPER"),
                     "/opt/data/profiles/hermes-standard/" + REL):
            if cand and os.path.isfile(cand):
                return cand
        return ""                                # the pack is older than this plugin, or not installed

If it comes back empty, or `entity_note.API_VERSION` is lower than the version you were told about,
say so in one line and do the simple thing. Do not reimplement the filename rule or the lookup: two
implementations of those is the wrong-file bug arriving by another road. API_VERSION is 1 today.

## This sits ON the Obsidian skill, not beside it

The engine already ships a skill that reads, searches and creates markdown notes with wikilinks in
`OBSIDIAN_VAULT_PATH`. Use it for all of that. This skill adds only what it does not have:
frontmatter as a contract, dated sections, the regenerated block, a computed what-changed, and an
index. Before you write anything that touches a markdown file, check whether that skill already does
the job. Two ways to write into one folder is how two files for one thing appear.

The one place you must NOT use it is retrieval: finding which file an entity belongs to is `locate()`
and an exact key, never a search over the folder.

## A supplier, end to end

    Suppliers/Fisher Jordan - SAP-ACME-4471.md

    ---
    type: entity
    entity_kind: supplier
    entity_key: SAP-ACME-4471
    entity_keys: [SAP-ACME-4471]
    display: "Fisher, Jordan"
    class: company
    source: record
    source_system: sap
    created: 2026-06-14
    updated: 2026-09-07
    read_at: 2026-09-07T18:22:41-0400
    read_on: 2026-09-07
    last_read_complete: true
    encounters: 2
    first_encounter: 2026-06-14
    last_encounter: 2026-09-07
    terms: "Net 45"
    contact: "[[Ana Ferreira]]"
    site: "[[Bermondsey yard]]"
    open_dispute: false
    ---

    # Fisher, Jordan — SAP-ACME-4471

    <!-- carry-forward:start — regenerated on every write; everything below carry-forward:end is append-only -->
    > [!warning] This file is a memory, not a record.
    > Last read from the supplier ledger on 09/07/26. This banner was written on 09/07/26 and does
    > not count the days again when the file is opened, so work that age out before you use anything
    > below it.
    > Nothing on this page is today's record. Read the record live before you act on it; where this
    > file and the record disagree the record wins and a correction is appended below.

    ## Carry forward

    - Terms went from Net 30 on 06/14/26 to Net 45 on 09/07/26. The ledger does not say who agreed it.
    - Two late deliveries logged on 08/12/26 and 08/29/26. Nothing raised with them yet.
    - Last thing we said: we would confirm the yard address by the end of the month, on 06/14/26.
    <!-- carry-forward:end -->

    ## Encounters

    ### 2026-06-14 — first look — [[Ana Ferreira]]

    - Read live from the supplier ledger at 2026-06-14T17:41:08-0400. All four screens answered.

    **Terms** — Net 30, per the ledger read 06/14/26.
    **Deliveries** — none logged as late, per the ledger read 06/14/26.

    **What changed** — first look at this supplier; nothing to compare.

    **Not recorded** — no bank details on file; no signed framework agreement.

    **Could not be read** — nothing.

    ### 2026-09-07 — quarterly check — [[Ana Ferreira]]

    - Read live from the supplier ledger at 2026-09-07T18:22:41-0400. The disputes screen timed out.

    **Terms** — Net 45, per the ledger read 09/07/26.
    **Deliveries** — two late, 08/12/26 and 08/29/26, per the ledger read 09/07/26.

    **What changed since 06/14/26**
    - Terms: Net 30 on 06/14/26 -> Net 45 on 09/07/26. No reason recorded.
    - Deliveries: none late on 06/14/26 -> two late, most recent 08/29/26.
    - Contact: no change.

    **Not recorded** — still no bank details; no reason given for the terms change.

    **Could not be read** — the disputes screen timed out, so "no open dispute" below means we could
    not look, not that there is none.

`vault/Entities.base` is the board over all of these: one row per entity, with days since the last
read next to every fact, and a view for the ones nobody has read in a month. Copy it into the notes
folder root and filter it by `entity_kind` for a board of one kind.

## The board

Obsidian gives you a table over these notes (`vault/Entities.base`). `board.py` gives you the same
thing as one self-contained HTML page, for the times there is no Obsidian: a pod with no browser, a
page mailed to a laptop, a sheet somebody prints and carries.

    python3 board.py --spec boards/entities.board.json --vault "$OBSIDIAN_VAULT_PATH" \
                     --out "$HOME/board/entities.html"

    python3 board.py --demo --out /some/where/demo.html     # five made-up suppliers

It reads the notes, groups them, draws the state words as pills, sparklines any series you point it
at, and - the reason it exists - fades every row as its read date recedes, so a file last read in
May cannot look like a file read this morning. Columns, groups, tiles, sections, colours and the
staleness ladder all come out of the spec, which is yours to write: `references/BOARD-SPEC.md` has
every key.

Three things worth knowing before you use it:

- **It draws nothing it was not given.** A key that is absent draws an em dash meaning "nobody
  looked"; a key holding the spec's `absent_word` draws those words. Rule 5, on a screen.
- **The page cannot reach the network.** A Content-Security-Policy meta forbids every origin, and
  nothing is kept in the browser - no `localStorage`, no cookie. A board can carry confidential rows.
- **It writes and stops.** It refuses an `--out` under `/tmp`, writes the file 0600, and has no way
  to send it anywhere. Delivering a board is the caller's decision and the caller's tool.

A plugin with its own vocabulary ships its own spec and, when it has to work a value out, its own
row builder; the renderer stays generic. That is the seam. If you find yourself wanting to teach
`board.py` a word from your subject, the word belongs in your spec.
