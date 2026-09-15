# Presets: the jobs every new assistant starts with

Seven cron job specs, one JSON file each, in the shape of the engine's `create_job`
payload. The controller applies them at provision, and again from a Presets tab
for assistants that already exist. The pack does not ship a `cron/jobs.json`:
that file is per person and a pack-owned copy would overwrite every person's
own jobs on update (the 3 Sep lesson).

| File | Name | Schedule (person's timezone) | Delivers | Ends with | On at provision |
|---|---|---|---|---|---|
| `morning-brief.json` | `preset-morning-brief` | weekdays 08:00, held by the quiet calendar | `__HOME_CHANNEL__` | the Brief plus a 60-second voice note (`text_to_speech`) | yes |
| `meeting-prep.json` | `preset-meeting-prep` | weekdays 07:30, held by the quiet calendar | `__HOME_CHANNEL__` | one pre-read per meeting; `[SILENT]` on a day with none | yes |
| `open-commitments.json` | `preset-open-commitments` | nightly 23:00 | `__HOME_CHANNEL__` | `[SILENT]`; rewrites `Open commitments.md` in the vault | yes |
| `mail-watch.json` | `preset-mail-watch` | every 30 min, 07:00-21:00, every day; the script stays shut through a quiet window and until 09:00 the next morning | `__HOME_CHANNEL__` | `[SILENT]` unless something in their mailbox needs them | opt in |
| `delegation-scan.json` | `preset-delegation-scan` | Mondays 09:00, held by the quiet calendar | `__HOME_CHANNEL__` | three named things the assistant could take off their plate, one question; `[SILENT]` when there is nothing worth proposing | opt in |
| `commitment-watch.json` | `preset-commitment-watch` | 09:00, 13:00 and 17:00 every day; the monitor source holds its last answer through a quiet window | `__HOME_CHANNEL__` | no model run at all when no promise moved; `[SILENT]` unless a change clears the interruption gate | opt in |
| `memory-audit.json` | `preset-memory-audit` | nightly 02:30 | `__HOME_CHANNEL__` | `[SILENT]`; holds `MEMORY.md` and `USER.md` to the admission test | opt in |

Everything below was read from the engine the fleet runs, at `v0.21.0` (2026.8.31).

## Two are different: they are opt in, and the mail watch runs a script first

`mail-watch.json` and `delegation-scan.json` carry `"opt_in": true`, which the other three do not. A
provision run OFFERS it instead of creating it, and it is created only when
somebody names it (`POST /v1/assistants/<person>/presets` with
`{"only": ["preset-mail-watch"]}`). The other three are what the assistant IS,
and a person who gets an assistant gets them. The delegation scan is opt in for
the same reason: it reads a fortnight of somebody's mail and calendar on its
first run, and the research behind it (people leave an assistant because they
never knew what to hand it) does not license reading their mail unasked. It is
the gate script's continuity shape, like the brief. A job that reads somebody's
mailbox every half hour is a decision about that person, and a provision run
must not make it on their behalf. The field is read by the controller and
stripped before `create_job`, which has no such argument.

## One is on everywhere, and it never asks

Sruly's decision, 15 Sep 2026 (PUL-303): `open-commitments.json` is on for
every assistant, the ones that exist today and the ones built tomorrow, and it
does not ask. It replies `[SILENT]` on every run including the first, so the
person is sent nothing, ever, unprompted, and there is nothing for them to
consent to. An assistant without it is an assistant whose open commitments list
goes stale in silence, which is what PUL-185 found on Susan's cell.

The controller carries that as `presets.ALWAYS_ON`: the job goes on when an
assistant is built, when its pod is moved onto a newer pack, and when a phone
is wired up after the fact, so there is no rollout step. With no home channel
it is created with `deliver: local` and kept on the box, because a silent job
has nothing to deliver. Stopping stays the person's: the controller writes down
every preset it installs (`pulse.hqpulse.ai/presets-installed` on the person's
StatefulSet), and a name it installed with no job on the pod is a job somebody
removed, which it never puts back.

The morning brief and the meeting pre-read are NOT in this class. They send the
person something every time they run, so asking once is still right for those
two.


`mail-watch.json` is the only preset that carries a `script`, and the field
changes the shape of the job. `cron/scheduler.py` runs `scripts/mail-watch.py`
BEFORE building the prompt; a last stdout line of `{"wakeAgent": false}` skips
the model entirely (no run, no delivery, no cost), and any other output is
injected as a `## Script Output` block. So the deterministic half of the watch
(what is new, what has already been shown, is the door even answering) is code,
and only the judgement reaches a model.

Two consequences worth knowing before copying the pattern:

- **A scripted preset must not set `continuity`.** A gated tick still writes an
  output document ("Script gate returned `wakeAgent=false`"), and the continuity
  block injects the NEWEST one. On a job that is silent most ticks, "is there a
  previous-run block" says yes from the first gated half hour, so the one-time
  hello would never be said and the block itself would be a gate receipt rather
  than anything the assistant wrote. The script owns both jobs instead: it
  remembers every message id it has shown, and prints its own `FIRST NOTICE`
  marker until it has woken the model once.
- **The controller checks the script exists before it creates the job.** A
  missing script is not a loud failure: `_run_job_script` returns "Script not
  found", the engine treats it as a data-collection failure, and the assistant
  reports a broken script to the person every half hour. `presets.CREATE_SCRIPT`
  stats `scripts/<name>` on the pod and refuses the create instead.

## The commitment watch is a monitor, not a script

`commitment-watch.json` carries `monitor_script`, which is a different engine
mode from `script`. On every tick `cron/monitor.py` runs
`scripts/commitments_state.py` FIRST and hashes its exact stdout against the
hash from the last tick that woke the model. Same hash: a silent `no_change`
run, no model, no delivery. Different hash: a capped unified diff plus the new
output is put in front of the prompt and the model runs. The first tick ever is
a "Monitor Baseline" and the prompt answers it with `[SILENT]`. A source that
exits non-zero is an ERROR, never a change, and the stored hash is left alone.

What that shape costs, and how the watch pays it:

- **No clock in the output.** The engine compares bytes, so the script prints
  no timestamp and no day count: days-to-due is a bucket (overdue, due today,
  due tomorrow, due within a week, due later, no due date) that moves only when
  a promise crosses a line.
- **No `script` beside it.** The engine stores the new hash before a pre-run
  gate could close, so `jewish_time.py` cannot sit in front of this job: a
  change seen on Shabbat would be spent on a tick nobody may hear. The monitor
  source reads the quiet calendar and the stated quiet hours itself and, while
  held, prints its last answer from outside the window byte for byte
  (`<HERMES_HOME>/commitment-watch/last-output.txt`), so everything that moved
  arrives as one diff when the hold lifts. `check_pack.py` refuses a monitor
  preset that also carries a script. That file is written by ANY run outside
  a hold, so do not run the script by hand on a pod just before a quiet
  window: a hand run that saw a different state than the engine's last tick
  would make the held output differ from the stored hash and wake the model
  inside the window.
- **No continuity, and no writer.** The diff is the context. And the engine
  sets `skip_background_review` on every cron turn, so no memory review runs
  after this job: whatever it learns it writes itself, in its own turn.
- **The controller installs it.** `cron.allow_agent_scheduling` is false, so
  the assistant cannot create it; the controller must pass `monitor_script`
  through to `create_job` and check the script exists first, as it already
  does for `script`. A controller that drops the field creates an ordinary job
  that wakes the model three times a day.

It is opt in for the same reason as the mail watch: it is a job whose purpose
is to speak first.

## The memory audit is a cron turn on purpose, not the review fork

`memory-audit.json` does the same job as the engine's memory writer from the
other end: the writer decides what goes in after a conversation, the audit
re-reads what is already there against the admission test in the
assistant-standard skill's Memory section, and consolidates.

It has to be an ordinary scheduled turn. The writer runs as an unattended
review fork, and an unattended fork is add-only: every `replace` and `remove`
it makes is staged for a person to approve (`tools/memory_tool.py`,
`_background_delete_gate`), so a fork could never retire a line. A cron turn is
not a review: while `memory.write_approval` is off, as the fleet rulebook
keeps it, its writes go through as in any foreground turn, so the audit can
replace and remove. With that switch on, every write from a cron turn is staged
for approval instead, so the prompt stops at the first staged answer rather
than leave an add waiting beside a remove that could be approved without it. The other half of the same fact is that the engine
sets `skip_background_review` on every cron turn, so no writer runs after the
audit and nothing it does is second-guessed.

Five things the prompt holds to, and why:

- **It reads Policy.md itself, and writes it as plain statements of fact.** A
  cron turn has no working folder, so the engine loads no context file and
  Policy.md is not in its prompt: without reading it the audit would call a
  line a second copy of something it never saw. And one Policy.md line in a
  shape the engine's scanner refuses blanks the whole file for the next
  session, first-contact lines included. The job does NOT load policy-keeper
  for those phrasing rules: that skill quotes the attack phrasings it warns
  about, and the engine scans a cron job's prompt together with its loaded
  skills (`cron/scheduler_prompt.py`, `_scan_assembled_cron_prompt`), so the
  run would be blocked every night and the failure notice sent to the
  person's phone. `check_pack.py` runs that scanner over every preset.
- **Only the memory tool touches the two files.** The store refuses a write
  when the file on disk no longer round-trips through its parser, so one
  `write_file` or `patch` on `MEMORY.md` would lock the assistant out of its
  own memory until somebody cleans the file by hand.
- **The add before the remove.** Moving a preference from `MEMORY.md` to
  `USER.md` is two calls. Adding first means a refused add (a full `USER.md`)
  leaves the line where it was instead of losing it.
- **02:30, after the nightly commitments pass at 23:00** and before the
  morning session reset, so a line the audit moved into a note has a
  commitment note to sit beside, and the next session starts from the cleaned
  files (memory is frozen into the system prompt when a session starts).
- **Opt in.** It changes memory with nobody watching, so a provision run
  offers it and never creates it. It is not the person's to ask for either:
  the people who run Pulse turn it on per assistant, starting with one pod and
  a week of reading what it changed before any other.

It is silent like the nightly commitments pass: `[SILENT]` on every run, no
ask-once question, and nothing about memory, files or schedules ever reaches
the person.

## Quiet hours for everyone

The same gate reads a second file, `<HERMES_HOME>/quiet/windows.json`: the
evenings, weekends, days off and personal hours a person states out loud. The
quiet-windows skill writes it (`quiet-windows add weekly mon-fri 19:00 08:00
evenings`, `quiet-windows add dates 2026-11-26 2026-11-27 days off`) the moment
the person says the rule, and `jewish_time.py` consults it before the calendar,
so a preset with the gate is held shut inside either. The mail watch reads it
too. No file means no quiet hours beyond the calendar; nothing is inferred.

## The quiet calendar, and why two presets with continuity run a script

`morning-brief.json` and `meeting-prep.json` carry `"script": "jewish_time.py"`.
It is a gate, not a data feed. For a person who keeps Shabbat and yom tov it
reads their calendar (`<HERMES_HOME>/jewish-time/calendar.json`, built once
per person, never owned by the pack) and prints `{"wakeAgent": false}` inside a
quiet window and on erev Pesach and Tisha B'Av, so the job does not run at all.
Outside one it prints a `QUIET CALENDAR` block (a fast day, chol hamoed, the
first morning back and how far back to look) and an open gate. For everyone
else it prints one neutral line; it always prints something, because a script
with empty output skips the model and the brief would never come.

That looks like it breaks the rule above, and it does not. The rule exists
because a gate receipt used to become the continuity block. The engine the
fleet runs (v2026.9.11) skips receipts when it builds that block
(`cron/scheduler_prompt.py`, `_inject_context_from`), and this gate closes a
handful of ticks a month, so the ask-once question and the "do not repeat
yesterday" block both still see the last real brief. `check_pack.py` allows
continuity on a scripted preset for this script only. On the v2026.8.31 engine
a gated day would make the next day's block a receipt, which costs one day's
continuity and nothing else.

**Nothing already on a pod gets the gate by upgrading the pack.** The controller
never rewrites a preset job that already exists (`presets.plan` keeps it by
name), so an existing `preset-morning-brief` or `preset-meeting-prep` keeps no
script and its old prompt, and so does every job the person made for
themselves. To hold one of those for a person with a calendar, back up
`cron/jobs.json`, then set the job's `script` to `jewish_time.py` and add the
QUIET CALENDAR sentence to its prompt, on a pod already on this pack (before
it, the engine reports "Script not found" on every tick). A job that already
has a script, like the mail watch, cannot take a second one; the mail watch
checks the calendar itself.

## What the payload fields are

These are the fields the `cronjob` tool accepts on `create`
(`tools/cronjob_tools.py`, `CRONJOB_SCHEMA`). The same names are the keyword
arguments of `cron.jobs.create_job`, with one exception noted.

- `name`: the job's friendly name. The presets use a `preset-` prefix; the skill
  lets the assistant edit, pause or remove only jobs with that prefix.
- `schedule`: cron syntax. Resolved in the profile's configured timezone
  (`cron/jobs.py` anchors a schedule to the configured timezone, not the server's local one), which the fleet render writes into each person's config as the
  top-level `timezone:` key. `hermes_time.py` resolves that key, and
  `gateway/run.py` bridges it to `HERMES_TIMEZONE` at start. It is now PER
  PERSON: the value lives on the person's StatefulSet
  (`pulse.hqpulse.ai/timezone`) and falls back to the org's `FLEET_TIMEZONE`
  when they have none of their own, so 08:00 is 08:00 where the person is. A
  timezone the machine's tzdata cannot load is refused when it is set, because
  the engine's fallback for an unloadable name is the box's own clock — an 8am
  brief would fire at 8am UTC and look like nothing was wrong. A pod reads its
  clock at boot, so a change takes effect on the next restart.
- `prompt`: self-contained. The job runs in a fresh session with no chat context.
- `deliver`: where the final reply is posted. The presets carry
  `__HOME_CHANNEL__`, a PLACEHOLDER. The controller must substitute the
  person's home platform and chat id (`platforms.<p>.home_channel.chat_id` in
  their rendered config) before creating the job. An explicit `platform:chat_id`
  target is the only form that `attach_to_session` can attach: a bare platform
  name (`telegram`) resolves to the same chat but carries no provenance tag, so
  `_target_mirror_eligible` refuses it and the brief is never continuable
  (cron/scheduler.py, _target_mirror_eligible: "bare-platform home targets ...
  are never eligible"). Do not leave it unset: a job created through the API
  door defaults to `origin`, and the API server cannot receive a delivery (the
  7 Sep reminder on Susan's pod failed with exactly that).

  The failure in full, because it is the reason this field is a placeholder
  rather than a default. `create_job` defaults `deliver` to the creating
  session's origin ("Default delivery to origin if available, otherwise
  local"), and the chat door stamps its origin as
  `{"platform": "api_server", "chat_id": "api-<id>"}`
  (`gateway/platforms/api_server.py`, `_cron_origin_from_request`). At fire
  time `_resolve_single_delivery_target` hands that straight back as the
  target, and the send fails with "API server uses HTTP request/response, not
  send()". The engine DOES have a home-channel fallback, but it fires only when
  a job has NO origin at all — a chat-door job has one, it is just
  undeliverable — so these fail on every run and keep failing. Measured on
  `hermes-susan-0`: five of her nine jobs are in that state. Both halves of the
  rule matter to that count. EIGHT of the nine were made through the chat door
  and so carry `origin: api_server`; only five of those also ask to deliver to
  that origin, and those five are the broken ones. The other three say
  `deliver: local`, which opts out of delivery on purpose and is not a fault.
  Reading the origin alone gives eight and condemns three healthy jobs. There
  is no config
  key for this; the default is written in `create_job`, not read from config.
  The fix is two halves: the skill tells the assistant to always name a
  delivery platform, and the controller has a repair pass for the ones already
  made.

  Note the two halves deliberately use DIFFERENT forms, and neither is a
  mistake to be tidied into the other. A preset gets the explicit
  `platform:chat_id` written by the controller, because only that form can
  attach a session and the person must be able to reply to their brief. A
  reminder the assistant creates in chat gets the bare platform name, because
  the assistant does not know a chat id and the engine resolves a bare name
  against the same `home_channel` block. A reminder that cannot be replied to
  is fine; a reminder that never arrives is not.
- `skills`: skills loaded before the prompt. All three load `assistant-standard`
  so the Brief, pre-read and commitment formats are in the job's context.
- The nightly job runs seven days a week (`0 23 * * *`) while both briefs are
  weekdays only. That is deliberate, not an oversight: commitments are made and
  met at weekends too, and the pass is silent, so it costs the person nothing.
- `continuity`: `true` means each run gets its own previous output injected at
  the top of the prompt under the heading "Your previous run's output". On the
  tool and CLI this is a flag; `create_job` itself has no such argument, it is
  stored as `context_from: ["self"]`. The CLI flag is `--continuity`.
- `attach_to_session`: `true` makes the delivered message continuable, so the
  person can reply to the brief and the assistant has it in context. It only
  works with an explicit `platform:chat_id` target (see `deliver` above). Set
  `true` on the two briefs and pinned `false` on the silent nightly job. The
  fleet's global `cron.mirror_delivery: true` never activates an explicit
  target on its own (`_target_mirror_eligible`), so the `false` is a record of
  intent, not a fix; it is what protects the nightly job if the target is ever
  resolved from the origin instead.
- `model`, `provider`, `reasoning_effort`: `create_job` kwargs, NOT `cronjob`
  tool fields (model/provider are deliberately withheld from the agent so it
  cannot point unattended spend at a different model). The presets leave them
  unset so the job follows the profile's model. Note `cron.model_drift_guard`
  (default on): an unpinned job fails closed if the profile's model changes
  after creation; re-applying the preset recreates the snapshot.
- Also available, unused here: `repeat`, `script`, `monitor`, `no_agent`,
  `enabled_toolsets` (a native-toolset allowlist; leave unset so the Pulse MCP
  tools stay), `workdir`.

## How the job knows it is its first run

Continuity. On the first run there is no previous output, so the prompt runs as
written. On every later run the scheduler prepends the block "Your previous
run's output" (`cron/scheduler.py`, `context_from` handling; output is saved
before the `[SILENT]` check, so a silent run still counts). Each prompt says:
no block, first run, add the question; block present, never ask again, even if
the person never answered. That is the whole mechanism; no memory entry and no
job field is involved.

The saved output embeds the run's whole assembled prompt, so each run's
output nests the previous one. From about the third run the 8,000-character
injection cap truncates the tail, which is the previous brief; what survives
is the prompt echo. The first-run check still works (the block is present),
but do not rely on continuity for dedupe here.

The question is asked by the job; the answer is handled in chat. The
assistant-standard skill (section "Presets") tells the assistant what to do with
keep, change and stop, and to update the job so the first-run paragraph is gone
from its prompt. Both halves together mean the question is asked once.

## What the controller must do and allow

1. **Apply at provision, by name.** For each preset: if a job named
   `preset-<x>` exists in the person's profile, skip; otherwise substitute
   `__HOME_CHANNEL__` with the person's home platform and create it. A pod
   with more than one connected platform is the dangerous case: Telegram
   being connected does not make it the home channel, and preflight cannot
   tell the difference, so read the home channel from the person record and
   never fall back to a default. Susan has a home channel on BOTH Telegram and
   WhatsApp, and the one job of hers that delivers correctly delivers to
   WhatsApp — a controller that had quietly preferred Telegram would have put
   her morning figures in the chat she does not read. The controller therefore
   refuses rather than picking, until somebody says which is home
   (`pulse.hqpulse.ai/home-platform` on the person's StatefulSet).

   Two things about doing this from Python, both measured on the running image
   rather than read off a signature:

   - **Point `HERMES_HOME` at the PROFILE, not at the pod's own home.** The pod
     sets `HERMES_HOME=/opt/data`, and a script that imports `cron.jobs` with
     that value resolves its cron store to `/opt/data/cron` — while the running
     gateway's jobs are in `/opt/data/profiles/hermes-standard/cron/jobs.json`.
     A job created the obvious way is written where nothing reads it:
     `create_job` returns an id, the apply reports success, and the brief never
     fires. Use `HERMES_HOME=/opt/data/profiles/hermes-standard`.
   - **`create_job` takes `schedule`, not `schedule_str`, and it takes
     `attach_to_session` directly.** No second `update_job` pass is needed;
     only the CLI lacks the flag. `continuity` is not an argument at all — it
     is stored as `context_from=["self"]`.
2. **Only when the home channel exists.** `cron.preflight` (on by default)
   records a job whose delivery platform is not configured as
   `blocked_config` and never runs it. A person with no Telegram or WhatsApp
   yet should get the presets when the channel is wired, not before.
   Preflight checks CREDENTIALS, not the home channel: a pod with a bot token
   but no `platforms.<p>.home_channel` passes preflight, runs, and drops the
   delivery into `last_delivery_error`. The controller must refuse to create a
   preset whose `deliver` still contains the literal `__HOME_CHANNEL__`.
3. **Let the assistant manage preset jobs from chat.** The interactive agent
   already has the `cronjob` toolset: it is not in the rulebook's
   `disabled_toolsets`. The engine has no per-job ownership, so the restriction to
   `preset-` names is the skill's rule, not a mechanism. If the rulebook ever
   disables `cronjob`, the ask-once answer stops working. Verified 2026-09-07
   against the live org rulebook ConfigMaps: `hermes-venza` (14 disabled toolsets),
   `hermes-ista` (14) and `hermes-pvc` (16) all leave `cronjob` and `file`
   enabled.
4. **`cron.allow_agent_scheduling` can stay `false`.** That key only decides
   whether the agent *inside a cron run* gets the `cronjob` toolset
   (`cron/scheduler.py`, `_resolve_cron_disabled_toolsets`). The presets never
   manage themselves; the chat agent edits the job after the person answers.
   Turn it on only if the lead wants the job to strip its own first-run
   paragraph without waiting for an answer.
5. **`approvals.cron_mode: deny` stays.** The presets run Pulse tools, the
   vault file tools and `text_to_speech`; none is a dangerous command.
6. **`text_to_speech` needs the TTS key on the pod.** The rulebook pins
   `tts.provider: openai`; the org secret carries the key. Audio the agent
   attaches is uploaded on delivery as a voice bubble on Telegram.
7. **Watch it once on a real phone** before calling any preset done. To fire a
   job now: `hermes -p hermes-standard cron run <job_id>` (runs in the
   background; the reply arrives at the delivery target).
