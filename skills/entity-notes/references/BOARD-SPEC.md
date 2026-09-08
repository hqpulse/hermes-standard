# The board spec

`board.py` draws one HTML page from a folder of entity notes and a spec. The spec is the whole of
what it knows about your subject: the columns, their words, the colours a state maps onto, what
counts as stale, which rows go in which section. The renderer itself has never heard of a supplier
or anything else, which is why the same file draws a supplier board and a plugin's own.

    board.py --spec <spec.json> --vault <folder> --out <file.html>
             [--rows <rows.json>] [--context <context.json>]
             [--as-of YYYY-MM-DD] [--title <string>] [--source-label <string>]
             [--demo] [--spec-version]

It always exits 0. It prints one line naming the file it wrote, or one line saying why it did not.

## The version, and why it is frozen

`"spec": 1` is the contract. A renderer that meets a spec integer it does not know refuses and names
both numbers rather than drawing a best effort, because a board with a column silently missing is
worse than no board. New capability arrives as spec 2 and a spec 1 file keeps drawing forever.
`--spec-version` prints the integers this copy can draw, so a caller can check before it asks.

## Where the rows come from

`--vault` reads every `.md` in the folder (or in `spec.folder` under it) and uses each note's
frontmatter as the row, with the body under `_body`. That is the whole path for a board drawn
straight from notes.

`--rows` takes a JSON file of `{"rows": [...], "trouble": [...]}` instead. Use it when a caller has
to work something out that the frontmatter does not hold - a series assembled from the note's own
dated sections, a value classified by knowledge that belongs in the caller and not here. The rows
are plain objects with the same keys the spec names.

`--context` is the caller's own list for the day, laid over the rows:

    {"as_of": "2026-09-08",
     "header": "a line for the page head",
     "groups": {"<group value>": {"note": "...", "level": "quiet|attention|alert"}},
     "rows": [{"id": "<entity_key>", "slot": "09:20", "group": "...", "label": "...",
               "no_note": true}]}

A context row whose id matches a note adds the slot and the group to it. A context row with
`no_note` and no matching note becomes a row of its own, drawn dashed - which is the point: a board
built only from the notes cannot show you the one nobody has looked up yet.

## The spec, key by key

| key | what it does |
|---|---|
| `title` | the page's name, and the browser tab |
| `entity_kind` | only notes whose `entity_kind` is this are drawn |
| `class_required` | a note of a different `class` is a REFUSAL, not a skip: the board has been pointed at the wrong folder |
| `folder` | subfolder under `--vault` to read |
| `group_by` | the frontmatter key rows are grouped under |
| `sort_name` | the key rows sort by inside a group |
| `date_format` | `mm/dd/yy` (default), `dd/mm/yy` or `iso` |
| `absent_word` | the words a note uses for "we looked and there was nothing", e.g. `not documented` |
| `search_fields` | the keys the search box matches, as a substring, never fuzzy |
| `nominal_width` | the width the column widths are drawn for; default 1272 |
| `staleness` | `{key, label, ladder:[{upto_days, level}]}` - the clock the whole page fades on |
| `counts` | `{ready_label, person_label, person_field}` for the count line in the head |
| `columns` | below |
| `secondary_line` | `{key, label}` for the full-width line under each row |
| `palettes` | `{name: {value: token}}`, tokens `good progress attention closed alert unknown` |
| `tiles` | `[{id, label, when}]`, each a toggle filter; two pressed tiles intersect |
| `sections` | `[{id, title, grouped, when, hide_when_empty, collapsed, empty_words}]` |
| `banner` | the sentence above every fact on the page |
| `legend`, `footer` | the small print at the foot |
| `no_note_words` | the secondary line for a context row with no note |
| `drawer` | `{title_key, key_key, memory_line_key, fields, blocks, sections_key}` |

### Columns

Every column takes `key`, `label`, `width` (pixels, or a share like `1.25fr`) and `ages` - which
says this value gets fainter as the row's read date recedes. Eight types:

| type | draws |
|---|---|
| `identity` | the name, bold, with `sub` under it in mono. Never faded, on any row. |
| `text` | the value; optionally `pill` + `palette` to put a state beside it, and `sub` under it |
| `pill` | the value as a state pill, coloured by `palette` |
| `pills` | a list as solid pills, with `also: [{key, style}]` for a second list drawn outline. `none_word` when both are empty and we did look. |
| `date_age` | the date, and how long ago under it |
| `staleness` | the chip for this row's place on the ladder |
| `series` | a sparkline over `key` (a list, or `{values, dates, unit}`), with `dates`, `unit`, `text`, `measured_on`, `first_word` |
| `interval_watch` | `since` (a date key) and `interval` (a text key like "3 months") side by side |

`series` is the one column that can raise a caution. Give it `good_direction` (`down` or `up`),
`expect_from` (a key holding a status word) and `expect` (that word to `down`, `up` or `flat`), and
when the declared direction and the numbers disagree the cell gains a marker carrying both, plus
`caution_hint` - your words for what to go and read. It never changes the state pill and never
contradicts the record. This is the only judgement the renderer makes, and it makes it out of two
things the spec told it.

`interval_watch` reads "3 months" as a duration for exactly one purpose: deciding whether to say
"past the interval" beside the two dates it worked that out from. **It never produces a due date.**
Turning somebody's words into a date on a screen is the kind of quiet invention that gets read as a
decision somebody made.

### The filter language

Filters are JSON, evaluated by hand. A spec arrives from another repo, so an expression string in it
would be an execution path in it.

    {"field": "contract_open", "op": "truthy"}
    {"all": [ ... ]}   {"any": [ ... ]}   {"not": { ... }}

Operators: `truthy`, `falsy`, `empty`, `not_empty`, `eq`, `ne`, `in`, `staleness_in` (a list of
ladder levels) and `flag` (a marker a cell raised while drawing, `past_interval` or `disagreement`).

## What the page may not do

The output carries a Content-Security-Policy meta that forbids every network origin, so a font, a
stylesheet or a tracker pasted in later is refused by the browser rather than fetched. It stores
nothing in the browser: no `localStorage`, no `sessionStorage`, no cookie. A board can carry
confidential rows and a residue in a browser profile outlives the file it came from.

`board.py` refuses an `--out` under `/tmp`, writes 0600 inside a 0700 folder, and sends the file
nowhere. It is a renderer; it has no way to deliver anything.
