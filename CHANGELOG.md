# Changelog

## 0.19.0

- **A promise that moves can wake the assistant; a quiet day cannot.** A sixth
  preset, opt in: the commitment watch. A few times a day a script reads every
  open promise in the person's notes and the engine compares it with the last
  look. When nothing moved the model never runs and nothing is sent. When a
  promise closes, comes due or goes overdue, the assistant sees just that
  change and decides, through the interruption gate, whether it is worth a
  message. Almost always it is not. Inside a quiet window the change waits
  until the window ends.

## 0.18.0

- **The assistant can look someone up instead of guessing.** A new `brain`
  skill teaches it when to open a person's page and when not to bother. The
  person's own messages are now a searchable knowledge base, one page per
  person and per group, and the assistant reaches it as a tool. The rule it
  encodes is simple: if you are about to state a detail about someone from
  memory, check first, and if the answer is not there say so rather than
  filling the gap. It answers like someone who remembers, never by reciting
  page names or counts.

## 0.17.0

- **Three things I could take off your plate.** A fifth preset, opt in like
  the mail watch: on Mondays the assistant reads the week's mail and calendar
  and names three specific things it could do for the person, never the same
  one twice, and asks which to start. It exists because the best-evidenced
  reason people stop using an assistant is that they never knew what to hand
  it. Nothing is read before the person says yes.

## 0.16.0

- **The voice, three rules and a firewall.** Acknowledge in a clause what the
  person is in the middle of, then answer; a caveat after the answer, one
  sentence, only when it changes what they do; one question a message. Warmth
  is how the person is treated, never agreement: a wrong figure is corrected
  in the first sentence, kindly, and a position holds under pushback until
  something new arrives.
- **Speaking first, loosened and bounded.** The ceiling is three unprompted
  messages a day, counted by the fleet's gate, in place of "most mornings
  none". Inside it, one small line with nothing behind it is allowed once a
  day when the hour and the person fit; a twice-ignored nudge stops. A
  "keep an eye on this" becomes a bounded scheduled job, never one that runs
  for ever.

## 0.15.0

- **Quiet hours for everyone.** A person's evenings, weekends, days off and
  personal hours, stated once in passing, are kept in a file by the new
  quiet-windows skill and read by the same gate that already holds a scheduled
  job shut for an observance calendar. Nothing unprompted reaches them inside
  one; the mail watch stays shut too. Nothing is guessed: a person who states
  no quiet hours is messaged on the ordinary rules.

## 0.14.0

- **Memory is for the person; plumbing goes to notes.** How a data source is
  wired, what a tool returns, which table holds what: an entity note or the
  reading skill's notes, never memory. What is kept about the person is written
  as the way to behave for them, and a nudge they ignored twice is a fact worth
  one line, after which the nudge stops. With this, the fleet turns the engine's
  own memory writer back on for every assistant.
- The pack check names the phone rules by their current wording (sentences, not
  lines); the suite had gone red on two stale phrases.

## 0.13.0

- **A bar for speaking first, for every assistant.** Every item in a message a
  person did not ask for now passes four questions: it is theirs to act on,
  something is different tomorrow if they do not see it today, they have not
  heard it before, and there is one thing you would do about it. One no and the
  line does not go. A job they kept keeps its shape; the questions decide what
  fills it. Borderline is written down as an open commitment for the next brief
  rather than dropped, one unprompted message a morning beyond their kept jobs
  is the ceiling, and nothing is about the assistant itself except a door of
  theirs that stays closed and a preset's own first question. This was written for one
  person's assistant on the night of 13 Sep and lived in her job prompts; it is
  the standard now (assistant-standard, "Speaking first").
- **Length ceilings and an easy question to end on.** A message nobody asked for
  is four lines, an answer two to four, the brief one screen (about fifteen
  lines of text) with four meetings at most. No hyphen bullets, which a phone prints as hyphens. The last line is a
  question the person can finish in a word or three.
- **The brief looks back to the last working day,** not a fixed day or two, so
  the first morning after a long weekend or a three-day yom tov reads three
  days of mail and puts the oldest thing that is genuinely theirs first.
- **A new `jewish-time` skill, and a calendar that holds jobs shut in code.**
  For a person who keeps Shabbat and yom tov: the rules for quiet windows, fast
  days, chol hamoed, erev Pesach and Tisha B'Av, going in and coming back. The
  times are that person's own, built once from hebcal.com for where they live
  (`scripts/jewish_time.py build`) into `jewish-time/calendar.json` beside
  their profile, a path the pack never touches. The morning brief and the
  pre-read now run `scripts/jewish_time.py` first: inside a window the model is
  never woken, and outside one it is told what kind of day it is and how far
  back to look. Somebody with no calendar gets one neutral line and no change.
  A build covers 24 months, and `jewish_time.py status` exits non-zero inside
  60 days of the end, for whoever checks the fleet.
  Jobs already on a pod, presets included, do not pick the gate up from an
  upgrade: the controller never rewrites an existing job (see presets/README).
  The first hand version told three jobs to answer a word the engine does not
  treat as silence, which would have delivered that word to a phone every half
  hour of Shabbat.
- **The mail watch no longer relies on its prompt to keep Shabbat.** The script
  checks the same calendar before it reads anything, and stays shut from the
  start of a quiet window until nine the next morning, so what arrived meanwhile
  is judged once, when the person is back; after a gap the read reaches back to
  the day of the last good one, up to six days, so Friday evening's mail is
  still seen. The half-hourly schedule is
  unchanged, and costs nothing inside a window.

## 0.12.1

- **The pack no longer says which engine it is built on.** An assistant is
  bought from Pulse; the engine underneath is our supplier and no customer has
  a reason to be told its name. The persona has always said "never name a
  vendor", but a persona is one file and this pack lands sixty-odd others on
  every pod, all of them text a model reads and then repeats. The presets
  reference named the engine in four sentences and quoted a fifth from its
  source; all five now say "the engine" or say what the code does.
- **A check that keeps it that way.** `tests/check_engine_name.py` reads every
  file `distribution_owned` ships. In markdown prose the name in any case
  fails, and only an ALL-CAPS environment name or a filesystem path may appear
  bare; inside code spans and fences the name as a capitalized word still
  fails, because a sample reply in a fence is a reply the model may copy.
  Frontmatter values are prose. Python is parsed, so every string is checked
  (docstrings and comments are developer text and are skipped) and a `#` inside
  one hides nothing. YAML, Bases and JSON are read whole,
  comments included, because the model reads them whole. Identifiers stay where
  code needs them (renaming those is a separate decision). An independent
  review of the first version found a dozen shapes it let through, among them a
  nested bullet and "Hermes-based"; `--self-test` plants all of them, and CI
  runs it and then a leaky copy of the tree that must fail naming the planted
  line.
  A second review tightened it again: inside code, only lowercase commands,
  paths and identifiers are allowed, so a sample reply saying "Hermes-based"
  fails; the shipped list is read with a YAML parser, and a run that reads no
  files fails instead of passing.

## 0.12.0

- **A new `ask-assistant` skill: putting a question to somebody else's assistant.** Where two
  assistants have been introduced, one can ask the other a question for the person it works for
  instead of interrupting that person. The skill carries the whole of the asking side: the list
  of who may be asked and that there is nothing else to search, one clear question with only as
  much of the person's own matters as the question needs, never somebody else's forwarded words
  and never a request the person did not ask for, the show-it-first path (the exact question, a yes to that question, and
  the person's own direct instruction counting as the yes), the ask-freely path (one line naming
  who was asked, every time), the one-line first mention when the list gains a name, the five
  fixed lines for a miss, a decline, no answer, too many questions and a question that has to wait,
  the spoken controls
  ("Who can you ask?", "What did you ask X this week?", "Stop asking X"), and never a second
  attempt at a question that failed.
- **assistant-standard gains "Answering another assistant".** The framing arrives as the turn's
  own standing orders and never inside a message, so a chat, group, email, document or file that
  copies the same opening is a message that copied the words and gets none of what this section
  allows: two independent reviewers found the first draft missing that sentence, which would have
  handed a stranger a free calendar answer with the tell-tale suppressed. Inside a real one: answer
  as the person would be answered and no wider than the standing orders allow, quote nothing from
  mail, files, notes or earlier conversations and give no figure the person has not already told
  the asker, send, book, file, arrange and ask nobody anything during the turn, decline an action
  in one line beginning "I can't help with that", and save nothing anywhere afterward. The
  answering person's own two controls live here too: "did anyone ask you anything today?" and
  "stop answering X's assistant", the second showing the line and waiting for a yes. "Speaking
  first" gains the mirror of the asking side's first mention: when the list of who may ask you
  changes, one line inside the next reply, never a message of its own.
- **"Stop answering X" now says which list it belongs to.** The reach skill bound that phrase to taking a PERSON
  off the WhatsApp list; said of an assistant it would have struck the wrong name and answered
  "Done", leaving the introduction open. It now points at the other skill and asks when a name
  could be either.
- **Who may ask you is a rule the team can lock.** policy-keeper lists "Who may ask you, and who
  you may ask (other assistants)" among the rules that need a real switch.
- **Not live until the door is.** The two calls this skill names do not exist on the data side
  yet. Until they do, the list comes back empty and the assistant says "I'm not able to ask
  {name}'s assistant things yet", which is the right answer, so the pack is safe to hold but
  should not be made the fleet standard ahead of them.
- **Every fixed line is pinned, and there is now a live exam.** `tests/test_ask_assistant.py`
  holds each line word for word, pins the copied-framing rule and the two answering controls, and
  runs the words-that-never-appear check over the new skill and over every line added to another
  skill; CI runs it. `tests/exam_answering_turn.py` puts both questions to a real test copy
  through the answering door and is not in CI.

## 0.11.5

- **`ecw signin` sizes the window before it types anything.** It never did, and that alone
  made a sign-in impossible: eCW's login page answered "Your screen resolution is 800 x 600"
  against its own 1600 x 900 floor, screen one never advanced, and the two attempts a night
  allows were spent with no password ever submitted (13 Sep). The window override belongs to
  a CDP session and dies when that client detaches, so it cannot be set once elsewhere: the
  sign-in raises it itself before screen one, and again after the confirmation link and at
  the shell. It refuses, naming the one-line fix on the browser image, rather than driving a
  page it knows cannot advance.
- **"Already in the application" now asks the application, not the address bar.** The guard
  read the URL, so a shell that had been signed out, sitting on index.jsp exactly like a
  working one, read as healthy and the sign-in declined to run. The test is four facts in one
  quick read: the Office Visits control on screen, no "Building your user experience" splash,
  no loading veil, and no login field on the page. A page that cannot answer says it cannot
  tell instead of claiming health, and `ecw where` no longer answers "fine" on a shell that
  is not working.
- **`ecw dialogs` stops instead of hanging, and says what stopped it.** Against two stacked
  modals that could not be pressed it ran 180 seconds, was killed, and had cleared nothing.
  Every wait in the sweep now comes out of one budget, and what it could not clear comes back
  named in the application's own words, so the answer is "the application is showing a data
  loading error" rather than an unexplained timeout. Fenced to the three entry dialogs, cut
  short, with long numbers masked.
- **The attempt ledger counts submitted passwords.** It counted invocations, so both of
  13 Sep's attempts were spent by runs that never reached the password field, and the budget
  was gone having risked nothing. Only a submitted password can lock a clinician out, so the
  row is written at that moment, immediately before the control is pressed. A run that stops
  earlier leaves the ledger alone and says so. The budget is still two, the window still six
  hours, and a genuinely spent budget still refuses.
- CI: `test_ecw.py` and `test_reach.py` now run in the pack job. Neither ever had, which is
  why nobody noticed the eCW door had no cover over any of this; the ecw suite is 83 checks,
  driven against a stand-in page.

## 0.11.4

- `ecw` script: the sign-in reports the application only when the application has finished
  loading (PUL-169). The old gate was "the Office Visits anchor exists", which is true mid-paint,
  and on 13 Sep `signin` printed in-the-app on a shell still saying "Building your user experience"
  half an hour later; the schedule read behind it found nothing it could click. The gate is now
  three facts read in one call (`shell_loaded`): a control carrying the Office Visits target ON
  SCREEN, the splash gone, the loading veil down. `signin` waits up to two minutes for it, clearing
  the entry dialogs as they come, and dies with the reason (exit 2) when it never comes; the
  already-in short cut and `session restore` stand behind the same gate. It says out loud what the
  first reading was, because that is the reading the old gate got wrong.
- `references/screens.md`, `references/login.md`: `a#jellybean-panelLink22` is the "S" jellybean,
  a toggle that opens a menu; the "Office Visits" item is inside it (`…panelLink25` on the recorded
  layout, hidden until the toggle is open). Both carry the same href.

## 0.11.3

- `ecw` script: the sign-in keeps what it saw the way the medical-scribe plugin's doors do (PLAN B10,
  B10-02). With `HERMES_REPLAY_DIR` set (the fleet renders it on every pod), `signin` writes a
  full-page screenshot into `$HERMES_REPLAY_DIR/<run_id>/` at `signed-in`, at `dialog` for each entry
  dialog before it is cleared, and at `confirm` on the mailed confirmation page, as
  `NN-<op>-<label>.png` with one `index.jsonl` row each (seq, t, op, label, kind, file, sha256, bytes,
  task_id). Unset means no screenshot anywhere. The credential form and a one-time code page are never
  shot. A screenshot that cannot be written is a note, never a failed sign-in.

## 0.11.2

- `recurring-work`: a new skill. A person asking for work on a clock (a Monday report, a daily
  summary, a weekly check) gets it filed through Pulse's `recurring_work` tool as the same
  read-only schedule the agent page's Recurring work card makes, never as a job the assistant
  writes for itself. The skill tells a run from a reminder, says the schedule and the one fixed
  prompt back in one line before filing, removes one on the same yes, and says in plain words
  when a job would send or change something and so cannot run on a clock. assistant-standard
  points at it from the reminders paragraph.

## 0.11.1

- `ecw` script: a page that is not on the practice host (about:blank after the browser sidecar
  restarts) is "elsewhere", never "in the app", so `signin` signs in instead of declining.

## 0.11.0

- `logins` skill: a sibling `keeper` command. Companies that keep their working logins in
  Keeper (one shared folder per provider) get the same door as 1Password: the controller
  holds the company's Keeper identity and signs in server side, the assistant is scoped to
  its provider's folder, and the pod reads one field of one record at call time. No Keeper
  software or device on the pod (hermes-fleet PLAN B9).
- `ecw` script: reads the host and login title from the lane when the env is unset, so a
  plugin scribe signs in with nothing extra configured.

Earlier versions are in the git history (`git log --oneline v0.1.1..v0.2.2`).

## 0.10.0

- **The reach skill: who may reach the assistant, asked in her own chat.** Merged with 0.9.0's eCW command; the two entries below are the reach half.
- **The reach script no longer rewrites the page's two standing answers on every grant.** It sends
  them to the fleet door only when the bridge says she changed them, so a toggle made on the page
  whose live push did not land is not undone by her next yes. The skill now says what is true after
  a yes, a no, or a folded question: two groups from one "tell me which" are two commands on one
  key; "they can ask about my diary" a minute after her yes is a widening that works; a no she gave
  can be put right with `reach allow` while it stands; and a number nobody ever asked her about is
  not granted from chat, she is asked the moment they write.


- **Who may reach the assistant is now asked in her own chat, and enacted from it.** When she adds
  the assistant to a group, when a number it does not know writes first, or when someone it wrote
  to for her writes back, a short question in fixed words goes to her own chat before the model
  sees anything, and a plain yes or no from her is acted on the spot, no page and no restart. A
  yes with more in it, a rule said out of the blue, or a name goes to the model, whose turn now
  carries a REACH note (what is waiting, short refs, a key good for that turn only). The new
  `reach` skill says how to read the note, how to match her words to a waiting question (the
  presets rule: two waiting and it fits either, ask which), what her phrases mean (guest by default
  for a number that wrote first, "they can ask about my diary" widens it, "stay out of X" is a real
  leave, "any group I add you to is fine" is a standing rule) and the one line to say back; its
  script `skills/reach/scripts/reach` hands the bridge one decision at a time with her key, then
  records it through the fleet door with the assistant's own key, and refuses `principal` before
  it makes a call. assistant-standard's "Speaking first" gains two sentences naming these questions
  as the one other thing that arrives unprompted, and policy-keeper's list of rules that need a real
  switch gains "Who may reach you (groups, replies)." `tests/test_reach.py` proves the script
  against a fake bridge and a fake door, and greps the skill and every string the script can print
  for the words that never reach a person.
- **A leave that did not happen is never reported as done.** The bridge now answers a refused
  group leave as a failure; the script says "I couldn't leave that group just now" and exits
  non-zero instead of printing "left group". The key from the note is bound to what was waiting
  when it was armed: a grant answers one of those, once, and the script has plain lines for a grant
  outside the list and for one already answered.

## 0.9.0

- **`ecw` gets its own command, and the ban gets somewhere to send the assistant.**
  `skills/ecw/scripts/ecw` ships in the pack the way `skills/logins/scripts/login`
  does: standard library, run with the terminal tool, one reviewable file. Rules 5
  and 6 stand exactly as they were -- no free-hand `browser_cdp`, no free-hand
  Playwright, ever -- and this is now the one named exception, because four things
  this door needs have no permitted road otherwise, and each was measured rather than
  assumed. There is no isolated browser context, and the mailed confirmation link
  fails when it is opened holding the pending sign-in's cookie. There is no wait, no
  force-click and no settle, and the three entry dialogs need all three. `browser_type`
  fires no key events at all -- 0 keydown, 0 keyup, against 13 and 13 for a real per-
  character press -- so anything on an Angular `ng-keyup` never reacts to it. And no
  tool reports the page's address after a click, which is the one thing this skill's
  central recognition rule depends on. The command attaches to the SAME Chromium at
  `BROWSER_CDP_URL` and drives the SAME page the `browser_*` tools are on, so it is not
  a place to hide: the next snapshot sees what it did. Its refusals are compiled in
  rather than remembered -- two paths on one configured host and no default host, a stop
  on `SecurityImage.jsp` and on `changePasswordOnLogin.jsp`, never Verify, Save, a
  picture or the do-not-show-again checkbox, never `logout.jsp`, never
  `browser.close()`, and the two-attempt budget kept on disk so a fresh session cannot
  spend a third. No secret passes through the model: the password comes from the logins
  door and the mailbox token from the controller door, inside the script.
- **The skill said this tenant has no second factor. It has one.** Corrected in place in
  `references/login.md` §4 and §6: the verification countdown ran out, the account is
  enrolled on email, and every sign-in now lands on `OTPVerification` and waits for a
  mailed confirmation link. The old text would have read a login that was one click from
  succeeding as "newLogin.jsp with some other error -> refused -> stop." The entry ladder,
  the failure table and §0's viewport paragraph are updated with it.
- **Rule 4's eval allowlist grows by four named reads, and by nothing else.**
  `location.href`, because the rule "match on the query string, never on the page" had no
  permitted way to run; and the three server-rendered login flags
  (`newLogin_bBlocked`, `newLoginStep_isUserSoftLockOut`, `newLogin_bCaptcha`), which say
  whether an account is locked out, blocked or behind a CAPTCHA before a credential is
  spent finding out. All four are reads returning a primitive, each is on the list for a
  named reason, and everything else on `window` and `location` stays refused.
- **`logins` gets one narrow exception**, for the case that skill's "stop and ask the
  person" line would otherwise have blocked outright: a code or link sent to **this
  assistant's own mailbox**, for a login filed under **that same site**, with a named
  procedure in a skill for it. All three, or it still stops.
- **Authorization on the record:** Eli confirmed on 12 September 2026 that we have full
  permission and expectation to connect to these accounts as the provider. The relaxation
  above is that decision written down, not an oversight.

## 0.8.0

- **eClinicalWorks.** A new skill, `ecw`, for the hosted V12.0.3 Web EMR: the two-screen
  sign-in and its client-side encryption, the plug-in nag that bounces an already successful
  login onto a page with no error on it, the app shell behind three stacked dialogs, and the
  work queues, patient lookup and actions list with an anchor selector each. It is read only:
  no form but the sign-in, a search box and a grid's own filters, and nothing saved, signed,
  locked, booked or printed **by clicking or by evaluating** — the refusals are written about
  the effect, so `browser_console` is pinned to reading a value off a rendered element and `browser_cdp`,
  `browser_exec` and a Playwright script are refused outright on this application, because
  `browser_navigate` cannot be granted without them. Two sign-in attempts per working
  session across every cause, because this practice's login page renders no error element
  at all, so a refusal and a session bounce are indistinguishable and a third attempt locks
  a real clinician out of their own day. The Patient Hub, the progress-note form and My
  Favorite Templates are marked UNRECORDED; what is said about them is labeled "from the
  SOP, not observed"; and `references/doctrine.md` is labeled as ported from a stand-in
  replica, with its two claims that the live recording refuted corrected in place.
- **PointClickCare.** A second clinical skill, `pointclickcare`, ships in the same pack
  (merged separately as #2, and it added no entry of its own). Same shape and same refusals
  as `ecw`: read only, gated on the browser tools, and written about the effect rather than
  the gesture, so acknowledging an alert or an eINTERACT Stop and Watch is refused as the
  write it is. It carries the behaviors that were each paid for once against the live
  application: the self-submitting six-box challenge, the resident id that rotates on every
  page load, the menu wrapper that goes stale and re-serves the previous row's report, and
  the assessment that must be read from the checked inputs rather than the page text. No
  login of ours exists for it yet, so nothing in it has been run end to end and the skill
  says so.

- **On the gate.** `requires_tools: [browser_navigate, browser_console]` is a **discovery**
  gate, not an access gate: it keeps the skill out of the system-prompt index on an
  assistant without those tools (`_skill_should_show`, reached only from the index builder),
  and the skill stays loadable by name through `skills_list` and `skill_view` everywhere. It
  also excludes almost nobody in practice — nine of the ten live hermes cells have a browser
  image set. Real exclusion needs a per-cell skills block, which does not exist yet.
- **`browser`: one carve-out.** Its "write your own automation" section now says the
  Playwright route, `browser_cdp` and `browser_exec` are off for eClinicalWorks, and
  points at the `ecw` refusals instead. One paragraph, nothing else in that skill moved.

## 0.7.6

- **The pack has checks that run themselves, and every skill now says its own name in the one
  line the model reads.** A GitHub Action runs all seven scripts under `tests/` on every push
  and pull request, against the engine's own parsers at a pinned commit, so a green run means
  what the `check_pack.py` docstring says a green run should mean rather than the quieter
  fallback: schedules parsed, preset fields checked against the real cronjob schema. Two checks
  are new. `check_skill_index.py` prints the skills index exactly as the engine builds it and
  refuses a description whose visible part never says the skill's own name. The index cuts a
  description at 60 characters (`SKILL_PROMPT_DESC_LIMIT`), so anything past that cannot be
  matched on, and eight of the fourteen skills were in that state: a model looking for the mail
  watch read "Deciding whether something that just arrived in the perso..." and had nothing to
  go on. Those eight now lead with the name and read the same afterwards. `check_distribution.py`
  covers the manifest's quiet ways of going wrong: a line listed twice, a symlink, a path git
  does not track, and `scripts/` as well as `skills/`, which is where the mail watch's own
  script lives. Quoting the eight descriptions also fixed two that were not valid YAML at all,
  `documents` and `policy-keeper`, each carrying an unquoted colon and loading only because the
  engine falls back to splitting a line on its first one.

## 0.7.5

- **One emoji is a reply.** On a phone, a thanks or an OK from the person gets a reaction on
  their message, never a message back. The turn carries the message's id and the `react` command
  (agent image apply.py XII), and the assistant answers NO_REPLY so nothing else goes out. One
  line under "On a phone".

## 0.7.2

- **Nobody behind the assistant is ever named.** Not a team, not a person, not a ticket, and never
  that anyone else can read the thread. Something being fixed is being set up; something switched on
  is on; something the assistant cannot do, it cannot do from here. The intro says "built for you",
  the mail watch's failure line says "it is being looked at", and the seven lines across the skills
  that used to tell the assistant to say "the Pulse team" no longer do. Also: short by default, two
  to four lines, a report only when asked. `check_pack.py` pins both and refuses a what-to-say line
  that names the team.

## 0.7.1

- **On a phone.** A new section in assistant-standard, and one line in SOUL: everything the assistant
  sends lands in a chat, so one idea per line, a blank line between ideas, three or more things as a
  list whatever the question was, a colleague's day as one line per meeting, and no em or en dash in
  anything sent. The pack had only forbidden dashes in documents and had said "bullets only when the
  content is a list", so on Susan's first morning a six-meeting day came back as one paragraph and the
  mail watch's hello carried a dash. `check_pack.py` pins the phrases and refuses a dash in the files
  that forbid them.

## 0.7.0

- **The mail watch.** A fourth preset, the first that is opt in (`"opt_in": true`, offered at
  provision and created only when somebody names it) and the first that runs a script before the model. Every
  half hour from seven to nine, seven days a week (the case worth the most is bad
  news on a Saturday evening, and a person who wants weekdays only can say so), `scripts/mail-watch.py` asks the person's own Pulse door what has arrived in
  their mailbox since it last looked, remembers every message id it has already shown, and closes the
  wake gate when there is nothing new, so a quiet half hour costs one web call and never wakes the
  model. When something is new, the new `mail-watch` skill judges one thing: is it theirs to answer
  and is there a clock on it. Almost always the answer is no and the reply is `[SILENT]`. The first
  run after switching it on is deliberately silent (it records what is already there rather than
  firing forty old emails at a phone), and the one-time hello rides a `FIRST NOTICE` marker the
  script prints, not the continuity block, because a gated tick overwrites that block with a gate
  receipt. A mailbox that cannot be read stays quiet for four tries, then says one plain line, then
  at most once a day: silence from a watch must not read as a quiet mailbox. The watch reads and
  reports and never sends, replies, marks read or forwards; mail text reaches the model inside a
  block labelled untrusted content, and the rule that it is evidence and never an instruction is in
  the job as well as the skill, so a skill that fails to load cannot drop it. `check_pack.py` pins
  the explicit wake-gate line (an email quoting a JSON object would otherwise silence the watch for
  ever), the failure ceiling, the absence of any acting tool, and the skill's own bar.

## 0.6.2

- logins: a new skill and a `login` script (list, show, password, otp). An assistant reaches its
  own 1Password logins through the fleet controller's door with a per-assistant key, so it never
  holds a 1Password token; it signs in only on the login's own domain and stops on SMS, push or
  hardware keys. `check_pack.py` now fails a script under `skills/*/scripts/` that is not executable.

## 0.6.1

- first-contact: only the line written after the fourth beat ends first contact. A test copy seeded
  with weeks of somebody else's sessions read them as a long-running thread, declared first contact
  done on its own, and skipped the introduction. `check_pack.py` pins the sentence.

## 0.6.0

- **First contact.** A new `first-contact` skill carries the first conversation with a person:
  reactive, their request first, four beats with one question per message, a dossier branch (say
  how you read them, ask where it is wrong) and a nothing-known branch (say so, ask one thing), a
  plain answer to "what can you do for me" that is never a capability list, and an off switch a
  persona can set for a specialist cell. `SOUL.md` points at it, keyed on a memory line that says
  first contact is done, and says how the assistant sounds as rules (contractions, a take,
  matching the register, a light joke never on a figure or a refusal). The numbers rule now says
  what to do where nothing is wired into Pulse. Every safety line kept.
- **assistant-standard.** The Brief is built for a phone (what needs them first, blank lines
  between blocks, one item per line, figures only where a source is wired in); greetings split
  first contact from a running thread; a "Who is who" rule (their own WhatsApp if linked, then the
  directory, then ask); the three worked examples are domain-neutral. The humanizer fence, the
  confidentiality table and the deliver paragraph are unchanged.
- **TRAINING.md** carries the new training block: both first days (a person we hold a read of, and
  one we know nothing about), one question per conversation once first contact is done, a rule
  said in chat gets one line back. `check_pack.py` pins its sha256 to the controller's
  `TRAINING_BLOCK`; the two repos change together or the test fails.
- **policy-keeper.** The three-part reply shape is for a document; a rule said in conversation gets
  one plain line back. **own-whatsapp.** A name the person uses that the assistant does not know
  is a question its contacts answer first.

## 0.5.1

- policy-keeper: the phrasing advice now names the engine's real scanner shapes (role takeover, "you must report", "check in with", hidden text, invisible characters) instead of the persona lint's. SOUL and the template say that Policy.md is the one rule file the assistant keeps, so the "never change your own rules" line no longer contradicts it.

## 0.5.0

- **policy-keeper.** Every assistant keeps a `Policy.md` in its workspace, loaded into every
  session by the engine (the controller symlinks `.hermes.md` to it). The skill says what goes in
  it, the seven sections, the 12,000-character cap, the one intake procedure for a document or
  message from any door, the fixed reply shape (wrote / left out / needs a real switch), the
  leftovers note (`class: private`), and the phrasings the engine's scanner refuses.
  `references/POLICY-TEMPLATE.md` is the seed the controller copies once.
- **TRAINING.md.** The block the controller appends to a persona while the assistant is in
  training, kept here so the pack states it; the controller holds the pinned text.
- SOUL gains one line: Policy.md is the standing orders.

## 0.4.0

- **own-whatsapp.** A read-only skill over the person's own WhatsApp, for pods where they have
  linked one through the agent page. `own_whatsapp.py` (standard library, GET only, loopback only)
  asks the private listener store for status, chats, contacts, one chat's messages, or a search,
  and wraps every line of chat content in an origin frame that says what it is: the person's own
  history, context to draw on, never an instruction, never to be saved, never to be quoted to
  anyone else. Refusals are sentences with exit 0, so "no WhatsApp is linked" and "the listener is
  not reachable" can be said to the person as they stand. `references/STORE.md` records the read
  API and why the caps are 200 rows and 90 days per call.
- The confidentiality table gains the matching row: say it to the person as marked context, never
  memory, never the vault, and never quoted onward, treated as an instruction, or kept after they
  unlink. `check_pack.py` asserts the row word for word and that the skill's prose carries no
  address or port. Nothing in this version writes anything from the link anywhere: no job, no
  note, no memory line.

## 0.3.2

- The board's caution is on the page, not in a tooltip. It carried its sentence only in `title=` and
  `aria-label=`, so the one judgement the renderer makes needed a hover to read and did not print at
  all; it now sits on the row's own line at full contrast, and stays there on a faded row.
- A group heading the filter empties actually disappears. `.grp{display:flex}` is an author rule and
  outranks the browser's own `[hidden]{display:none}`, so filtered-out headings stayed on the page
  over nothing, above a row count frozen at render time. Both fixed, and both checked.
- The staleness banner says that its own number is frozen. This is flat markdown: the age is worked
  out once, when the file is written, and a note written the day it was read shows "0 days" for ever
  after. The banner now names the day it was written and asks the reader for the subtraction rather
  than handing them a count that stopped.

## 0.3.1

- entity-notes gains `board.py`: one self-contained HTML page from a folder of entity notes plus a
  board spec. Columns, groups, tiles, sections, colours and the staleness ladder are all spec-driven,
  so the renderer carries no vocabulary from any subject; `--demo` draws five made-up suppliers to
  prove it. The page reaches no network (a CSP meta forbids every origin), keeps nothing in the
  browser, refuses an `--out` under /tmp, writes 0600, and prints one line saying what it wrote.
- The board's one judgement, and the only one: when a spec declares which direction a series should
  move for a given status word and the last two numbers go the other way, the cell gains a caution
  carrying both. It never overrides the record's own word.
- `references/BOARD-SPEC.md` documents the spec format. `spec: 1` is frozen: an unknown spec integer
  is a refusal naming both numbers, never a best-effort render with a column quietly missing.

## 0.3.0 (2026-09-08)

- **Entity notes.** `skills/entity-notes/`: one markdown file per THING an
  assistant meets more than once - a supplier, a customer, a site, a candidate,
  a machine - so the second time starts with what happened the first time. The
  skill teaches the shape (frontmatter as a contract, a regenerated block at the
  top, dated sections appended for ever and never edited, a what-changed list
  that has a line for every fact including the ones that did not move) and the
  five rules behind it: the note is a memory and never a source, retrieval is an
  exact lookup and never a search, one file per thing verified by key on every
  write, the file goes where its class says, and nothing is invented.
- **`entity_note.py`**, the helper that owns the parts nobody should write
  twice: where the notes folder is (OBSIDIAN_VAULT_PATH, then the workspace,
  then a development path, then a refusal in words), the filename rule
  (`<Name> - <KEY>.md`, total and reversible with one rsplit), frontmatter that
  re-emits keys it has never heard of byte for byte, an atomic 0600 write, the
  section reader, an idempotent append, the generic diff, and the exact-lookup
  index. Standard library only; the frontmatter parser is hand-rolled and dumb
  on purpose, and says so.
- **`class: phi`** added to the confidentiality table and to the note types: a
  stricter `private` for a cell whose whole job is those people, bought back
  with a local-only rule (never mirrored, never to a sink, a group note, a brain
  or memory). It overrides the "never a patient or client by name" row on that
  cell alone, and nowhere else. Without this written down, the next agent to
  read the pack would have been right to refuse to write those files.
- `Entities.base`, the board over every entity note, with days since the last
  read next to every column and a view for the ones nobody has read in a month.
  Four views: everything we keep, one grouped by kind (which is where you see
  that one table really does hold every kind of thing), the stale ones, and the
  ones that need a person. The freshness column is never the last column and is
  always paired with the raw `read_on` beside it, so the view still reads
  correctly on an Obsidian too old to compute a formula.
- `tests/check_entity_notes.py`: 151 checks - every nasty filename, two things
  with the same name, a frontmatter round trip carrying a key this parser cannot
  read, a child process killed between the temp write and the rename, and no
  notes folder at all. Run it with `python3 tests/check_entity_notes.py`.

### Known gaps in 0.3.0

- 0.2.4 and 0.2.5 bumped the version with no changelog entry, so `check_pack.py`
  was already failing before this release; what those two versions changed is in
  the git log, not here.
- The frontmatter parser is checked against what we write plus a handful of
  shapes somebody else might. It is not a YAML conformance suite and does not
  claim to be: anything it does not understand is kept as the exact text it
  arrived as, which is the property the checks actually cover.
- Nothing has yet written an entity note on a real pod. The helper is exercised
  only by the checks and by whatever the first specialised layer does with it.

## 0.2.6 (2026-09-08)

The preset work of 0.2.3 finished against the engine rather than against its
schema. Nothing here changes what the three presets say; it changes what the
assistant does with a scheduled job it makes itself, and it corrects two
things the 0.2.3 notes had right in intent and wrong in detail.

- **A reminder now names where it goes.** 0.2.3 said reminders deliver to the
  phone and never to the chat door, which was the right rule and no
  instruction: the assistant was told to set `deliver` "explicitly" without
  being told what to write, and it does not know its person's chat id. It now
  says to pass the platform name — `telegram` or `whatsapp` — which the engine
  resolves against that person's own home channel, and to ask in one line when
  it cannot tell which platform is the phone. Measured cause, on
  `hermes-susan-0`: `create_job` defaults `deliver` to the creating session's
  origin, the chat door's origin is `api_server:api-<id>`, and the engine's
  home-channel fallback fires only for a job with NO origin — so five of her
  nine jobs run on time, report success, and are never delivered.
- **The timezone is the person's.** `08:00` in a preset now means 08:00 where
  that person is: the controller keeps a per-person IANA timezone and falls
  back to the org's. The presets README says which key the engine reads
  (`timezone`, top level), which file it reaches, and that a pod picks it up on
  its next restart.
- **The controller notes corrected where they were wrong.** `create_job` takes
  `schedule`, not `schedule_str`, and takes `attach_to_session` directly, so
  the second `update_job` pass the notes described is not needed. And a script
  that imports `cron.jobs` with the pod's own `HERMES_HOME=/opt/data` resolves
  its cron store to `/opt/data/cron`, which the running gateway never reads —
  a preset created that way returns an id and never fires. The profile's own
  home is the one to use.
- **`cron.allow_agent_scheduling` stays `false`, with the reason written
  down.** Re-read in the engine: the key is consumed in exactly one place and
  only decides whether an agent inside a cron RUN gets the `cronjob` toolset.
  The chat agent — the one that acts on keep, change and stop — already has it
  and is unaffected. Scoping the permission to `preset-` names is not
  expressible: Hermes has no per-job ownership, so that restriction is the
  skill's rule and not a mechanism.
- `tests/check_pack.py` also checks the skill still tells the assistant to name
  a delivery platform, since that sentence is the only thing standing between a
  chat-made reminder and silence.

## 0.2.3 (2026-09-07)

- **Humanizer skill.** `skills/humanizer/` is blader/humanizer (MIT, license
  file kept, SKILL.md verbatim from upstream main on 2026-09-07). The
  assistant-standard skill now says to run it over anything written for
  someone else: a mail draft, a note that will be shared, a document. The pass
  may change how a thing reads, never what it says, and a note to a patient, a
  resident's family, a clinician or anyone outside the company gets no pass at
  all.
- **Open commitments file.** The skill names `Open commitments.md` in the
  vault root: one table (owner, owed to, what, due, since), rewritten nightly
  from the commitment notes. The three shipped Bases stay.
- **Presets.** `skills/assistant-standard/presets/`: `morning-brief.json`
  (weekdays 08:00, ends in a 60-second voice note), `meeting-prep.json`
  (weekdays 07:30, one pre-read per meeting), `open-commitments.json`
  (nightly, silent). Each asks once on its first run whether the person wants
  it, in its own words rather than a shared line, so an answer names what it
  belongs to; the skill says how keep, change and stop are handled in chat,
  including matching an answer to the right job when two are outstanding. Each
  ships
  `deliver: __HOME_CHANNEL__`, a placeholder the controller substitutes with
  the person's own home platform and chat id; left unsubstituted the job is
  blocked at preflight rather than delivered to whichever channel happens to be
  connected. The mechanics and what the controller must allow are in
  `presets/README.md`.
- **Dossier prompt.** `references/DOSSIER.md`, the fixed prompt the staff
  button posts: context skill body under 6,000 characters plus five to eight
  USER.md entries; never figures, another customer, pay or HR matters.
- **Memory wording pinned.** Preferences and stable facts go to memory; dated
  facts, a named person's matters and anything with money go to a vault note,
  never to memory. SOUL.md's one-line rule now says the same.
- **Reminders deliver to the phone**, never back to the chat door.
- Every new file the pack ships is listed in `distribution_owned`: with an
  explicit list, only listed paths reach the pod at all.
- `tests/check_pack.py`: frontmatter, preset payloads, manifest checks, the
  three ask-once questions being distinct, and the humanizer fence still being
  present. Prefer the Hermes interpreter: without `croniter` the schedule check
  is skipped with a note rather than failing, so a plain `python3` run is green
  without having checked a single schedule.

### Known gaps in 0.2.3

Recorded so a green check run is not read as more than it is. The first three
are limits of the checks themselves and none of them blocks the release. The
last one does: it gates rolling the presets beyond a single pod.

- The ask-once distinctness check is an exact string comparison, so two
  questions that differ by a word but read the same to a person still pass.
- The dossier check greps for the literal "240" rather than doing the
  arithmetic, so widening the entry count would pass while breaking the
  2,000-character ceiling.
- The humanizer fence is guarded by phrase, not by meaning: the checks catch
  it being deleted or thinned, not a rewrite that keeps the phrases and loses
  the rule.
- No preset has been watched firing on a real phone. That smoke test gates
  rolling these beyond one pod.
