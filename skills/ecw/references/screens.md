# The eClinicalWorks screens

Recorded off a live V12.0.3 practice on 11 September 2026. Each screen below carries the
way in, an anchor selector that proves you are on it, and the controls and columns that
were actually on the glass.

**Every list screen was empty on the account that was recorded.** So this file proves the
shape of each screen, not its populated behavior. It knows the columns. It does not know
what a row looks like, and it does not pretend to.

A screen marked **UNRECORDED** has never been seen. Do not drive one from a guess.

## The rule that catches everybody once

**After sign-in the address bar stops moving.** Every module loads into `index.jsp`
through a hash route. The URL is not a location signal. The screen you are on is named
by the module title at the top left of the content area. Anything that tracks its
position by URL will think it never moved.

## The app shell

**URL** `/mobiledoc/jsp/webemr/index.jsp`, HTTP 200
**Anchor** `a#jellybean-panelLink22` visible and clickable
**Get there** sign in, then navigate, then clear the three entry dialogs. See
`login.md`.

Top bar, left to right:

| control | selector | what it is |
|---|---|---|
| hamburger | `a#jellybean-panelLink4` (`.navgator.mainMenu`, x=0 y=0 w=61) | opens and pins the left module rail |
| user initials | `a#jellybean-panelLink6` ("Toggle Dropdown") | the user menu. eCW's own popup says verification lives at User Initials > Gear Icon > User Profile > Verify |
| product mark | none | reads "eClinicalWorks 12" |
| patient lookup | the person-with-magnifier icon at about x=320, and `a#jellybean-panelLink65` ("Action") beside it | opens the Patient Lookup dialog |

### The jellybeans

eCW's work queues, each a letter plus a waiting count. Every one carries its target as
an href, which makes them the most useful map on the screen.

| bean | selector | href, all prefixed `#/mobiledoc/jsp/webemr/` |
|---|---|---|
| P | `a#jellybean-panelLink13` | `jellybean/preRegistration/Patient_Pre-Registration.jsp` |
| N | `a#jellybean-panelLink14` | `jellybean/transcriptions/NJellyBeanMain.jsp` |
| E | `a#jellybean-panelLink19` | `jellybean/refillrequest/EJellyBean.jsp/Refill Requests/Success` |
| **S** | `a#jellybean-panelLink22` | `jellybean/officevisit/officeVisits.jsp` |
| D | `a#jellybean-panelLink29` | `jellybean/reviewdocs/ReviewDocsWeb.jsp` |
| R | `a#jellybean-panelLink33` | `jellybean/referral/referral.jsp/Outgoing` |
| T | `a#jellybean-panelLink37` | `jellybean/telephoneencounter/JellyBeanT-Telephone-Encounter-ListView.jsp` |
| L | `a#jellybean-panelLink52` | `jellybean/labs/JellyBeanL-Lab-DI-Procedure-ListView.jsp/all` |
| M | `a#jellybean-panelLink58` | `jellybean/messages/MjellyBean.jsp/Inbox` |

All nine read `0` on the recorded account. The `panelLinkNN` numbers are assigned per
user layout: they held across four sessions on one account, but the durable form is the
href, and the href form was derived from the recorded DOM rather than separately
click-tested. Verify it on the first run and keep the number as the fallback.

## The navigation

**Get there** click the hamburger, `a#jellybean-panelLink4`.

The left rail, top to bottom: `Favorites, Menu, Practice, Registry, Referrals, Messages,
Documents, Billing, Analytics, healow, Admin, ASC, EVA, healow Insights, University,
SCR`. Each is `a.cursor`, and they carry **no id**, so match them by exact text.

**Favorites was empty on the recorded account**, rendering "No Favorites configured".
Anything that tells an assistant to use a favorite is wrong until somebody configures
one.

**Menu** opens a full mega-menu with its own search box and eleven tabs:
`File | Patient | Schedule | EMR | Billing | Reports | CCD | Fax | Tools | Community | Help`.

**Practice** is the scribe's menu. Its items, exactly as they render:
`Resource Scheduling (CTRL+ALT+R)`, `Centralized Contact Center and Scheduling`,
`Out-of-Office Visits`, then the practice's own providers by name, then
**`Office Visits (CTRL+SHIFT+O)`**, **`Review Actions`**, `Patient Pre-registration`,
`Interface Dashboard`, `Scheduling Intake Form Configuration`,
**`Progress Notes (CTRL+ALT+VN)`**, `Telephone/Web Encounters (CTRL+SHIFT+T)`,
**`Lookup Encounters`**, **`Review Progress Notes`**,
`eClinicalMobile Patient Registration`, `Billing Summary`, `Interface Reconciliation`,
`Out Of Office Billing Summary`.

### The id convention, the most reusable thing on this page

A menu leaf carries an id of **the item text uppercased, spaces as underscores, then an
underscore and the parent menu**. Verified live:

```
REVIEW_PROGRESS_NOTES_PRACTICE     REVIEW_ACTIONS_PRACTICE
PROGRESS_NOTES_PRACTICE            LOOKUP_ENCOUNTERS_PRACTICE
TEMPLATES_FILE                     ACTION_TEMPLATE_FILE          LOOKUP_PATIENT
```

So a menu item is reachable as `#REVIEW_ACTIONS_PRACTICE` without hunting for text. Open
the rail and the parent menu first: the whole tree is in the DOM once the rail is open,
but a leaf has zero width until its parent is expanded.

### The safety note that was learned the hard way

The first rail entry in DOM order is **`Log out`** (`a#jellybean-panelLink10`), and the
expanded tree also holds `New Action`, `New Telephone Encounter`, `Create New Messages`,
`Change Password`, `Patient Merge` and `Set Out of Office`. Anything that iterates over
discovered links will log itself out on the first step, or worse. **Click named targets
only. Never enumerate and click.**

## Office Visits, the day's schedule

**Get there** `a#jellybean-panelLink22`, or Practice > `Office Visits` (CTRL+SHIFT+O)
**Anchor** `table#officeVisitsTbl1`, plus the module title "Office Visits"

The date control at the top reads `< MM/DD/YYYY >` with a calendar picker, and it opens
on today.

Filters: `Provider` (`input#provider-lookupIpt1_9715`, defaults to "All"), `Facility`
(`input#single-facility-lookupIpt1_8504`, empty), a checkbox "Include appointments with
Resources", `Appt Time` (`select#officeVisitsSel5`: All Day, Morning, Afternoon), `View`
(`select#officeVisitsSel6`: All, Checked In Only, Checked Out Only, Locked Only,
Unlocked Only, Ready To Lock), `Sort by` (`select#officeVisitsSel7`: Appt Time, Patient
Name, Check In Status), and `button#officeVisitsBtn6` **Filter**.

Grid columns, in order:

```
Visit Type | Appt Time | Appt Date | Patient Name | Insurance | P/R | Reason | Sex |
Age | Visit Status | HCC Un-Reviewed | QM (O/W) | Arr Time | Duration | Room | Status |
Cycle Time | Notes Sts | VBC Gaps | Healow Connect
```

Row action bar: `Room In/Out`, `Billing Data`, `View Orders`, `eCliniForms`, `Send TV
Message`, `Messenger`, **`Hub`** (`button#officeVisitsBtnPH1`, the Patient Hub for the
selected row), **`View Progress Notes`** (`button#btnViewPN`), **`Lock Progress Note`**
(`button#officeVisitsBtn13`), `Copy`, `Activity`, `Connect`, `Global Alert`. Paging is
`select#officeVisitsSel8` (25/50/100/Autofit) with Prev and Next, and the count reads
"Total Counts : N" at the bottom right.

**What matters here.** `Notes Sts` is the note-status column the work is read from.
`Hub` and `View Progress Notes` are the two ways off this screen into a chart.

**`button#officeVisitsBtn13`, Lock Progress Note, is forbidden.** It sits two buttons
away from `View Progress Notes` and it is a one-click irreversible clinical act. It is
named here by selector so there is no ambiguity about which control is meant.

## Review Progress Notes, the pending-notes queue

**Get there** rail > Practice > `#REVIEW_PROGRESS_NOTES_PRACTICE`
**Anchor** `table#ReviewProgressNotesTbl1`, module title "Review Progress Notes"

This is the queue a scribe lives in, and it opens pre-filtered to the signed-in user:

```
Provider     : All Providers          input#provider-lookupIpt1_0783
Assigned To  : the signed-in user     input#staff-lookup_staff4480_Ipt1   (clearable)
Status       : All Open               select#ReviewProgressNotesSel2  (All / All Open / Addressed)
```

Columns: `PATIENT NAME | STATUS | DATE | PROVIDER | REASON | ASSIGNED TO | STATUS`.

Buttons: `Patient Hub` (`button#ReviewProgressNotesBtn1`), **`Lock Progress Note`**
(`button#ReviewProgressNotesBtn2`, **forbidden**), Prev, Next. Page size is
`select#ReviewProgressNotesSel3`.

**Read an empty result correctly.** With nothing in the queue the footer reads
`Total Counts :` with no number and `Page 1 of NaN`. That is what eCW renders for an
empty result set. It means zero. It does not mean the screen broke.

## Patient Lookup, the door to the Patient Hub

**Get there** the patient-search control in the top bar, `a#jellybean-panelLink65`
**Anchor** the dialog titled "Patient Lookup"

Search form: `Primary Search` with a field picker (Name, DOB, Sex, SSN, Acct No (MRN),
Phone (C/H/W), Guarantor Name, Guarantor Phone, Subscriber No, External MRN, Previous
Name, S Discharge Date, S Facility Name), a `Secondary Search` on the same field list,
`Status` (Active), `Facility` (All), and a `Search` button.

Result grid columns: `Pt. Alerts | Last Name | First Name | Middle Name | DOB | Sex |
Acct No (MRN) | Phone (C/H/W) | Guarantor Name | Last Appt`.

Bottom buttons: `Quick Reg + Quick Appt`, **`New Patient`** (forbidden), `Family Hub`,
`Patient Demographics`, **`Patient Hub`**, `Cancel`.

No search was run during the recording, so the grid is empty and no chart was opened.
This is the recorded structure of the door. What is behind it is not recorded.

**What matters here.** `Acct No (MRN)` is the stable handle. Search by MRN whenever you
have one. A name search returns a grid the assistant then has to disambiguate, and that
is exactly where a wrong-patient read starts. A name that matches two people is two
answers, not one list: say so and ask, rather than picking.

## Review Actions, the actions list

**Get there** rail > Practice > `#REVIEW_ACTIONS_PRACTICE`
**Anchor** `table#actionListTbl1`, module title "Review Actions"

Status tabs across the top right:
`All | Open | All Open(All Dates) | All Open(As of Today) | Addressed | Cancelled`. It
opens on **All Open(As of Today)**.

Filters: `Provider` (All), `Assign To` (defaults to the signed-in user), `Action Type`
(`select#actionListSel1`), `Created By`, `Facility` (All), `Patient` (All), `Subject`
free text, and a Filter button.

The eight `Action Type` values, which are eCW's own list:

```
All | Ultrasound | Procedure | Follow up | Patient Inquiry | CPT Inquiry |
Collection Query | Claim Query
```

Columns: `PATIENT NAME | DUE DATE | STATUS | ASSIGNED TO | ACTION TYPE | SUBJECT |
CREATED BY | START DATE | FACILITY`.

Buttons: **`New`** (`button#actionListBtn4`, forbidden), **`Reassign To`**
(`button#actionListBtn3`, forbidden), Prev, Next.

**What matters here.** Those eight action types are the vocabulary any practice's own
actions procedure is built on. A practice's action *templates* are a local fact and
belong wherever this install keeps its own settings, never in this skill.

## The other three queues

Recorded because they are one click away and the work runs into them.

- **T, Telephone/Web Encounters.** Anchor
  `table#JellyBeanT-Telephone-Encounter-ListViewTbl1`. Columns
  `T/W | V | Ref # | Date | Patient Name | Provider | Reason | Phone | Assigned To | Facility`.
  Buttons Filter, Delete, Reassign To, Messenger, New. Delete, Reassign To and New are
  forbidden.
- **D, Review Documents.** Anchor `table#ReviewDocsWebTbl1`. Columns
  `Scan Date | Patient Name | Custom Name | Assigned To | Description | Tags | Facility`.
  Buttons View Document, Bulk Actions, View Worksheet, Delete, Reassign To. The
  Assigned-To filter defaults to "Me". Bulk Actions, Delete and Reassign To are
  forbidden.
- **L, Labs / DI / Procedures.** Anchor
  `table#JellyBeanL-Lab-DI-Procedure-ListViewTbl1`. Columns
  `O | S | Order Date | Coll Date | Result Date | Patient | Labs/Imaging/Procedures | Reason | Interface Status | Result | Assigned To`.

## Lookup Encounters, the retrospective search

**Get there** rail > Practice > `#LOOKUP_ENCOUNTERS_PRACTICE`

This is how to reach a past encounter once the schedule has rolled over. Filters:
Service Date range, Date of Birth range, Place of Service, Visit Status, Visit Types,
Sort By, Diagnosis (ICD), Procedure, RX, Appointment Facility, and a "Show Unique
Patient" checkbox.

Grid: `PATIENT NAME | DOB | SEX | AGE | TELEPHONE | WORK TELEPHONE | ACCOUNT NO.`, with
`Patient Hub` (`button#encounterlookupBtn4`) on the action bar.

## UNRECORDED: the Patient Hub

**Not recorded, deliberately.** Reaching it means opening a real patient chart, which the
recording session was told not to do, and the Hub is per-patient so there is no empty
version of it to capture.

What **is** recorded is every door into it:

- `Patient Hub` on the Patient Lookup dialog
- `button#ReviewProgressNotesBtn1` on Review Progress Notes
- `button#encounterlookupBtn4` on Lookup Encounters
- `button#officeVisitsBtnPH1`, labeled `Hub`, on Office Visits

Describe the Hub as the screen those four buttons open, and say plainly that its
internals have not been mapped. `tasks.md` carries what a practice's own written
procedure says is on it, and that section is marked as coming from the procedure rather
than from a recording, because it is.

## UNRECORDED: the progress-note form, and the clean proof of why

**Attempted** rail > Practice > `#PROGRESS_NOTES_PRACTICE`.
**What happened** eCW popped a modal titled **"Progress Note"** reading **"No encounter
opened after Login."** with a single OK button.

That is an answer, not a failure:

> **The progress note is not a place you can navigate to.** It exists only in the
> context of an encounter that has been opened first, from Office Visits or from the
> Patient Hub.

Carry that exact error string. An assistant that meets it has taken a wrong turn, and
should not conclude the application is broken or that the patient has no note.

## UNRECORDED: My Favorite Templates

Not in the main menu. The recorded navigation tree holds six entries with "template" in
the name and none of them is this one: `TEMPLATES_FILE`, `ACTION_TEMPLATE_FILE`,
`ALERT_TEMPLATES_ALERTS`,
`IMMUNIZATION_TEMPLATES_IMMUNIZATIONS/THERAPEUTIC_INJECTIONS`,
`MESSENGER_TEMPLATES_MESSENGER`, `EDIT_HCFA_TEMPLATE_HCFA_MAPPINGS`. The rail's
`Favorites` reads "No Favorites configured".

My Favorite Templates is a control **inside the progress note**, so it sits behind the
same wall as the note itself.

## What it would take to close the three gaps

One recording session of about ten minutes, with a person at the practice agreeing which
patient may be opened. That opens a chart, which opens the Hub, which opens an encounter,
which is the only place the progress note and its template list exist. Until then these
three sections stay marked UNRECORDED, and an assistant says so rather than improvising.
