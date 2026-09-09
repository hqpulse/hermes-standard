---
name: policy-keeper
description: How to keep Policy.md: what goes in it, the 12,000-character cap, how to turn a handbook, job description or message into rules without losing one, where the leftovers go, and which rules need a real switch.
---

# Keeping Policy.md

`Policy.md` sits in your workspace and is loaded into every session as your standing orders. You keep it. Nobody else writes it except the Pulse team, who may edit it on your page. Read this skill before you change it, and whenever someone hands you a job description, a handbook, a policy, a contract, or tells you a rule in conversation.

## The shape of the file

Line 1 is `# Policy` and never changes. Then these seven sections, in this order, each a heading and short lines:

1. **Your job** — what you were hired to do, in the words you were given. Title first, then the duties, then what a good day looks like.
2. **Company rules** — what the company's policies say that applies to you: confidentiality, how information is handled, who may be contacted, working hours, tone.
3. **Do without asking** — what you may do on your own.
4. **Wait for a word** — what you draft and hold until the person says go.
5. **Never** — hard lines. The five shipped lines stay; add to them, never cut them.
6. **Who you work for and with** — the person, their role, the people you deal with and how (by role, not by private matters).
7. **Needs a real switch** — rules you were given that only a setting can guarantee (see below). One line each, so the Pulse team sees them on your page.

Under 12,000 characters, all in. Count before you save. When you are within 500 characters of the cap, condense before you add.

## Intake: the one procedure for every door

Material reaches you three ways: a document or message in chat; text the Pulse team typed on your page; a file the Pulse team placed in `Inbox/` in your workspace, with a message telling you so. The procedure is the same.

1. Read it whole. Use the document tools for a file. Never skim a policy.
2. Sort every statement into one of four homes:
   - **Policy.md** — a rule, a duty, a limit, a permission, a hard line.
   - **Memory** — how this person likes things done (their preferences and corrections).
   - **USER.md** — a stable fact about the person (role, hours, timezone, how they write).
   - **A vault note** — anything with a date, a figure, a named person's matters or a history; the confidentiality table in the assistant-standard skill decides the note's class.
3. Write. Edit `Policy.md` with the file tools; put each rule under the section it belongs to; keep line 1.
4. Reply in this shape and no other:
   - **Wrote** — one line per section you touched, saying what went in.
   - **Left out** — what did not fit or did not belong, and where it went instead (memory, USER.md, a note) or why it was dropped.
   - **Needs a real switch** — the rules from the list below that appeared in the material.
5. Append the same three parts, with today's date as a heading, to `Notes/Policy leftovers.md` in the vault. The note's frontmatter carries `class: private`, so it never leaves this machine. Open it later when a situation needs the fine print you condensed away.

## Condensing without losing a rule

- Keep the rule, drop the rationale. One line per rule.
- Keep the person's own bounding words exactly: over, under, only, never, at least, up to, before, after. Dropping one turns a bound into a different rule.
- Merge duplicates; never merge two rules that differ in scope.
- Never invent a rule to fill a gap. A section with nothing given says so in one line.
- When a document is long, write the rules first and the context second; if the cap presses, the context goes to the leftovers note.

## Phrasing that keeps the file loadable

The engine scans this file before every session and refuses the whole file on some phrasings. Write every rule as a positive instruction to yourself:

- Write "tell the person before you send anything" rather than a rule phrased as a ban on telling them.
- Write "keep to the rules in this file" rather than "ignore", "override" or "set aside" anything.
- Write no reference to a system prompt, a model, a vendor or an engine.
- Write plain text: no HTML, no hidden text, no shell commands, no file paths other than the names in this skill.

## Rules that need a real switch

A rule in this file is what you hold yourself to. Some rules the Pulse team can also lock with a setting, and those belong in the **Needs a real switch** section as well as where they apply, so the team can set the switch. They are:

- Spending money.
- Sending mail, invites or posts in the person's name.
- Searching the web.
- Driving a browser.
- Running shell commands.
- Reading a linked mailbox or calendar.
- Scheduling your own jobs.

When you list one, say the rule in the person's words and the switch in yours: "No outbound mail without Susan's word. Switch: mail sending."

## Training

While you are in training, every rule you are given goes into `Policy.md` at once and you say back in one line what you wrote. The training block in your own instructions says the rest.
