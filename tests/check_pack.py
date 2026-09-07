#!/usr/bin/env python3
"""Pack checks: run from the repo root with `python3 tests/check_pack.py`.

Uses the Hermes source at ~/.hermes/hermes-agent when present (frontmatter
parser, cron schedule parser, cronjob tool schema); otherwise falls back to
plain YAML/JSON checks so the script still runs anywhere.

PREFER THE HERMES INTERPRETER (~/.hermes/hermes-agent/venv/bin/python). The
fallback above triggers on IMPORT failure, but `parse_schedule` imports fine
and then needs `croniter` at CALL time; without it the schedule check is
skipped with a note rather than reporting three schedules "rejected". So a
green run on a plain interpreter proves less than a green run on the Hermes
one: it has not checked any schedule.

KNOWN GAPS, so nobody reads a green run as more than it is:
  - The ask-once distinctness check compares exact strings. Two questions that
    differ by a word but read identically to a person still pass.
  - The dossier check greps for the literal "240". It does not do the
    arithmetic, so raising the entry count past what 2,000 characters can hold
    would sail through as long as that number is still on the page.
  - The humanizer fence is checked by phrase, not by meaning. It catches a
    deletion or a thinning, not a rewrite that keeps the words and loses the
    rule.
"""
import json, os, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERMES = Path(os.environ.get("HERMES_SRC", Path.home() / ".hermes" / "hermes-agent"))
errors = []

def err(msg):
    errors.append(msg)

# --- Hermes helpers (optional) -------------------------------------------
parse_frontmatter = parse_schedule = tool_props = None
if (HERMES / "agent" / "skill_utils.py").exists():
    sys.path.insert(0, str(HERMES))
    try:
        from agent.skill_utils import parse_frontmatter
        from cron.jobs import parse_schedule
        from tools.cronjob_tools import CRONJOB_SCHEMA
        tool_props = set(CRONJOB_SCHEMA["parameters"]["properties"]) - {"action", "job_id"}
        # parse_schedule imports fine but needs croniter at CALL time. Without
        # it every cron schedule reports "rejected", which is three failures
        # that are not real. Unchecked is the honest answer, so drop just this
        # one helper and keep the rest.
        try:
            import croniter  # noqa: F401
        except ImportError:
            print("note: croniter missing; cron schedules left unchecked")
            parse_schedule = None
    except Exception as e:  # pragma: no cover
        print(f"note: Hermes helpers unavailable ({e}); using plain checks")
        parse_frontmatter = parse_schedule = tool_props = None

def plain_frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}, text
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    return fm, text[m.end():]

# --- manifest -------------------------------------------------------------
import yaml
manifest = yaml.safe_load((ROOT / "distribution.yaml").read_text())
owned = manifest.get("distribution_owned") or []
version = str(manifest.get("version"))
if not re.fullmatch(r"\d+\.\d+\.\d+", version):
    err(f"version {version!r} is not x.y.z")
for rel in owned:
    if not (ROOT / rel).is_file():
        err(f"distribution_owned lists a missing file: {rel}")
    if (ROOT / rel).is_dir():
        err(f"distribution_owned lists a directory (would wipe on upgrade): {rel}")
shipped = {str(p.relative_to(ROOT)) for p in ROOT.rglob("*")
           if p.is_file() and not any(part.startswith(".") for part in p.relative_to(ROOT).parts)
           and p.relative_to(ROOT).parts[0] in ("skills", "SOUL.md", "distribution.yaml")}
for rel in sorted(shipped - set(owned)):
    err(f"shipped file not in distribution_owned (never reaches a pod): {rel}")
changelog = (ROOT / "CHANGELOG.md").read_text() if (ROOT / "CHANGELOG.md").exists() else ""
if f"## {version}" not in changelog:
    err(f"CHANGELOG.md has no entry for {version}")

# --- skills ---------------------------------------------------------------
for skill_md in sorted(ROOT.glob("skills/**/SKILL.md")):
    text = skill_md.read_text()
    fm, body = (parse_frontmatter or plain_frontmatter)(text)
    rel = skill_md.relative_to(ROOT)
    for key in ("name", "description"):
        if not fm.get(key):
            err(f"{rel}: frontmatter missing {key}")
    if fm.get("name") and fm["name"] != skill_md.parent.name:
        err(f"{rel}: frontmatter name {fm['name']!r} != folder {skill_md.parent.name!r}")
    if not body.strip():
        err(f"{rel}: empty body")
    for ref in re.findall(r"\b(references|presets)/([\w .-]+\.(?:md|json))", text):
        target = skill_md.parent / ref[0] / ref[1]
        if not target.exists():
            err(f"{rel}: points at missing {ref[0]}/{ref[1]}")

# --- the humanizer fence --------------------------------------------------
# This paragraph carries the pack's clinical exposure: it is what stops a note
# to a resident's family being rewritten at all, and what stops an open bound
# ("over 3,000") being flattened into a false exact figure. Every other check
# here would stay green if it were deleted, so name the load-bearing phrases.
fence = (ROOT / "skills/assistant-standard/SKILL.md").read_text()
FENCE_PHRASES = [
    "changes how it reads, never what it says",
    "A word that bounds a figure is part of the figure",
    "gets no humanizer pass at all",
    "a clinician, or anyone outside the company",
]
for phrase in FENCE_PHRASES:
    if phrase not in fence:
        err(f"assistant-standard/SKILL.md: the humanizer fence has lost "
            f"{phrase!r}; that paragraph is load-bearing, do not thin it")

# --- presets --------------------------------------------------------------
ASK_TAIL = "Say keep, change, or stop."
ask_lines = {}
# The controller substitutes this before create_job. A preset that ships a real
# platform name delivers to whichever channel happens to be connected, which on
# a two-platform pod is the wrong phone and nothing alerts.
HOME_CHANNEL = "__HOME_CHANNEL__"
PLATFORM_NAMES = {"telegram", "whatsapp", "slack", "discord", "signal", "imessage",
                  "sms", "email", "matrix", "all", "origin"}
for pj in sorted(ROOT.glob("skills/assistant-standard/presets/*.json")):
    rel = pj.relative_to(ROOT)
    try:
        job = json.loads(pj.read_text())
    except json.JSONDecodeError as e:
        err(f"{rel}: bad JSON: {e}"); continue
    for key in ("name", "schedule", "prompt", "deliver"):
        if not job.get(key):
            err(f"{rel}: missing {key}")
    if not str(job.get("name", "")).startswith("preset-"):
        err(f"{rel}: name must start with preset-")
    if job.get("continuity") is not True:
        err(f"{rel}: continuity must be true (first-run detection depends on it)")
    m = re.search(r'"([^"]*' + re.escape(ASK_TAIL) + r')"', job.get("prompt", ""))
    if not m:
        err(f"{rel}: prompt lacks the ask-once question ending {ASK_TAIL!r}")
    else:
        ask_lines[str(rel)] = m.group(1)
    if "Your previous run's output" not in job.get("prompt", ""):
        err(f"{rel}: prompt does not say how to recognise the first run")
    if "does not begin with" in job.get("prompt", ""):
        err(f"{rel}: first-run test says 'does not begin with'; the continuity "
            f"block never starts the prompt, so that test is false on every run")
    deliver = str(job.get("deliver", ""))
    if deliver.split(":", 1)[0].strip().lower() in PLATFORM_NAMES:
        err(f"{rel}: deliver {deliver!r} names a platform; presets must ship "
            f"{HOME_CHANNEL} for the controller to substitute")
    elif deliver != HOME_CHANNEL:
        err(f"{rel}: deliver must be the literal {HOME_CHANNEL} placeholder, "
            f"got {deliver!r}")
    if tool_props is not None:
        extra = set(job) - tool_props
        if extra:
            err(f"{rel}: fields the cronjob tool does not accept: {sorted(extra)}")
    if parse_schedule is not None:
        try:
            parse_schedule(job["schedule"])
        except Exception as e:
            err(f"{rel}: schedule {job['schedule']!r} rejected: {e}")

# Three presets can fire in the same minute: a gateway that was down across
# all three windows collapses the backlog and fires each ONCE on the next tick
# (cron/jobs.py, get_due_jobs), and one tick dispatches them together. An
# identical question in each is then unanswerable -- neither the person nor the
# assistant can tell which job a bare "stop" belongs to.
by_line = {}
for rel, line in sorted(ask_lines.items()):
    if line in by_line:
        err(f"{rel}: ask-once question is word-for-word {by_line[line]}'s; each "
            f"preset must name its own thing so an answer is unambiguous")
    else:
        by_line[line] = rel

# --- reminders reach a phone ----------------------------------------------
#
# The one sentence between a chat-made reminder and silence. `create_job`
# defaults `deliver` to the creating session's origin, and the chat door's
# origin is `api_server`, which has no sender: the job runs, reports success,
# and nobody is told. Five of one person's nine jobs were in that state on
# 7 Sep. The engine has no config key for this, so the skill saying it is the
# whole prevention.
skill_text = (ROOT / "skills/assistant-standard/SKILL.md").read_text()
for phrase in ("must name a `deliver` target",
               "`telegram`, or `whatsapp`",
               "never pass `origin`"):
    if phrase not in skill_text:
        err(f"assistant-standard/SKILL.md: lost {phrase!r} — without it the "
            f"assistant leaves `deliver` unset and its reminders go nowhere")

# --- dossier --------------------------------------------------------------
doss = (ROOT / "skills/assistant-standard/references/DOSSIER.md").read_text()
for marker in ("=== CONTEXT SKILL ===", "=== USER.MD ===", "6,000", "240", "§"):
    if marker not in doss:
        err(f"DOSSIER.md lacks {marker!r}")

# --- result ---------------------------------------------------------------
if errors:
    print("\n".join(f"FAIL {e}" for e in errors)); sys.exit(1)
print(f"ok: pack {version}, {len(owned)} owned files, "
      f"{len(list(ROOT.glob('skills/**/SKILL.md')))} skills, "
      f"{len(list(ROOT.glob('skills/assistant-standard/presets/*.json')))} presets")
