# The entity note, field by field

One markdown file per thing an agent meets more than once. Generic: a supplier, a customer, a site,
a candidate, a machine, a case. A specialised layer adds its own fields on top and never changes the
meaning of the ones here.

## Frontmatter

**The contract, stated once: every field is as of `read_on`, unless it is paired with its own `*_on`
date.** `terms`, `contact`, `status` are as of the last read. `price_agreed_on`, `inspected_on`,
`certified_on` carry their own, because those facts age on a clock of their own - a fresh read of a
three-month-old inspection is still a three-month-old inspection, and that distinction is where this
file earns its keep. A field whose age matters and that has no `*_on` partner is a hole in your
schema, not a field to add.

### The generic block. Every entity note has these.

The table is the order they are read in, not an order the file has to be in: a board reads
keys by name, and a writer that reshuffled the frontmatter on every save would make every
change to a note unreadable in a diff.

| key | example | why |
|---|---|---|
| `type` | `entity` | Marks the shape. Every board filters on it first. Deliberately not a new type per domain, so one table can hold every kind of thing an agent tracks. |
| `entity_kind` | `supplier` | The one word that says what kind of thing this is. A board filters `type == "entity" && entity_kind == "supplier"`. This is the seam a specialised layer hangs off. |
| `entity_key` | `SAP-ACME-4471` | The exact-lookup key and the second half of the filename: `<system>-<tenant>-<record number>`. Nothing is written into the file until the payload's computed key equals this (or is in `entity_keys`). The wrong-file guard, in one field. |
| `entity_keys` | `[SAP-ACME-4471, SAP-BETA-88]` | Every key this file answers to, the anchor first - the anchor is the one the filename carries. A second key appears only on a proven merge. Without this field, a thing that moved between systems silently becomes two memories. |
| `display` | `"Fisher, Jordan"` | The name as the record writes it. The filename's name half is a cleaned-up derivative; this is the original, so nothing is lost to the filename rules. |
| `aliases` | `["Fisher Jordan - SAP-BETA-88"]` | Obsidian's alias list, and it holds ONLY previous filenames after a rename or a merge. Never a friendly spelling of the name: two things can share a name, and an alias is exactly how a link resolves silently to the wrong one. |
| `class` | `company` | The confidentiality class, from the assistant-standard table. It decides where this file may go. No default: a defaulted class is one nobody chose. |
| `source` | `record` | How we came by the facts: `chat`, `voice`, `mail`, `calendar`, `file`, or `record` for a system read directly. It matters - a dictated fact is somebody's account of the thing, a read fact is the record. |
| `source_system` | `sap` | Which door read it. With the tenant it reconstructs `entity_key`, so the key is never the only copy of its own parts. |
| `created` | `2026-06-14` | The day this file was first written. |
| `updated` | `2026-09-07` | Any write, including a rename or a frontmatter correction with no new encounter. Not the same as `read_on`, and the difference is the point. |
| `read_at` | `2026-09-07T18:22:41-0400` | The live read that produced the newest facts, copied VERBATIM from the payload. Never re-formatted, never re-stamped by the writer's own clock. |
| `read_on` | `2026-09-07` | The first ten characters of `read_at`, never typed by hand. Boards sort and do date arithmetic far more reliably on a plain date than on a stamp with an offset, and every staleness view keys on this. |
| `last_read_complete` | `true` | False when the last read had a refused screen or a door that did not answer. A false here means the absences in the newest section are "we could not look", not "the record does not say". |
| `needs_a_person` | `false` | True when the last attempt could not be completed at all. It is the board column that tells a human where the automation stopped. |
| `encounters` | `3` | How many dated sections the body holds. A cheap board column and a checksum: counted off the headings, so if it disagrees with what a writer expected, the file has been hand-edited. |
| `first_encounter` | `2026-06-14` | Date of the oldest section. How long this thing has been ours. |
| `last_encounter` | `2026-09-07` | Date of the newest section. Usually equals `read_on`, deliberately separate: a section can be appended with no fresh read, and then this moves and `read_on` does not. |

### Your own fields

Add what your kind of thing has, and follow four rules.

1. Pair anything whose age matters with its own `*_on`.
2. Keep laterality, side, units and any qualifier INSIDE the string. Two facts in one field is how a
   side gets lost; a field per side is how it is kept.
3. Store what the record said, verbatim. Do not map a value onto a house list, do not compute an
   area from two dimensions, do not turn "3 months" into a date. A derived number on a board is read
   as a measurement, and a computed date is read as a decision somebody made.
4. Some facts must NOT be in frontmatter at all. Anything that would read as a current fact at a
   glance and would be dangerous if stale belongs inside a dated section, behind its read date. A
   board renders frontmatter as a table with no dates attached; that is the whole risk.

## The body

    # <Display> — <ENTITY KEY>          one line, rewritten only by a rename or a merge
    <!-- carry-forward:start ... -->
    > [!warning] the staleness banner    regenerated, first prose in the file
    ## Carry forward                     regenerated, the only body text a writer overwrites
    <!-- carry-forward:end -->
    ## Encounters                        container heading, no prose
    ### YYYY-MM-DD — <kind> — [[Who]]    one per encounter, OLDEST FIRST, appended, immutable

The H1 carries the key because a chunk of this file pasted into a chat or a model's context has to
name whose it is; a filename does not travel with the text.

Under each `###` section, in this order:

- one bullet saying where it was read and when (the verbatim stamp), and whether everything answered;
- the facts, one short block per element, each opening with where it came from and its date;
- **What changed since <date>** - one line per element of the comparable set, naming BOTH dates and
  BOTH values, with "no change" written out for the ones that did not move and the reason written out
  for the ones that could not be compared. Silence is banned: every element gets a line every time,
  so "nothing said about it" can never mean "nobody looked";
- **Not recorded** - the elements your template asks for that this record does not have. An absence
  is a written fact with a date. If there are none, say so;
- **Could not be read** - the doors that did not answer, with the reason. Kept rigidly apart from
  Not recorded: one means the record is silent, the other means we were blind. A non-empty block here
  sets `last_read_complete: false`;
- **Corrects this file** - only when today's read contradicts what the file already says. Name the
  old value, the section that carries it, today's value, and the frontmatter key that moved. The old
  section is not edited.

Interval arithmetic - days between two dates - is the only arithmetic allowed in the body.

## The filename

    <Folder>/<NAME> - <KEY>.md
    Suppliers/Fisher Jordan - SAP-ACME-4471.md

NAME, from the record's own spelling:

1. Unicode NFC normalise, so one name from two sources is one filename.
2. Drop commas. Family name first still sorts like a roster.
3. Replace every character in `/ \ : * ? " < > | # ^ [ ] %` and every control or invisible character
   with one space. Those are the ones a filesystem refuses or a wikilink chokes on.
4. Collapse whitespace runs, trim, drop a leading dot (it would hide the note).
5. Apostrophes, hyphens and accents SURVIVE: `O'Brien Mary`, `Vandermeer-Katz Teresa`, `Muñoz Ana`.
6. Cut to 60 characters on a word boundary.
7. Case is NOT touched. Only the caller knows whether its record system shouts; fix the case before
   you hand the name over.

If nothing survives, no file is written and the tool refuses in words.

KEY is `<system>-<tenant>-<record number>`, upper case, every run of anything else becoming one
hyphen. The tenant is whatever the record number is unique WITHIN - an org code, an account, a
company id. Record numbers are reused across tenants, and without that middle part one tenant's
number opens another tenant's file. No record number, or an unknown tenant: no file, a refusal in
words, exit 0.

The separator is space-hyphen-space, chosen because it cannot occur inside the KEY (the KEY has no
spaces). So `filename.rsplit(" - ", 1)[1]` recovers the key from the filename alone, with no parsing.

## The lookup: an index, never a search

`<Folder>/.index.json`, dot-prefixed so Obsidian hides it, written atomically, holding two exact
maps: key -> filename, and identity fingerprint -> key. It is a CACHE. The frontmatter is the truth,
and `rebuild-index` regenerates the whole thing from the files themselves.

1. Compute the KEY from the live payload.
2. Look it up. A hit: open that file and VERIFY that its `entity_key` or `entity_keys` contains the
   KEY, and that the identity fields you nominated match exactly. Either check failing is a hard
   stop - write nothing, escalate, say which file and which mismatch.
3. A miss: compute the expected filename. If that file is there, open and verify as above; this is
   how a lost or stale index heals itself. If it is not, this is a thing we have not met.
4. Before any write, verify again. A corrupt index must never be able to point a fact at the wrong
   file, and the check that stops it costs one string comparison.

Nothing is ever resolved by scanning, globbing, fuzzy matching, an embedding, or the Obsidian search.

## The four edge cases

**Two things share a name.** Their record numbers differ, so their keys differ, so their filenames
differ, and both files sit side by side. A lookup by name alone is refused outright. There are no
name-only aliases in this design, deliberately: an alias is precisely how `[[Fisher Jordan]]`
resolves silently to the other one. A human typing the name in Obsidian sees two candidates and has
to choose, which is the correct amount of friction.

**A name has a comma or an apostrophe.** The comma is dropped, the apostrophe is kept. Both are legal
filenames and legal wikilink targets, and `display` keeps the original.

**The record's spelling changes.** The filename changes, the KEY does not. The lookup finds the file
under its old name, and the writer RENAMES it rather than creating a duplicate, appending the old
filename to `aliases` so existing links keep resolving. This is why the index is keyed on the key and
not on the path.

**The thing moves to another system or tenant.** The key changes. Look the identity fingerprint up in
the index; an exact match on every identity field you nominated - all of them, exactly - is a MERGE:
append the new key to `entity_keys`, point the index's second key at the same file, LEAVE THE
FILENAME ALONE so no link breaks, and append a `move` section naming both keys and both dates.
Anything less than an exact match is not a merge. It is a person's decision, and nothing is written.
