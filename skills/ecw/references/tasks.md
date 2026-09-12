# The eClinicalWorks controls behind the everyday work

Where the other reference files describe screens that were recorded, this one describes
the **mechanism** a practice's own written procedures walk through: the patient hub, the
documents viewer, the anatomy of a progress note, the template merge, the fields on an
action, and the structured-data default step. It is eCW's own user interface, so it
belongs with the system and not with any one customer.

## Two labels to keep straight while you read this

**FROM THE PROCEDURE, NOT OBSERVED.** Everything from the progress note downward on this
page comes from a practice's written procedure rather than from a recording. The note
form has never been captured, because eCW itself refuses to open one outside an
encounter (see `screens.md`). Treat every control named here as a description of what a
person told us is there, not as a selector somebody proved.

**Values are not here, and must not be added here.** Which template a practice merges,
who its actions are assigned to, which facility a visit belongs to, what counts as a
relevant medication, how it writes a wound line, which risk boxes it ticks: all of that
is a fact about one install. It lives wherever this install keeps its own settings. This
file names the CONTROL. Something else names what to put in it. **Where the two
disagree on a detail, the local instruction wins**, because it was written by the people
who use that install.

## Nothing on this page is a write instruction

Every procedure below ends in an OK or a Save, and this skill presses neither. Read
`SKILL.md` again if that seems inconvenient: a note, an action, a demographic field and a
setting are all somebody's medical record.

What this page is for is twofold. Reading a chart intelligently means knowing what the
sections are called and where they sit. And on the day somebody with the authority to do
it decides an assistant may draft or file, the mechanism is already mapped, and the only
new thing is the permission.

## The Patient Hub

The patient's central dashboard in eCW: records, actions, billing and encounter history
in one place. It is per patient, so there is no empty version of it and it has never been
recorded.

Four controls open it, all of them recorded, all of them on screens in `screens.md`:

- `Patient Hub` on the Patient Lookup dialog
- `button#ReviewProgressNotesBtn1` on Review Progress Notes
- `button#encounterlookupBtn4` on Lookup Encounters
- `button#officeVisitsBtnPH1`, labeled `Hub`, on Office Visits

From Patient Lookup the route is: search the patient, click the name, and the Hub opens.
Search by `Acct No (MRN)` whenever you have one. A name search returns a grid you then
have to disambiguate, and a name that matches two people is two answers, not one list.

The Hub carries an `Action` dropdown, which is where actions are created and viewed
outside an encounter.

## Patient Docs, the documents viewer

The route through the chart to a scanned or received document, including a referral:

```
Patient Docs (dropdown) > Patient Doc - Web Mode > Patient Documents
    > open the document
    > Close
```

Documents are labeled by the practice, so the label that identifies a referral is a local
fact rather than a system one. **Close** is the way out, and it is a read the whole way:
nothing on this route saves anything.

## The progress note

FROM THE PROCEDURE, NOT OBSERVED.

The note is not a page you can navigate to. It exists only inside an encounter that has
been opened first, from the day's schedule or from the Patient Hub. eCW says so itself,
in a modal reading "No encounter opened after Login."

The way in from the schedule is to click the patient's name in the appointment list.

### Its anatomy, and how each part is edited

| part | what it is | how it is edited |
|---|---|---|
| **My Favorite Templates** | the provider's saved note templates, listed inside the note | click the arrow next to a template to **merge** it into the note |
| **HPI** | History of Present Illness, the narrative section | the edit icon under the section heading opens it for typing |
| the opening demographic line | the first sentence of the HPI, carrying age and gender | click it to edit |
| a **placeholder line** | a line a merged template leaves for a value | double-click it and type the value over it |
| **Pertinent Medical History** | a checklist of risk factors | click the text under the heading to open the checklist, tick, then OK |
| **Assessment** | the encounter's diagnoses | the add-assessment icon opens a search; clicking a result adds that code to the encounter; then OK |
| **Plan > Treatment** | where an action is created from inside the note | see the actions section below |

### Three mechanics worth knowing before you read a merged note

1. **A merged template carries defaults, and one of them is demographic.** A template
   written for one demographic fills the HPI opening line and the physical exam with that
   demographic's wording, and it is corrected by hand afterward, in both places. So a
   sentence in a freshly merged note may describe a template rather than a patient. Do
   not read one as evidence.
2. **A checklist does not read itself off the narrative.** Ticking a risk box is a
   separate act from typing the history into the HPI, so a note whose narrative mentions
   a condition may still have that box unticked, and the reverse. Read the checkbox, not
   the prose, when the checkbox is the question.
3. **OK is a save.** OK on the HPI editor, on the risk-factor checklist and on the
   assessment search all commit. This skill does not press them.

### Reading a chart section without touching it

The narrative sections render as text on the note. Read them from a snapshot. The moment
a read needs an edit icon, a double-click on a placeholder, or a checklist to be opened,
it has stopped being a read: say what you were trying to find out and leave the note as
you found it.

## Actions

FROM THE PROCEDURE, NOT OBSERVED for the dialogs. The `Review Actions` list itself was
recorded and is in `screens.md`.

An **action** is eCW's workflow task: the thing that makes a follow-up or a procedure
actually get booked rather than sitting in a note nobody reads.

### The field set on the action dialog

The same fields appear whichever route opens the dialog:

| field | what goes in it |
|---|---|
| **Facility** | the clinic location the visit belongs to |
| **Action Type** | one of eCW's own eight types, listed in `screens.md` under Review Actions |
| **Subject** | the task in words |
| **Assigned To** | the person who will do it |
| **Priority** | Normal or High, on the edit dialog |
| **Merge Template** | bottom left of the dialog: fills type, subject and assignee from a saved preset |
| **Structured Data** tab | the standardized chart fields, see below |

### The Structured Data step, and why it is called out

```
Structured Data tab > the dropdown arrow next to Default For All > Default Templates All
```

This is done before the dialog is closed, on **every** route below. Skipping it is what
leaves records inconsistent across a practice, which is a data-quality problem nobody
notices for months. If a written procedure names one step twice, it is usually this one.

### The four routes to an action

**1. From inside the progress note.** Plan > Treatment > `Add` > `Action`. Fill Facility,
Action Type, Subject, Assigned To. Structured Data > Default For All > Default Templates
All. Back to the Action tab, check it reads right, OK. Use this while the note is being
written, so the follow-up is created in the same pass.

**2. From an action template.** `Add` > `Action` in the Treatment toolbar. Select the
Facility. `Merge Template` at the bottom left. Tick the template, Ok. Edit the Subject if
the interval or the instruction differs from the template's, which is how a template for
one interval becomes a task for another: **edit the text rather than hunting for a second
template**. Structured Data > Default For All > Default Templates All. OK.

**3. From the Patient Hub, with no encounter open.** Patient Lookup in the top
navigation, search the patient, click the name to open the Hub. `Action` dropdown >
`New Action`. Select the Facility. `Merge Template`, pick the procedure template, Ok.
Update the Subject if a different procedure is required. Structured Data > Default For
All > Default Templates All. OK. This is the route when a provider asks for something to
be tasked after the fact.

**4. Viewing and editing an existing action.** Patient Hub > `Action` dropdown >
`View Action`. Click the action to change. Edit the Subject with the new timeframe or
instruction. The `Priority` dropdown moves Normal to High.  OK.

> **Only while the task has not been started.** Once it is started it is somebody else's
> work, and eCW will not let it be edited.

### One structural rule that is eCW's, not a practice's

**An imaging study is an order, not an action.** Diagnostic imaging goes in as a
diagnostic imaging order. Creating an action for one puts it in a workflow queue instead
of an order queue, where it does not get booked. Written procedures tend to call this out
first because it is the mistake people make first.

Who an action is assigned to, and which templates exist, are local facts. They are not
here.

## Copying between systems

A pre-charting procedure typically reads from a facility's own record system and types
into eCW. That other system is a different door with its own skill, and which vendor it
is varies per site. Two mechanics belong here because they are about the eCW side:

- **An impression is not a report.** When a procedure says to copy a study's impression,
  that means the impression line, with the study label and its date typed in first so the
  note says where the finding came from. Pasting a whole report into a narrative section
  is how a note becomes unreadable.
- **A structured value goes over its placeholder**, by double-clicking the placeholder
  line, not appended after it. A merged template's placeholder that is still sitting
  there is a gap somebody can see. One that has been typed over reads as a finding.
