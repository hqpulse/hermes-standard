---
name: ecw
description: "eClinicalWorks EMR: sign in and read charts in a browser. The V12.0.3 hosted Web EMR under /mobiledoc: the two-screen sign-in, the app shell and its work queues, the patient lookup, the actions list and the progress note. Read only. It never files, signs, locks or books anything."
metadata:
  hermes:
    requires_tools: [browser_navigate]
---

# eClinicalWorks

eClinicalWorks is a hosted electronic medical record. A practice reaches it at its own
host, and every screen lives under the `/mobiledoc/` path. This skill is how this
assistant drives that web client: how to get in, what each screen is, what a page can
and cannot tell you, and the short list of things it must never touch.

Everything here was read off a live V12.0.3 practice on 11 September 2026, except the
parts marked UNRECORDED, which say so on their own line. **A screen marked UNRECORDED
has never been seen by anybody who wrote this file.** Do not click your way through one
from a description. Say what you were asked to do, say the screen has not been mapped,
and stop.

The version string is printed on the login page, and the browser title reads
`eCW (<Last>, <First> ) Production`. If the version you see is not V12.0.3, say so out
loud before you act: this vendor rewrites its login bundles between releases, and a
selector below may have moved.

## Read these two skills first

- **`browser`** is the loop: navigate, snapshot, act on a ref, snapshot again. Refs are
  per snapshot, and this application re-renders constantly, so snapshot again after
  every click. Everything here is done with the `browser_*` tools.
- **`logins`** is where the username and the password come from. Take the password at
  the moment you fill the field and not before. Compare the domain in the address bar
  with the domain on the login before you type anything into it.

## The shape of the job

**Sign in once and keep the session.** Do not sign in per task. There are two hard
reasons and both are in `references/login.md`: the practice runs a mandatory email
verification whose skip counter goes down on every single sign-in whether anybody
touches the popup or not, and a refused sign-in cannot be told apart from a bounce, so
retrying is how a real clinician's account gets locked.

The entry procedure is four moves:

1. Sign in across the two screens (`input#doctorID`, `input#nextStep`, then
   `input#passwordField`, `input#Login`).
2. Read the landing URL, not the page. A successful login is bounced back to the login
   page carrying `error=6`, and that page shows no error of any kind.
3. Navigate to `/mobiledoc/jsp/webemr/index.jsp`. It answers 200 and paints a loading
   frame that never clears on its own.
4. Clear the three entry dialogs. Only then is the shell interactive.

Full sequence, every selector, every failure and how to recognize it:
`references/login.md`.

## Reading the application

Once you are in, **the address bar stops moving.** Every module loads into `index.jsp`
through a hash route, so the URL is not a location signal after sign-in. The screen you
are on is named by the module title at the top left of the content area: "Office
Visits", "Review Progress Notes", "Review Actions", "Lookup Encounters".

The screens that have been recorded, each with its anchor selector, its controls and
its columns: `references/screens.md`. The eCW mechanics behind a practice's own written
procedures, the patient hub, the patient documents viewer, the anatomy of a progress
note, the template merge, the action fields and the structured-data default:
`references/tasks.md`.

What a page can and cannot tell you, and why a refusal is often the right answer:
`references/doctrine.md`. Read it before you report that something is empty.

## Never enumerate and click

The first entry in the left rail's DOM order is **Log out**. The expanded navigation
tree also holds `New Action`, `New Telephone Encounter`, `Create New Messages`,
`Change Password`, `Patient Merge` and `Set Out of Office`. Anything that walks the
discovered links and clicks them will sign itself out on the first step, or do worse.
That is not a hypothetical: it happened during the recording session that produced this
file.

**Click named targets only.** Every control this skill asks you to press is named here
by selector or by its exact label. If the control you want is not in this file, it has
not been mapped, and the answer is to say so.

## What this skill will not do

These are not preferences. Every one of them is a live clinical system doing something
irreversible to a real person's record.

1. **No form but the sign-in and a search box.** The sign-in and a search field are the
   only two places this assistant types. Everything else is read.
2. **Never Save, Submit, Sign, Lock, Finalize or File.** Not a note, not an action, not
   a demographic field, not a setting. `Lock Progress Note` sits two buttons away from
   `View Progress Notes` on the schedule, and one click on it cannot be undone.
3. **Never book, print, export, create a patient, or change a setting.** That includes
   `New Patient`, `Quick Reg + Quick Appt`, `New`, `Reassign To`, the CPT notice's "do
   not show this message again" checkbox, and the Security Verification popup's `Verify`
   and `Save` buttons.
4. **One retry on a sign-in, and only one.** This practice's login page renders no error
   box at all, so a refusal and a stale-session bounce look identical. If a second
   attempt does not land in the app, stop and tell the person the sign-in did not go
   through. Repeated failures lock an account a clinician needs the same day.
5. **Never type a password that came from chat**, and never write one into a script or a
   file. It comes from the `logins` door at the moment of use or the work does not
   happen.
6. **Never conclude "empty" from a page that did not open.** A bounce, a 412, a modal and
   a loading frame all answer with something. "No visits", "no notes", "no such patient"
   must come from a screen that proved it is the screen.
7. **Leave the browser on a blank page when you are finished.** The browser is shared and
   long lived, and a parked chart is somebody's medical record left on a screen.

## When you are stuck

Say which screen you are on, what you were trying to reach, and what the page did. Do
not quote the page's own error text back at anybody: this application's error boxes
carry a patient's name, an account number and a session id. Name the screen and the
control instead.

If a control is present in the snapshot and reports visible but a click on it times out,
you are looking at a modal backdrop. Clear the dialogs (the entry sequence in
`references/login.md`) and try again.
