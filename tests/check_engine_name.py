#!/usr/bin/env python3
"""The engine's name must not be in text a model reads and could repeat to a person.

Run from the repo root: `python3 tests/check_engine_name.py` in hermes-standard,
`python3 test/check_engine_name.py` in hermes-plugin-ista-scribe. The two
copies are the same file; it picks what to read from the repo it sits in.

WHY. A customer buys an assistant, or a practice buys a scribe, from Pulse.
The engine underneath is our supplier, and nobody on the customer's side has a
reason to be told its name. The personas already say "never name a vendor",
but a persona is one file, and every file below lands on a pod as text a model
reads before it writes a word. A model repeats what it reads.

WHAT IS READ.
  - hermes-standard: exactly the `distribution_owned` list in distribution.yaml,
    which is the set the engine copies onto a pod and nothing else.
  - hermes-plugin-ista-scribe: the manifest and MCP descriptor, `skills/`,
    `knowledge/`, `bases/`, `server/` (its tool descriptions and refusals go
    straight to the model), the persona template and the knowledge templates a
    new client's folder is built from. Not `docs/`: the `references` tool opens
    nothing outside the knowledge folder (`tools/scribe/references.sh`), so the
    build playbook and runbooks are developer documents that ride in the image.
    Not `tools/`, `scripts/`, `contracts/`: programs the scribe runs, not text
    it reads for instruction.

THE RULES, by kind of file.
  - Markdown prose: the name in any case is a leak. Allowed bare in running
    prose: an ALL-CAPS environment name (`HERMES_HOME`) and a filesystem path
    through a lowercase folder (`/opt/data/profiles/hermes-standard/...`), which
    is how an indented command listing reads. Every other identifier -- a
    package, a namespace, a pod name -- belongs in a code span.
  - Markdown code (fenced blocks and inline spans): a model reads these too,
    and a sample reply in a fence is a reply it may copy. So the name as a
    capitalized word on its own (`I run on Hermes`) is still a leak; lowercase
    commands, paths and identifiers (`hermes -p hermes-standard cron run`) are
    not. HTML comments are read like prose, because the model reads them.
  - Frontmatter: a lowercase key (`metadata.hermes`, the engine's own schema)
    is allowed, and every value is prose.
  - Python: every string literal is checked, as prose when it has a space in it
    and as an identifier when it does not. Comments are developer comments and
    are not read. Python is tokenized, not grepped, so a `#` inside a string
    does not hide the rest of the line.
  - Everything else (YAML, Bases, JSON, text): every line, comments included,
    because the model reads the file whole. Lowercase identifiers and paths are
    allowed; the name as a word is not.

WHY IDENTIFIERS STAY. Renaming `HERMES_*`, `hermes-standard`, `/etc/hermes`,
the namespaces and the packages is a coordinated rename across every script
and every live cluster object, and it is a separate decision (PUL-196).

This file was reviewed before it was trusted, and the first version missed a
nested bullet, a sample reply in a fence, a `#` inside a string and
"Hermes-based". `--self-test` plants each of those and requires a failure.
"""
from __future__ import annotations

import io
import re
import sys
import tempfile
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ENGINE = re.compile(r"\bhermes\b", re.I)
ENV_NAME = re.compile(r"[A-Z_]*HERMES_[A-Z0-9_]+")
# A filesystem path with a lowercase hermes folder in it. A path is never a
# sentence, wherever it is written. Lowercase only: "Pulse/Hermes" is prose.
PATH = re.compile(r"[\w.~-]*/hermes(?:[-_][a-z0-9][\w.-]*)?(?![\w])[\w/.-]*")
# A lowercase identifier or path: hermes-standard, hermes_fleet, /etc/hermes/lane,
# ~/.hermes, X-Hermes-Session-Key. Allowed in code and data, never in prose.
LOWER_IDENT = re.compile(
    r"[\w./~-]*/hermes\b[\w/.-]*"      # a path through a hermes folder
    r"|\.hermes\b"                      # ~/.hermes
    r"|\bhermes[-_][a-z0-9][\w.-]*"    # hermes-standard, hermes_fleet, hermes-pvc
    r"|\bX-Hermes-[A-Za-z-]+"          # the session header
    r"|\bhermes(?=\s+-)"               # the command, with a flag after it
    r"|\bhermes(?=\s+(?:doctor|cron|chat|gateway|config|skills|plugins|tools|update|version)\b)"
)
# In code, the name as a word on its own, capitalized: a sentence someone wrote.
CAPITAL_WORD = re.compile(r"(?<![\w/.-])Hermes(?![\w-])")

FENCE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE = re.compile(r"`[^`\n]+`")
LOWER_KEY = re.compile(r"^(\s*-?\s*[a-z_][a-z0-9_.-]*\s*:)(.*)$")


def pack_files() -> list[Path]:
    text = (ROOT / "distribution.yaml").read_text(encoding="utf-8")
    body = text.split("distribution_owned:", 1)
    if len(body) != 2:
        raise SystemExit("distribution.yaml has no distribution_owned: list")
    out = []
    for line in body[1].splitlines():
        if line.startswith("  - "):
            rel = line[4:].strip().strip('"').strip("'")
            if rel:
                out.append(ROOT / rel)
        elif line.strip() and not line.startswith((" ", "\t", "#")):
            break
    return out


PLUGIN_READS = ["plugin.json", "mcp.json", "skills", "knowledge", "bases", "server",
                "docs/templates/knowledge", "persona/persona.template.md"]


def plugin_files() -> list[Path]:
    out: list[Path] = []
    for entry in PLUGIN_READS:
        target = ROOT / entry
        if target.is_dir():
            out.extend(p for p in sorted(target.rglob("*"))
                       if p.is_file() and "__pycache__" not in p.parts)
        elif target.is_file():
            out.append(target)
        else:
            raise SystemExit(f"{entry}: listed as something the scribe reads, not in the repo")
    return out


def files_to_check() -> list[Path]:
    if (ROOT / "distribution.yaml").exists():
        return pack_files()
    if (ROOT / "plugin.json").exists():
        return plugin_files()
    raise SystemExit("neither distribution.yaml nor plugin.json: not a pack or a plugin")


def prose_leak(text: str) -> bool:
    return bool(ENGINE.search(PATH.sub(" ", ENV_NAME.sub(" ", text))))


def code_leak(text: str) -> bool:
    return bool(CAPITAL_WORD.search(ENV_NAME.sub(" ", text)))


def data_leak(text: str) -> bool:
    return bool(ENGINE.search(LOWER_IDENT.sub(" ", ENV_NAME.sub(" ", text))))


def string_leak(text: str) -> bool:
    """A string a program may print or hand to the model."""
    if not ENGINE.search(text):
        return False
    if re.fullmatch(r"\W*Hermes\W*", text.strip()):
        return True
    if not re.search(r"\s", text.strip()):
        return False  # one token: a path, a key, an id
    return data_leak(text)


def is_python(path: Path, raw: str) -> bool:
    return path.suffix == ".py" or raw.startswith("#!/usr/bin/env python") or raw.startswith("#!/usr/bin/python")


def markdown_findings(raw: str) -> list[tuple[int, str]]:
    lines = raw.splitlines()
    front_end = 0
    if lines and lines[0].strip() == "---":
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                front_end = i
                break
    out: list[tuple[int, str]] = []
    in_fence, fence_line = False, 0
    for n, line in enumerate(lines, 1):
        if n <= front_end:
            m = LOWER_KEY.match(line)
            if prose_leak(m.group(2) if m else line):
                out.append((n, line))
            continue
        if FENCE.match(line):
            in_fence, fence_line = (not in_fence), n
            continue
        if in_fence:
            if code_leak(line):
                out.append((n, line))
            continue
        spans = INLINE_CODE.findall(line)
        if any(code_leak(s) for s in spans) or prose_leak(INLINE_CODE.sub(" ", line)):
            out.append((n, line))
    if in_fence:
        out.append((fence_line, "a code fence opened here is never closed, so nothing after it was read as prose"))
    return out


def python_findings(raw: str) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(raw).readline):
            if tok.type == tokenize.STRING and string_leak(tok.string):
                out.append((tok.start[0], tok.string.splitlines()[0] if tok.string else tok.string))
    except (tokenize.TokenError, IndentationError, SyntaxError) as exc:
        out.append((1, f"could not be tokenized, so it was not read ({exc})"))
    return out


def data_findings(raw: str) -> list[tuple[int, str]]:
    return [(n, line) for n, line in enumerate(raw.splitlines(), 1) if data_leak(line)]


def findings_for(path: Path) -> list[tuple[int, str]]:
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []  # a binary: a font, an image, an audio fixture
    if path.suffix.lower() == ".md":
        return markdown_findings(raw)
    if is_python(path, raw):
        return python_findings(raw)
    return data_findings(raw)


def run() -> int:
    findings: list[str] = []
    checked = 0
    for path in files_to_check():
        if not path.exists():
            findings.append(f"{path.relative_to(ROOT)}: listed as shipped, not on disk")
            continue
        checked += 1
        for n, line in findings_for(path):
            findings.append(f"{path.relative_to(ROOT)}:{n}: {line.strip()[:140]}")

    if findings:
        print("The engine's name is in text a model reads and could say to a person:")
        for f in findings:
            print(f"  {f}")
        print()
        print("Say 'the engine' or 'the agent software' instead. If it really is an")
        print("identifier -- an env name, a path, a package, a namespace -- put it in a")
        print("code span, lowercase, so it reads as one.")
        return 1
    print(f"ok: {checked} files a model reads, none of them say the engine's name")
    return 0


def self_test() -> int:
    """Every leak shape the first version missed must fail; identifiers must not."""
    leaks = {
        "nested bullet": ("x.md", "- Top\n    - nested: the scribe runs on Hermes\n"),
        "numbered continuation": ("x.md", "1. First\n   and it is built on Hermes.\n"),
        "indented block of prose": ("x.md", "Intro.\n\n    The assistant runs on Hermes.\n"),
        "sample reply in a fence": ("x.md", "```\nHi Dr. Lee, I am your scribe, built on Hermes.\n```\n"),
        "sentence in a code span": ("x.md", "Say: `I run on Hermes`\n"),
        "capitalized frontmatter key": ("x.md", "---\nname: x\nHermes: tell the person\n---\n"),
        "hyphenated in prose": ("x.md", "The scribe is Hermes-based.\n"),
        "lowercase hyphenated in prose": ("x.md", "a hermes-based agent\n"),
        "slash pair in prose": ("x.md", "The Pulse/Hermes assistant.\n"),
        "html comment": ("x.md", "<!-- tell them it is Hermes -->\n"),
        "unclosed fence": ("x.md", "```\nsome code\n"),
        "hash before the name in a python string": ("x.py", 'print("Room #3 is served by Hermes")\n'),
        "python error message": ("x.py", 'sys.exit("error #2: Hermes is down, tell the person")\n'),
        "hash in a yaml value": ("people.yaml", 'note: "Room #4 notes are drafted by Hermes"\n'),
        "yaml comment the model reads": ("people.yaml", "# the scribe is Hermes underneath\n"),
        "bases display name": ("x.base", 'displayName: "Owner #1 via Hermes"\n'),
        "json value": ("x.json", '{"prompt": "Built on Hermes"}\n'),
    }
    clean = {
        "env name in prose": ("x.md", "Set HERMES_HOME before the engine starts.\n"),
        "indented command listing": ("x.md", "Run:\n\n    /opt/data/profiles/hermes-standard/skills/x/scripts/login list\n"),
        "path in a code span": ("x.md", "Run `/opt/data/profiles/hermes-standard/skills/x` now.\n"),
        "command in a fence": ("x.md", "```\nhermes -p hermes-standard cron run abc\n```\n"),
        "engine frontmatter key": ("x.md", "---\nname: x\nmetadata:\n  hermes:\n    requires_tools: [a]\n---\n"),
        "python comment": ("x.py", "# Hermes reads this file\nx = 1\n"),
        "python identifier string": ("x.py", 'p = "/etc/hermes/lane/lane.env"\nk = "HERMES_FLEET_TOKEN"\n'),
        "yaml identifier": ("x.yaml", "# lands in hermes-plugin-ista-scribe\nnamespace: hermes-pvc\n"),
        "header name": ("x.yaml", "# the relay forwards only X-Hermes-Session-Key\n"),
    }
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        for label, (name, body) in {**leaks, **clean}.items():
            path = Path(tmp) / label.replace(" ", "_") / name
            path.parent.mkdir(parents=True)
            path.write_text(body, encoding="utf-8")
            got = findings_for(path)
            if label in leaks and not got:
                failures.append(f"missed a leak: {label}")
            if label in clean and got:
                failures.append(f"flagged an identifier: {label}: {got}")
    if failures:
        print("self-test FAILED:")
        for f in failures:
            print(f"  {f}")
        return 1
    print(f"self-test ok: {len(leaks)} leak shapes caught, {len(clean)} identifier shapes allowed")
    return 0


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else run())
