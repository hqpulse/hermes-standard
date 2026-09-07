# Dossier prompt

The fixed prompt the staff "Build dossier" button posts through the chat door.
The controller reads the two parts back: part 1 becomes the person's context
skill body, part 2 goes through the USER.md seed route. Same prompt for every
org; nothing in it is per person except what Pulse returns.

---

Build a dossier of the person you work for, from Pulse only: their person card, their calendar for the last four weeks and the next two, their mail and their files. Look, do not send or write anything to anyone. Then answer with exactly the two parts below and nothing else.

Cover: their role and where they sit; their manager and their reports; the standing meetings they run or attend, with cadence and who else is there; their top correspondents inside and outside the company, by role; what they currently owe and are owed, with the person and the due date; how they write (length, greeting, sign-off, formality, the words they reuse).

Hard rules. Never a figure, not a count, an amount, a rate or a date-stamped number. Never the name of another customer of the Pulse team. Never pay, ratings, a hire or an exit, a health or family matter, or anything from personal mail; acknowledge only that such mail exists. Never a patient, client or resident by name. Say "not found" for a section Pulse gave nothing for; never fill it in from guesswork.

Part 1, between the lines === CONTEXT SKILL === and === END CONTEXT SKILL ===: the context skill body, plain markdown, under 6,000 characters, with these headings in this order: Role, Reports and manager, Standing meetings, Top correspondents, Open commitments, How they write. Short lines, facts only, no advice.

Part 2, between the lines === USER.MD === and === END USER.MD ===: one single line of five to eight entries separated by the section sign (§), each a declarative sentence about the person under 300 characters, the whole line under 2,000 characters. Stable facts only: role, timezone and working hours, how they like to be briefed, how they write, who they lean on. No dates, no figures, no other person's matters.
