#!/usr/bin/env python3
"""The release text a tag produces (.github/scripts/release_note.py), proven
on the script's own sample and on the real CHANGELOG.md: every version
heading parses, the newest section is not empty, and its Telegram message
reads like the rules say (no backticks, no paths, no em dashes, at most eight
bullets). Run: python tests/test_release_note.py"""
import importlib.util
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / ".github" / "scripts" / "release_note.py"


def load():
    spec = importlib.util.spec_from_file_location("release_note", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    rn = load()
    rc = rn.self_test()
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    versions = list(rn.sections(changelog))
    headings = re.findall(r"^## +(\S+)", changelog, re.M)
    if len(versions) != len(headings):
        print(f"FAIL  {len(headings)} '## ' headings but {len(versions)} parsed as versions: a heading is not X.Y.Z")
        rc = 1
    if not versions:
        print("FAIL  no version in CHANGELOG.md"); return 1
    newest = versions[0]
    try:
        body = rn.section(changelog, "v" + newest)
    except LookupError as exc:
        print(f"FAIL  {exc}"); return 1
    if not rn.items(body):
        print(f"FAIL  the newest section ({newest}) has no '- ' items to make a message from"); rc = 1
    msg = rn.telegram(changelog, "v" + newest, "https://github.com/hqpulse/hermes-standard/releases/tag/v" + newest)
    for bad, why in (("`", "a backtick"), ("\u2014", "an em dash"), ("\u2013", "an en dash")):
        if bad in msg:
            print(f"FAIL  the message for {newest} carries {why}:\n{msg}"); rc = 1
    if re.search(r"\b(?=[0-9a-f]*\d)[0-9a-f]{7,40}\b", msg.replace("https://", "")):
        print(f"FAIL  the message for {newest} carries a commit id:\n{msg}"); rc = 1
    if msg.count("\n- ") > rn.MAX_BULLETS - 1:
        print(f"FAIL  the message for {newest} has more than {rn.MAX_BULLETS} bullets"); rc = 1
    if not msg.startswith(f"Pack v{newest} is out"):
        print(f"FAIL  the message for {newest} does not start with 'Pack v{newest} is out':\n{msg}"); rc = 1
    if rc == 0:
        print(f"ok: {len(versions)} versions parse; the message for {newest} reads as it should")
    return rc


if __name__ == "__main__":
    sys.exit(main())
