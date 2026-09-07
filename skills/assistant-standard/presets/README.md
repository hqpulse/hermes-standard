# Presets: the jobs every new assistant starts with

Three cron job specs, one JSON file each, in the shape of a Hermes `create_job`
payload. The controller applies them at provision, and again from a Presets tab
for assistants that already exist. The pack does not ship a `cron/jobs.json`:
that file is per person and a pack-owned copy would overwrite every person's
own jobs on update (the 3 Sep lesson).

| File | Name | Schedule (person's timezone) | Delivers | Ends with |
|---|---|---|---|---|
| `morning-brief.json` | `preset-morning-brief` | weekdays 08:00 | `__HOME_CHANNEL__` | the Brief plus a 60-second voice note (`text_to_speech`) |
| `meeting-prep.json` | `preset-meeting-prep` | weekdays 07:30 | `__HOME_CHANNEL__` | one pre-read per meeting; `[SILENT]` on a day with none |
| `open-commitments.json` | `preset-open-commitments` | nightly 23:00 | `__HOME_CHANNEL__` | `[SILENT]`; rewrites `Open commitments.md` in the vault |

Everything below was read from Hermes v0.21.0 (2026.8.31), the engine the fleet runs.

## What the payload fields are

These are the fields the `cronjob` tool accepts on `create`
(`tools/cronjob_tools.py`, `CRONJOB_SCHEMA`). The same names are the keyword
arguments of `cron.jobs.create_job`, with one exception noted.

- `name`: the job's friendly name. The presets use a `preset-` prefix; the skill
  lets the assistant edit, pause or remove only jobs with that prefix.
- `schedule`: cron syntax. Resolved in the profile's configured timezone
  (`cron/jobs.py`, "anchor to the configured Hermes timezone"), which the fleet
  render writes into each person's config. Today that value is per org
  (`FLEET_TIMEZONE`); decision 17 moves it to the person record.
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
- `skills`: skills loaded before the prompt. All three load `assistant-standard`
  so the Brief, pre-read and commitment formats are in the job's context.
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
   never fall back to a default. Either
   `hermes -p hermes-standard cron create "<schedule>" "<prompt>" --name <name> --deliver <platform>:<chat_id> --skill assistant-standard --continuity`
   or `cron.jobs.create_job(..., context_from=["self"])` from Python, then
   `update_job` for `attach_to_session` (the CLI create has no flag for it; the
   tool does).
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
   `disabled_toolsets`. Hermes has no per-job ownership, so the restriction to
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
