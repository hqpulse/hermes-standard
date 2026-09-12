#!/usr/bin/env python3
"""distribution.yaml: what reaches a pod, and what silently does not.

Run from the repo root with `python3 tests/check_distribution.py`.

WHY THIS EXISTS

`distribution_owned` is not a hint. Two rules hang off it, both of them
one-way:

  1. Once the list is explicit, ONLY the paths on it are copied at all
     (hermes_cli/profile_distribution.py, _copy_dist_payload). A file the pack
     ships and forgets to list never reaches a pod, and nothing says so. The
     skill just is not there.

  2. A listed path that is a DIRECTORY is wiped and rewritten on every
     install, whole subtree included. That is how an assistant-written skill
     was destroyed on 3 Sep 2026: it had been created inside
     skills/pulse-analyst/, and the pack owned the folder. The pack owns the
     FILE now. The manifest's own comment block tells the story.

So the manifest is a load-bearing list that a person edits by hand, and every
way of getting it wrong is quiet. This checks the ways.

check_pack.py already refuses a missing path, a directory, and a shipped skill
file that is not listed. It is the script people run, so those stay there. This
adds the ones it does not have: a duplicate line, a path that escapes the repo,
a symlink, a listed file that git does not track (present on the author's disk,
absent from every clone), and coverage of scripts/ as well as skills/, which is
where the mail watch lives.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

# Everything under these tops is shipped to a pod and must therefore be owned.
# skills/ and SOUL.md are the profile; scripts/ holds the pre-run scripts a
# cron preset names (check_pack.py covers the first two, not the third).
SHIPPED_TOPS = ("skills", "scripts", "SOUL.md", "distribution.yaml")

errors = []
notes = []


def err(msg):
    errors.append(msg)


def tracked_files():
    """Everything git has. Empty set when git cannot answer, and we say so."""
    try:
        out = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "-z"],
            capture_output=True, check=True, timeout=30,
        ).stdout.decode()
    except Exception as e:
        notes.append(f"note: git could not list tracked files ({e}); "
                     f"the tracked-file check is skipped")
        return None
    return {p for p in out.split("\0") if p}


manifest = yaml.safe_load((ROOT / "distribution.yaml").read_text())
owned = manifest.get("distribution_owned") or []
version = str(manifest.get("version"))

if not re.fullmatch(r"\d+\.\d+\.\d+", version):
    err(f"version {version!r} is not x.y.z")

seen = {}
for i, rel in enumerate(owned, 1):
    if not isinstance(rel, str) or not rel.strip():
        err(f"distribution_owned entry {i} is not a path: {rel!r}")
        continue
    if rel in seen:
        err(f"distribution_owned lists {rel!r} twice (lines {seen[rel]} and {i})")
        continue
    seen[rel] = i
    if rel.startswith("/") or ".." in Path(rel).parts or rel.startswith("./"):
        err(f"distribution_owned entry must be a plain path inside the repo: {rel!r}")
        continue
    p = ROOT / rel
    if p.is_symlink():
        err(f"distribution_owned lists a symlink: {rel} -> {os.readlink(p)}; "
            f"ship the file itself, a link resolves differently on a pod")
        continue
    if p.is_dir():
        err(f"distribution_owned lists a folder: {rel}. A folder on this list is "
            f"wiped and rewritten on every install, taking anything the assistant "
            f"wrote inside it. List the files, one line each.")
        continue
    if not p.is_file():
        err(f"distribution_owned lists a path that is not there: {rel}")

git_files = tracked_files()
if git_files is not None:
    for rel in owned:
        if isinstance(rel, str) and (ROOT / rel).is_file() and rel not in git_files:
            err(f"distribution_owned lists {rel}, which git does not track. It is on "
                f"this disk and in no clone, so the pod gets nothing. git add it.")

# The other direction: shipped and not listed, so it never leaves the repo.
shipped = set()
for p in ROOT.rglob("*"):
    if not p.is_file():
        continue
    parts = p.relative_to(ROOT).parts
    if any(part.startswith(".") or part == "__pycache__" for part in parts):
        continue
    if parts[0] in SHIPPED_TOPS:
        shipped.add(str(p.relative_to(ROOT)))
for rel in sorted(shipped - set(owned)):
    err(f"{rel} is shipped but not in distribution_owned, so it never reaches a pod")

for note in notes:
    print(note)
if errors:
    print("\n".join(f"FAIL {e}" for e in errors))
    sys.exit(1)
print(f"ok: distribution {version}, {len(owned)} owned files, "
      f"{len(shipped)} shipped, no folder owned wholesale")
