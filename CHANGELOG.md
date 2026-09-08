# Changelog

Earlier versions are in the git history (`git log --oneline v0.1.1..v0.2.2`).

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
