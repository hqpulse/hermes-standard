# Note types

Every note in the vault is one of these. Same frontmatter keys everywhere, so
the tables in the vault root work for every assistant and a note written for
one person reads like a note written for another. Paths are relative to the
vault root. Dates are YYYY-MM-DD in the person's timezone.

Common frontmatter on every note:

```yaml
type: meeting | person | project | decision | commitment | daily | expense | shift | entity
created: 2026-09-07
source: chat | voice | mail | calendar | file
tags: [...]
class: company | people | deal | private | phi   # the confidentiality class (see the skill)
```

`class: private` notes are never mirrored, never sent to anyone but the person,
and never summarised into a group or a shared note. Default is `company`.
`class: phi` is stricter still and only exists on a cell whose job is that work:
the file never leaves the pod's own disk. See the confidentiality table in the
skill.

| type | path | extra keys | what goes in | what never goes in |
|---|---|---|---|---|
| meeting | Meetings/YYYY-MM-DD <who or what>.md | date, attendees ([[links]]), project | DECISIONS, action items with one owner each, open questions | pay, ratings, resident or patient names |
| person | People/<Full Name>.md | role, org, projects, reports_to | role facts, what they own, a dated log of talks | anything personal, health, family, pay |
| project | Projects/<Name>.md | status (open, on hold, done), owner, due | goal, current state, links to meetings and decisions | deal figures unless class is deal |
| decision | Decisions/YYYY-MM-DD <question>.md | decided_by, confirmed_by, status | the question, the position, who confirmed, why | nothing else |
| commitment | Commitments/<owner> - <what>.md | owner ([[link]]), owed_to, due, status (open, done, dropped), from ([[meeting]]) | one promise per file; the Open commitments table reads these | vague "follow up" with no owner or due |
| daily | Daily/YYYY-MM-DD.md | (none) | the person's own scribbles for the day and what you read back at the close | numbers copied from Pulse |
| expense | Expenses/YYYY-MM-DD <vendor>.md | amount, currency, category, receipt (file) | a receipt the person handed you, filed | card numbers |
| shift (worker) | Shifts/YYYY-MM-DD.md | provider ([[link]]), counts | what was done per provider, as counts and chart links | any patient identifier |
| entity | <Kind>/<Name> - <KEY>.md | entity_kind, entity_key, entity_keys, display, source_system, read_at, read_on, encounters | one thing you meet again and again: dated sections appended for ever, and what changed since last time | a fact belonging to any other entity |

Rules:
- A commitment is created the moment a meeting note records an action item; the meeting note links to it and it links back.
- When a commitment is met, set status: done and add `done: YYYY-MM-DD`; never delete.
- A person note is role facts. The dated log lines point at meeting notes; they do not restate them.
- Outbox/ holds files made for the person (spreadsheets, decks, PDFs); it is not a note type.
- The vault root carries the tables the assistant reads: Open commitments.base, Meetings.base, People.base. They ship with the pack; do not rewrite them, add views if the person asks.
- An entity note is the one type that grows for years. It has its own skill
  (`entity-notes`), which owns the filename rule, the frontmatter contract and
  the exact lookup; never hand-roll any of the three.
