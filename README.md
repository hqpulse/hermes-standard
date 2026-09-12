# hermes-standard

The Hermes profile distribution every Pulse assistant installs: persona (`SOUL.md`) and skills.
Installed into each pod as profile `hermes-standard` by `hermes profile install`; updated with `hermes profile update`.
The default branch is the fleet version. Never commit config.yaml (org policy and per-person config come from the fleet), never commit secrets.

## Checks

Everything under `tests/` runs on every push and pull request
(`.github/workflows/pack.yml`), and by hand from the repo root:

    python3 tests/check_pack.py            # the manifest, the skills, the presets, the pinned prose
    python3 tests/check_skill_index.py     # the one index line per skill the model reads
    python3 tests/check_distribution.py    # what reaches a pod, and what silently does not
    python3 tests/check_entity_notes.py
    python3 tests/test_login.py
    python3 tests/test_mail_watch.py
    python3 tests/test_own_whatsapp.py

Run them on the Hermes interpreter (`~/.hermes/hermes-agent/venv/bin/python`), or set
`HERMES_SRC` to a checkout of the engine. Without one, `check_pack.py` quietly checks less:
no cron schedule is parsed and no preset field is compared with the real cronjob schema. CI
fetches the engine at a pinned commit and refuses to run until it imports.

Adding a skill means adding every file it ships to `distribution_owned`, one line each, and
putting the skill's own name in the first 57 characters of its description. The index cuts
there, so a name past it cannot be matched on. Both are checked.
