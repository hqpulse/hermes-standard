# What a page can and cannot say

This is the oldest and most expensive thing in this skill. It is ported from the module
docstring of the scribe plugin's own eCW browser door, which was written while somebody
was paying for each of these lessons one at a time. The sentences are kept as they were
written wherever they are true of any practice.

Two edits were made and they are the only two. The original compared this browser door
against a second door that answered the same questions through an API, and called that
one "the mock door"; here it is just called **an API door**, because the comparison is
what carries the lesson and the other door's name does not. And the original named its
own operations (`patient.find`, `note.read`, `schedule.day`); here those are named as
the thing a person does on a screen, because that is how this skill works.

## The stance

Drive the controls the application actually offers, and nothing else.

> No stealth, no anti-fingerprinting, no evasion of any kind. The door drives the
> controls the app actually offers and nothing else: it never injects a form field the
> page did not render, never calls a JSON endpoint behind the app's back, and never works
> around a check. If a page ever demanded evasion, this stops and refuses.

## How to say that something went wrong

> Refusals are one sentence plus what a person does next. They never carry a stack, a
> URL, a credential, the vendor's name, or any word the PAGE wrote: a served error box
> on a real practice client carries the vendor's brand, the patient's name and MRN and a
> session id, and this door's own leak tests only ever see the replica's boxes, so
> nothing from a page is ever interpolated into a refusal. What a refusal MAY carry is an
> identifier the door resolved from the caller's own search or read: the chart id behind
> the name that was passed, or the encounter id read off the grid. Those are about the
> caller's own question and they are what a person needs to open the right screen.

## What a page cannot say, so do not pretend it can

**Finding a patient.** The lookup box matches on NAME only, so a search that has no name
in it searches nothing at all, and "nothing was searched" is not "no such patient". A
search with no name is a refusal rather than an empty list. A name that carries a digit
and matches nothing is refused the same way.

**Reading a note.** A page does not render a visit type, a provider id, a created or
updated timestamp, an author username, who locked it, a source, or whether it was
persisted. On a signed or locked note the signature line replaces the scribe's name, so
the author is simply absent there. The chart page renders the newest note first; put
that back into oldest-first order before you count, so "the first note" means the same
note however you got there. That holds **per chart**:

> a name matching two charts is refused rather than merged: this door walks chart by
> chart where an API door filters one practice-wide list, so a merged answer comes back
> grouped by patient where the API's comes back interleaved, and the first note would be
> a different patient on each door.

**A name that matches no chart is a refusal, not an empty answer.** This is where a
browser deliberately parts company with an API:

> The [API] door filters a practice-wide list, so a misspelt name is simply a list with
> nothing in it; here the search itself comes back empty, and reporting that as "this
> patient has no notes" is how somebody concludes a note never filed when the name was
> only mistyped.

A chart id that opens no chart is refused for the same reason. And a name that matches
**more** than one chart is refused too, with the candidates named:

> a web session opens one chart at a time, two patients' records are two answers rather
> than one list, and merging them is the wrong-patient failure with the evidence still
> attached.

**Checking whether a note is filed** needs a patient. A web session opens one chart at a
time and there is no practice-wide note index behind it, so a bare note id, or "every
note in the practice", is refused rather than answered from a partial walk. The next
appointment comes back as a sentence, because the page renders the sentence and not the
interval, date, reason and who set it.

**Reading one encounter.** No last-visit summary, and none of a record's own
bookkeeping. Whether it is locked, and the visit's notes, are read off the note on the
chart and not from the encounter itself.

**Reading a day's schedule.** The date is required, and this one has a specific history:

> The Office Visits screen opens on a day of ITS own choosing when none is named, so a
> missing date used to come back as that day's whole grid with a top-level date of null
> and every row stamped with a concrete day. This read is logged as material a quality
> check trusts as the chart's own word, and a day nobody asked for is material nobody can
> check.

A heading that does not say which day it is showing is a refusal too: every row on the
grid is dated by that heading and nothing else, so a heading that cannot be read would
turn a full day into an empty one.

And per row there is **no provider key at all**, rather than a provider of "nobody":

> absent says "the page does not say", where a null reads as "the page says nobody".

The reason: the Office Visits grid carries no provider column and no provider control.
It renders the whole practice day under one clinician's heading. So the honest answer is
the whole day, and filtering it by provider is refused outright, because handing one
clinician another's patients is the wrong-patient failure by another road. The heading
names the VIEW, not the row, and on a shared day most rows belong to somebody else.
Recording the real Office Visits provider filter is what would lift both of those.

**Reading a queue.** The grid truncates a dictated note to a preview and renders neither
when it was queued nor what it filed to, so those are absent rather than guessed. The
dashboard's queue panel is a summary with no line per item, so it cannot supply them
either.

**Listing a patient's appointments** needs a patient, because the booked-appointment list
lives on a chart and there is no all-patients page behind it. The lookup takes a name,
the same as every other search on this door, so a chart id or a chart slug passed in its
place is refused rather than guessed at.

**Writing a note.** This skill does not write, and section 2 of `SKILL.md` is why. The
doctrine is kept because it explains what a note form would demand if anybody ever
authorized one:

> the form will not save without a billing code and the door will not choose one, so an
> undictated note does not file through this door at all and waits for the code; the
> encounter must name the visit the application will pick, because the form renders no
> encounter field; and the provider is a cross-check rather than an instruction, because
> the note goes on under the provider whose visit it is and the answer always carries the
> name the CHART gave back.

**A chart address is a PATH, never an absolute URL.** Once the address names the
practice, an absolute one carries the practice host name into an answer somebody may read
out loud.

## Where a browser refuses differently from an API

Every one of these is a person's decision rather than a defect, and it is worth being
able to say each of them out loud in plain words when somebody asks why the browser
answered differently:

1. A billing code is required here; an API door files a code-pending draft.
2. Filtering a day's schedule by provider is refused here; an API door filters by
   provider.
3. Reading a note, checking a note's status and listing appointments need a chart here;
   an API door answers practice-wide.
4. A name that matches no chart, and a search the box cannot run at all, are refusals on
   the reads that walk a chart and on reading a chart; an API door returns an empty list.
   Finding a patient is the one search that still answers an unmatched name with an empty
   list, because an empty result IS the answer to "who is on this name".
5. A name that matches TWO charts is a refusal here on every read; an API door merges both
   charts into one list, or silently picks one.
6. A patient is named by NAME here; an API also takes a chart id or a chart slug, and both
   are refused here rather than guessing which one was meant.
7. A day's schedule requires a date here, which is the one divergence that closed rather
   than opened: an API refuses it too.
8. An unheaded draft is refused as bad input here and as a system error on an API door,
   which only finds out at the far end. The refusal families differ. Both refuse.

## The two rules that fall out of all of it

1. **Never conclude "empty" from a page that did not open.** A bounce, a 412, a challenge
   and an interstitial all answer with something. "No notes", "no visits", "no such
   patient" must come from a screen that proved it is the screen.
2. **Never retry a refused password.** One failure is a person's problem to fix. Three are
   a locked clinical account.
