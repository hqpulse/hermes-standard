---
name: ecw
description: "eCW (eClinicalWorks) EMR: sign in and read a chart in a browser. The V12.0.3 hosted Web EMR under /mobiledoc: the two-screen sign-in, the app shell behind three entry dialogs, the work queues, the patient lookup and the actions list. Read only. It never saves, files, signs, locks or books anything, by clicking or by evaluating."
metadata:
  hermes:
    requires_tools: [browser_navigate, browser_console]
---

# eClinicalWorks

eClinicalWorks is a hosted electronic medical record. A practice reaches it at its own
host, and every screen lives under the `/mobiledoc/` path. This skill is how this
assistant drives that web client: how to get in, what each screen is, what a page can
and cannot tell you, and the short list of things it must never touch.

## What in here was seen, and what was not

- **`references/login.md` and `references/screens.md` were read off a live V12.0.3
  practice on 10 and 11 September 2026.** Every selector in them was on a real screen.
- **`references/doctrine.md` was not.** It is ported from the module docstring of an
  older eCW browser door that ran against a **stand-in replica**, not against a practice.
  It is kept because its stance and its refusal grammar are true anywhere. Its
  screen-specific claims are not evidence, and where one disagrees with `screens.md`,
  **`screens.md` wins**.
- **`references/tasks.md` is FROM THE SOP, NOT OBSERVED.** It describes the mechanism a
  practice's own written procedure walks through. Nobody has seen those dialogs.

**Three things are UNRECORDED, and they are the three that matter most to a scribe:**

| UNRECORDED | why |
|---|---|
| **the Patient Hub** | reaching it opens a real patient chart, which the recording session was told not to do |
| **the progress-note form** | eCW refuses to open one outside an encounter: `Practice > Progress Notes` answers with a modal reading **"No encounter opened after Login."** |
| **My Favorite Templates** | it is a control *inside* the progress note, so it sits behind the same wall |

**A screen marked UNRECORDED has never been seen by anybody who wrote this file.** Do not
click your way through one from a description. Anything this skill says about those three
comes from the client's SOP and is labeled **from the SOP, not observed** where it is
said. Say what you were asked to do, say the screen has not been mapped, and stop.

The version string is printed on the login page, and the browser title reads
`eCW (<Last>, <First> ) Production`. If the version you see is not V12.0.3, say so out
loud before you act: this vendor rewrites its login bundles between releases, and a
selector below may have moved.

## Read these two skills first

- **`browser`** is the loop: navigate, snapshot, act on a ref, snapshot again. Refs are
  per snapshot, and this application re-renders constantly, so snapshot again after
  every click. Everything here is done with the `browser_*` tools, within the limits in
  "What this skill will not do" below, which are narrower than the `browser` skill's own.
- **`logins`** is where the username and the password come from. Take the password at
  the moment you fill the field and not before. Compare the domain in the address bar
  with the domain on the login before you type anything into it. That door is
  **read-only**: it lists, shows, and hands over a password or a code. It cannot store
  one. Nothing in this skill may create a credential, because there would be nowhere to
  put it.

## The shape of the job

**Sign in once and keep the session. Never sign out.** Do not sign in per task. There are
two hard reasons and both are in `references/login.md`:

1. **This practice has a real second factor.** The account's verification is now enrolled
   on email, and eCW **mails a confirmation link on every sign-in**: the password lands on
   an `OTPVerification` page and stays there until the link is opened and "Yes, it's me" is
   pressed. Four sign-ins on 12 September 2026 all completed that way. So a sign-in is not
   a free thing to repeat — it is a mailbox round trip, and it needs a mailbox.
2. **The login page renders no error element at all**, so a refusal and a bounce look
   identical, and retrying is how a real clinician's account gets locked.

The entry procedure is five moves, and `scripts/ecw signin` does all five:

1. Sign in across the two screens (`input#doctorID`, `input#nextStep`, then
   `input#passwordField`, `input#Login`).
2. Read the landing URL, not the page. A successful login is bounced back to the login
   page carrying `error=6`, and that page shows no error of any kind.
3. **If the landing is `OTPVerification`, a confirmation link has been mailed.** It must be
   opened in a **clean, isolated browser context** — opened while the pending sign-in's
   `JSESSIONID` is in the jar, eCW answers "An error occurred while processing the
   request" — and "Yes, it's me" pressed. Then the first tab moves on by itself.
4. Navigate to `/mobiledoc/jsp/webemr/index.jsp`. It answers **200** and paints a
   **loading frame reading "Building your user experience"** that **never clears on its
   own** — it was held there for sixty seconds. Never `home.jsp`: that is a 412.
5. Clear the three entry dialogs, in this order. Only then is the shell interactive.

| # | dialog | the control to press |
|---|---|---|
| 1 | `div#showCPTCopyRightModal`, the CPT copyright notice | `input#okBtn`. **Leave the do-not-show-again checkbox alone** — ticking it changes a setting. |
| 2 | an eCW data-loading **bootbox** | `.bootbox button.btn`. **Dismiss it if present, never wait for it**: it may only appear in headless Chromium with the eCW plug-in absent. |
| 3 | `div#verificationMethodPopup`, Security Verification | `button#showCloseBtnOnHeader`, the header X. **Never `Verify` and never `Save`.** |

**While those dialogs are up, every real click on a shell control times out on the modal
backdrop even though the control is present and reports visible.** They fire **once per
SIGN-IN, not per page load**: reloading `index.jsp` inside a live session brought back
only the data-loading box.

Full sequence, every selector, every failure and how to recognize it:
`references/login.md`.

## Reading the application

Once you are in, **the address bar stops moving.** Every module loads into `index.jsp`
through a hash route, so the URL is not a location signal after sign-in. The screen you
are on is named by the module title at the top left of the content area: "Office
Visits", "Review Progress Notes", "Review Actions", "Lookup Encounters".

The screens that have been recorded, each with its anchor selector, its controls and
its columns: `references/screens.md`. The eCW mechanics behind a practice's own written
procedures — the patient hub, the patient documents viewer, the anatomy of a progress
note, the template merge, the action fields and the structured-data default:
`references/tasks.md`, **all of it from the SOP, not observed**.

What a page can and cannot tell you, and why a refusal is often the right answer:
`references/doctrine.md`, read with the provenance warning at the top of this file in
mind.

## This skill's own command

Four things this door needs have no permitted road with the `browser_*` tools, and each
one was measured rather than assumed: there is **no isolated browser context** (the mailed
confirmation link fails when it is opened holding the pending sign-in's cookie), there is
**no wait, no force-click and no settle** (the entry dialogs need all three), **`browser_type`
fires no key events at all** (0 keydown, 0 keyup — anything on an Angular `ng-keyup` never
reacts to it), and **no tool reports the page's address after a click**.

So the skill ships one command instead of loosening rules 5 and 6:

    /opt/data/profiles/hermes-standard/skills/ecw/scripts/ecw <command>

    preflight              is a sign-in safe at all? costs no attempt, no credential
    url                    the page's address
    where                  what the address MEANS: signed-in, confirm-link, refused,
                           security-image, password-change, in-the-app
    viewport [W H]         read it; raise it to at least 1600x1000
    wait <selector|ms>     a deterministic wait
    gone <selector>        wait for something to go away (the loading veil)
    keys <sel> <text>      type with REAL key events, one per character
    dialogs                clear the three entry dialogs, on a clock. When one will
                           not clear it names what the application is showing
    confirm                the mailed confirmation link, in an isolated context
    signin                 the whole entry, refusals compiled in. It raises the window
                           itself, asks the application whether it works rather than
                           reading the address bar, and spends an attempt only when a
                           password is actually submitted
    session save|restore   keep a live session across a pod roll

**A restart does not cost the session, if the two guard jobs are set.** They are no-model
jobs a person registers once per eCW seat; you do not run them yourself:

- `hermes cron create "45 5 * * 1-5" --name ecw-session-guard --script ecw_guard.sh --no-agent --deliver local`
- `hermes cron create "*/5 * * * *" --name ecw-boot-guard --script ecw_boot_guard.sh --no-agent --deliver local --failure-deliver local`

`ecw_guard.sh` widens the eCW window, puts the saved session back, spends a password only if
that session is dead, and saves again. `ecw_boot_guard.sh` runs it exactly once after a new
pod or a new browser and is silent every other time. Both must sit in the PROFILE's
`scripts/` folder: the scheduler refuses a script anywhere else, symlinks included.

**Run it with the terminal tool, never with `execute_code`** — the same reason `logins`
gives: `execute_code` drops the environment the script needs and it would tell you the
door is not configured when it is.

**It is not a second browser.** It attaches to the same Chromium at `BROWSER_CDP_URL` and
drives the same page you are looking at, so your very next `browser_snapshot` sees what it
did. Snapshot after every call, the same as after a click.

**What it will not do, in the file rather than in prose:** it visits exactly two paths on
the configured host and has no default host; it stops on `SecurityImage.jsp` and on
`changePasswordOnLogin.jsp`; it never presses Verify, Save, a picture or the
do-not-show-again checkbox; it never navigates to `logout.jsp` and it never closes the
browser, only its own context; `keys` refuses anything that is not a field, so it cannot
become a way to press a control; and **the two-attempt budget is kept on disk**, so a
fresh session that has forgotten rule 7 still cannot spend a third.

**An attempt is a password that was SUBMITTED**, and the ledger is written at that
moment, not when the command is invoked. On 13 Sep both of a night's two attempts were
spent by runs that never reached the password field at all — one refused on a bad guard,
one died at the window-size wall — and the account was then out of budget having risked
nothing. A run that stops before the password says so in its own output, and the budget
of two, in a six-hour window, is exactly what it was.

No secret passes through you: `signin` takes the password from the `logins` door and the
mailbox token from the controller door **inside the script**, so neither is ever a tool
argument. That is strictly better than filling the field yourself, where the password is
the `text` argument of `browser_type`.

When it refuses, it prints one plain sentence and a non-zero exit. Say that sentence.
Do not run it again to see whether it means it.

## Never enumerate and click

**The first entry in the left rail's DOM order is `Log out`** (`a#jellybean-panelLink10`).
The expanded navigation tree also holds **`New Action`**, `New Telephone Encounter`,
`Create New Messages`, **`Change Password`**, **`Patient Merge`** and `Set Out of Office`.
Anything that walks the discovered links and clicks them will sign itself out on the first
step, or do worse.

**That is not hypothetical. It happened during the recording session that produced this
file: an early script iterated over discovered links, the first one was `Log out`, and it
ended the session.**

**Click named targets only.** Every control this skill asks you to press is named here
by selector or by its exact label. If the control you want is not in this file, it has
not been mapped, and the answer is to say so.

## What this skill will not do

These are not preferences. Every one of them is a live clinical system doing something
irreversible to a real person's record.

**The rule underneath all of them is about EFFECT, not about which control you press.**
Pressing `Save` and evaluating `document.forms[0].submit()` are the same act, with the
same result, on the same record. Read every rule below as covering the click, the
keystroke, the script and the **evaluated expression** alike. A rule written in the
vocabulary of clicking is not satisfied by finding a way to do it without clicking.

1. **No form but the sign-in, a search box and a grid's own filters.** Those three are
   the only places this assistant puts a value — by typing or picking in them, and by no
   other means. A grid filter counts because setting one only changes which rows are
   asked for: the Provider, Facility, Status and date controls above a queue, and the
   `Filter` or `Search` button that runs them. Set the filter rather than inferring it
   from the rows (`references/doctrine.md`), and say which value produced the list you
   report. This does **not** reach a checkbox that changes a setting (the CPT notice's
   do-not-show-again, rule 3), a field on a record, or anything a filter sits next to.
   Everything else is read.
2. **Never Save, Submit, Sign, Lock, Finalize or File.** Not a note, not an action, not
   a demographic field, not a setting. `Lock Progress Note` sits two buttons away from
   `View Progress Notes` on the schedule, and one click on it cannot be undone. This
   covers submitting a form by evaluation exactly as it covers pressing its button.
3. **Never book, print, export, create a patient, or change a setting.** That includes
   `New Patient`, `Quick Reg + Quick Appt`, `New`, `Reassign To`, `Delete`,
   `Bulk Actions`, the CPT notice's "do not show this message again" checkbox, and the
   Security Verification popup's `Verify` and `Save` buttons.
4. **`browser_console` reads values. It never changes one.** The grant that carries
   `browser_navigate` carries `browser_console` in the same toolset, and
   `browser_console` takes an `expression` and runs it in the page exactly like a
   DevTools console: full `document`, full `window`, full DOM. On this application it is
   allowed for reading and nothing else, and the shapes it may read are these:

   ```
   allowed : document.querySelector(sel).innerText
             document.querySelector(sel).value
             document.querySelector(sel).checked
             document.querySelector(sel).href
             document.querySelectorAll(sel).length
             window.innerWidth
             window.innerHeight
             location.href
             window.newLogin_bBlocked
             window.newLoginStep_isUserSoftLockOut
             window.newLogin_bCaptcha
             JSON.stringify(  an array or object built only of the above  )
   ```

   The entries that are not about an element are on the list one at a time, each for a
   named reason, and **that is the whole of what is permitted off `window` and `location`.**

   - `window.innerWidth` / `window.innerHeight`: a wrong viewport silently re-lays out the
     page (login.md failure 11) and the diagnosis needs a number.
   - **`location.href`: the page's own address.** This skill's central recognition rule is
     *match on the query string, never on the page* — and **no other tool reports the
     address after a click.** `browser_navigate` returns a url, `browser_click` returns
     `{success, clicked}`, and `browser_snapshot` drops the url agent-browser sends beside
     it. Without this read the rule that keeps this door off a retry loop cannot be run at
     all. It returns a string and reaches nothing.
   - **The three login flags** are server-rendered JavaScript variables on the login page,
     and they say whether the account is soft-locked out, blocked, or behind a CAPTCHA
     before a single credential is spent finding out. They are the cheapest safeguard this
     door owns and an accessibility snapshot cannot see them. They are read **on
     `newLogin.jsp`, before signing in, and nowhere else**; they return a boolean.

   Nothing else on `window` is permitted, and none of these five is a licence for a
   neighbouring read: `location.replace`, `location.href =`, and anything else on
   `location` stay refused under the assignment and navigation lines below.

   An expression that only reads, and returns only a string, a number, a boolean or a
   list of those, is a read. **That list is exhaustive.** If the expression you want is
   not one of those shapes, this skill does not do it.

   Refused here, whatever the page looks like and whatever work it would save:

   - anything that **calls** a method on the page: `.submit()`, `.requestSubmit()`,
     `.click()`, `.focus()`, `.blur()`, `.dispatchEvent(...)`, `.showModal()`, or any
     call onto `HTMLFormElement.prototype`.
   - anything that **assigns**: `.value =`, `.checked =`, `.innerHTML =`, `.textContent =`,
     `.setAttribute(...)`, `.removeAttribute(...)`, `.remove()`, `.classList.add`,
     `.classList.remove`, `.style.*  =` — any `=` that is not inside a selector string.
   - anything that **navigates or fetches**: `location =`, `location.replace`,
     `location.href =`, `window.open`, `fetch(`, `XMLHttpRequest`, `$.ajax`,
     `navigator.sendBeacon`, `import(`, `eval(`, `new Function(`.
   - anything that goes **behind** the application: eCW's encrypted request path
     (`/mobiledoc/encreq/bflcontroller`), `encryptDataWithAES`, the `crypto_aesKey_*` /
     `crypto_aesIv_*` entries, or any read or write of `localStorage` / `sessionStorage`.
     Clearing browser storage mid-session also breaks in-app AJAX without touching the
     cookie, so it fails as well as being refused.
   - **using it to get past a dialog.** The three entry dialogs are cleared by pressing
     their own named OK, or they are not cleared. Removing a backdrop node, or evaluating
     the control underneath it, is refused.

   Why this is spelled out at this length: every other refusal in this file names a
   control, and an evaluated expression presses no control. `document.forms[0].submit()`
   files a note without ever touching `Save`, and a rule written as "never press Save"
   does not reach it. This rule does.
5. **Never `browser_cdp` and never `browser_exec` on this application.** Both ship in the
   same grant as `browser_navigate`. `browser_cdp` sends raw Chrome DevTools commands, so
   `Runtime.evaluate` is rule 4 with rule 4 removed and `Input.dispatchMouseEvent` presses
   a button no snapshot ever showed. `browser_exec` hands the page to a second,
   unsupervised loop. Neither leaves a legible record of what it did to a chart. If the
   only way to do something here is one of those two, it is not done: say what you were
   asked for, say it needs a person, and stop. (This includes setting the viewport —
   `scripts/ecw viewport` handles the window size instead; see the section below.)
6. **No Playwright script against this application.** `skills/browser` documents attaching
   the Playwright client to the same Chromium for long scripted sequences. **That door is
   closed here.** A script is rules 1 to 5 with nobody reading them.

   **The one exception to rules 5 and 6 is `scripts/ecw`, which is this skill's own
   command.** Run it with the terminal tool and read what it prints. It is not a way
   around the two rules and it does not widen them: it is one named, reviewable file that
   does the four things this door needs and the tools cannot do, with every refusal above
   compiled into it. A script you write yourself is still refused, whatever it is for.
7. **Two submitted passwords per working session, across every cause, and then stop.** Not
   two per attempt, not two per reason, and not two each time the session drops. A
   refused password, an expired session bounce and a fresh start all spend from the same
   budget of two, because this practice's login page **renders no error box at all** and
   the three are indistinguishable from one another. When the budget is spent, say the
   sign-in did not go through, name the login by its title, and stop. Repeated failures
   lock an account a clinician needs the same day, and every attempt is also a mailbox
   round trip (`references/login.md` §6). **`scripts/ecw` keeps this budget on disk**, so
   a fresh session that has forgotten this rule still cannot spend a third attempt — that
   is a floor under the rule, not a replacement for it.
8. **Never sign out.** When you are finished, leave the browser on a blank page: the
   browser is shared and long lived, and a parked chart is somebody's medical record left
   on a screen. Do not close the session to tidy up. The session is the expensive thing.
   `logout.jsp` is documented in `references/login.md` for the case where a person asks
   for it, and for no other case.
9. **Never type a password that came from chat**, and never write one into a script or a
   file. It comes from the `logins` door at the moment of use or the work does not
   happen.
10. **A forced password change is a stop, not a task.** Landing on
    `/mobiledoc/jsp/webemr/login/changePasswordOnLogin.jsp` means the credential is
    temporary or expired. Do not fill the form, do not read its CAPTCHA, do not generate a
    password. The credential door is **read-only** — `skills/logins` offers list, show,
    password and otp, and there is no write — so a password changed here would exist
    nowhere afterward, and the clinician's own account would be unusable until a practice
    admin reset it. Say the credential has expired, name the login by its title, stop.
11. **The Security Image enrollment screen is a stop.** Landing on
    `/mobiledoc/jsp/webemr/login/SecurityImage.jsp` means the account has never been
    enrolled. Its Save writes a permanent account-level setting on a real clinician-facing
    account, so it is rule 2 and rule 3 together. **There is no Save anywhere in this
    skill that this assistant may press, and no exception to rule 2 exists in any
    reference file.** Do not pick a picture and do not press Save; do not press the X or
    Logout either, because both of those sign the account out. Stop and tell a person: the
    enrollment is a person's single click, done once.
12. **Never conclude "empty" from a page that did not open.** A bounce, a 412, a modal and
    a loading frame all answer with something. "No visits", "no notes", "no such patient"
    must come from a screen that proved it is the screen.

## When you are stuck

Say which screen you are on, what you were trying to reach, and what the page did. Do
not quote the page's own error text back at anybody: this application's error boxes
carry a patient's name, an account number and a session id. Name the screen and the
control instead.

If a control is present in the snapshot and reports visible but a click on it times out,
you are looking at a modal backdrop. Clear the dialogs (the entry sequence above and in
`references/login.md`) and try again — by pressing their own OK controls, never by
evaluating your way around them.

**`scripts/ecw dialogs` is on a clock and it will tell you why it stopped.** When a dialog
cannot be pressed it comes back with what the application is showing, in the application's
own words — the one exception to the rule above, fenced to the three entry dialogs, cut
short, and with any long number masked. Say the SENSE of it ("the application is showing a
data loading error") rather than pasting the box. A sweep that clears nothing is a refusal,
not a delay: pressing on through it reads a screen that is not there.
