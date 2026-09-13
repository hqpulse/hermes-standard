#!/usr/bin/env python3
"""A pack version's release text, from its CHANGELOG section (hermes-fleet PUL-103).

    release_note.py section vX.Y.Z [--changelog CHANGELOG.md]
        the `## X.Y.Z` section of the CHANGELOG, the GitHub release body
    release_note.py telegram vX.Y.Z --release-url URL [--changelog CHANGELOG.md]
        the plain-English message for the Pulse Agents chat
    release_note.py send [--chat ID] < message.txt
        post it; TELEGRAM_BOT_TOKEN from the environment, never printed
    release_note.py --self-test

The message is for a person who does not read code: the section's top-level
items become bullets (a bold lead when there is one, else the first
sentence), scrubbed of backticks, paths, commit ids and em dashes, at most
eight. A version with no section is an error: the workflow fails, and the fix
is to add the section and tag the next patch (a tag is never moved).
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional

PULSE_AGENTS_CHAT = "-1004278712029"
MAX_BULLETS = 8
SHA = re.compile(r"\b(?=[0-9a-f]*\d)[0-9a-f]{7,40}\b")


def plain(text: str) -> str:
    text = (text or "").replace("—", ", ").replace("–", ", ").replace(" -- ", ", ")
    text = re.sub(r"\s*,\s*,\s*", ", ", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def version_key(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3])


def sections(changelog: str) -> Dict[str, str]:
    """{version: body} for every `## X.Y.Z` heading, in file order."""
    out: Dict[str, str] = {}
    current: Optional[str] = None
    for line in changelog.splitlines():
        m = re.match(r"^##\s+v?(\d+\.\d+\.\d+)\b", line)
        if m:
            current = m.group(1); out[current] = ""
        elif current is not None:
            out[current] += line + "\n"
    return {v: b.strip("\n") for v, b in out.items()}


def section(changelog: str, version: str) -> str:
    v = version.lstrip("v")
    body = sections(changelog).get(v, "")
    if not body.strip():
        raise LookupError(f"CHANGELOG.md has no '## {v}' section")
    return body


def first_sentence(text: str) -> str:
    text = re.sub(r"\*\*|__|`", "", plain(text))
    m = re.match(r"(.+?[.!?])(\s|$)", text)
    return (m.group(1) if m else text).strip()


def items(body: str) -> List[str]:
    """The top-level `- ` items, each as its bold lead or its first sentence.
    A wrapped item continues on indented lines; those are read with it."""
    out: List[str] = []
    cur: Optional[str] = None
    for line in body.splitlines():
        m = re.match(r"^- (.*)", line)
        if m:
            if cur is not None:
                out.append(cur)
            cur = m.group(1).strip()
        elif cur is not None and line.startswith("  ") and line.strip():
            cur += " " + line.strip()
        elif cur is not None and not line.strip():
            out.append(cur); cur = None
    if cur is not None:
        out.append(cur)
    result = []
    for text in out:
        bold = re.match(r"^\*\*(.+?)\*\*", text)
        result.append(bold.group(1) if bold else first_sentence(text))
    return result


def for_a_person(text: str) -> str:
    text = plain(text)
    text = text.replace("`", "")
    text = SHA.sub("", text)
    text = re.sub(r"\b(origin|upstream)/[\w./-]+", "", text)
    text = re.sub(r"\S+/\S+", "", text)                      # paths
    text = re.sub(r"\b[A-Z][A-Z0-9]*_[A-Z0-9_]+\b", "", text)   # ENV_NAMES
    text = re.sub(r"\s+([,.:;])", r"\1", text)
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r"\s{2,}", " ", text).strip(" ,;:")
    text = text[:1].upper() + text[1:] if text else text
    if len(text) > 160:
        text = text[:159].rsplit(" ", 1)[0].rstrip(" ,;:") + "."
    if text and text[-1] not in ".!?":
        text += "."
    return text


def telegram(changelog: str, version: str, release_url: str) -> str:
    v = "v" + version.lstrip("v")
    bullets: List[str] = []
    for it in items(section(changelog, version)):
        b = for_a_person(it)
        if b and b not in bullets:
            bullets.append(b)
    bullets = bullets[:MAX_BULLETS]
    parts = [f"Pack {v} is out." if not bullets else f"Pack {v} is out: {bullets[0][:1].lower() + bullets[0][1:]}"]
    if len(bullets) > 1:
        parts.append("\n".join(f"- {b}" for b in bullets[1:]))
    parts.append("It becomes the standard for every company with the next fleet release, and that note says so. "
                 "Each company then moves onto it in its quiet hour.")
    parts.append(f"Release: {release_url}")
    return "\n\n".join(parts)


def send(chat: str, text: str) -> int:
    tok = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not tok:
        print("release_note: no TELEGRAM_BOT_TOKEN", file=sys.stderr); return 1
    api = os.environ.get("TELEGRAM_API", "https://api.telegram.org").rstrip("/")
    data = urllib.parse.urlencode({"chat_id": chat, "text": text[:4000], "disable_web_page_preview": "true"}).encode()
    req = urllib.request.Request(f"{api}/bot{tok}/sendMessage", data=data)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        print(f"release_note: telegram answered {exc.code}: {exc.read().decode('utf-8', 'replace')[:200]}".replace(tok, "<token>"), file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"release_note: send failed: {type(exc).__name__}: {exc}".replace(tok, "<token>"), file=sys.stderr)
        return 1
    if body.get("ok") is not True:
        print(f"release_note: telegram said not ok: {json.dumps(body)[:200]}".replace(tok, "<token>"), file=sys.stderr)
        return 1
    print(f"release_note: sent {len(text)} characters to chat {chat}")
    return 0


SAMPLE = """# Changelog

## 0.11.1

- `ecw` script: a page that is not on the practice host (about:blank after the browser sidecar
  restarts) is "elsewhere", never "in the app", so `signin` signs in instead of declining.

## 0.11.0

- `logins` skill: a sibling `keeper` command. Companies that keep their working logins in
  Keeper get the same door as 1Password (hermes-fleet PLAN B9).
- `ecw` script: reads the host and login title from the lane when the env is unset, so a
  plugin scribe signs in with nothing extra configured.

## 0.10.0

- **The reach skill: who may reach the assistant, asked in her own chat.** Merged with 0.9.0's eCW command — the two entries below are the reach half.
- **A leave that did not happen is never reported as done.** The bridge now answers a refused
  group leave as a failure at skills/reach/scripts/reach; see d1da511.
"""


def self_test() -> int:
    rc = 0

    def check(label: str, ok: bool, got: str = "") -> None:
        nonlocal rc
        if not ok:
            rc = 1; print(f"FAIL  {label}")
            if got:
                print("      " + got[:500].replace("\n", "\n      "))

    check("sections: every heading, in order", list(sections(SAMPLE)) == ["0.11.1", "0.11.0", "0.10.0"])
    check("section: by version, with or without the v", section(SAMPLE, "v0.11.0") == section(SAMPLE, "0.11.0") and "keeper" in section(SAMPLE, "v0.11.0"))
    try:
        section(SAMPLE, "v0.12.0"); check("section: a missing version is an error", False)
    except LookupError as exc:
        check("section: a missing version names the heading", "## 0.12.0" in str(exc), str(exc))
    check("items: wrapped items are read whole, bold lead else first sentence",
          items(section(SAMPLE, "0.10.0")) == ["The reach skill: who may reach the assistant, asked in her own chat.", "A leave that did not happen is never reported as done."])
    check("items: a plain item's first sentence, wrapped", items(section(SAMPLE, "0.11.1")) == ['ecw script: a page that is not on the practice host (about:blank after the browser sidecar restarts) is "elsewhere", never "in the app", so signin signs in instead of declining.'])
    tg = telegram(SAMPLE, "v0.11.0", "https://github.com/hqpulse/hermes-standard/releases/tag/v0.11.0")
    check("telegram: headline is 'Pack vX.Y.Z is out: ...' with the first item", tg.startswith("Pack v0.11.0 is out: logins skill: a sibling keeper command."), tg)
    check("telegram: the other items are bullets", "\n- Ecw script: reads the host and login title from the lane when the env is unset, so a plugin scribe signs in with nothing extra configured." in tg, tg)
    check("telegram: no backticks", "`" not in tg, tg)
    check("telegram: what happens next, and the link", "next fleet release" in tg and tg.rstrip().endswith("Release: https://github.com/hqpulse/hermes-standard/releases/tag/v0.11.0"), tg)
    check("telegram: a blank line between ideas", "\n\n" in tg and "\n\n\n" not in tg, tg)
    tg2 = telegram(SAMPLE, "0.10.0", "u")
    check("telegram: no em dash, no path, no commit id", "—" not in tg2 and "skills/" not in tg2 and "d1da511" not in tg2, tg2)
    tg3 = telegram(SAMPLE, "0.11.1", "u")
    check("telegram: one item makes a headline and no list", tg3.count("\n- ") == 0 and tg3.startswith("Pack v0.11.1 is out: ecw script"), tg3)
    many = "## 1.0.0\n\n" + "".join(f"- Change number {i}.\n" for i in range(12))
    check("telegram: never more than eight bullets", telegram(many, "1.0.0", "u").count("\n- ") == MAX_BULLETS - 1)
    if rc == 0:
        print("self-test: ok (sections, items, the message: no backticks, no paths, no ids, no em dashes, at most eight bullets)")
    return rc


def main(argv: List[str]) -> int:
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print(__doc__.strip()); return 2
    if argv[1] == "--self-test":
        return self_test()
    args = argv[2:]
    opt: Dict[str, str] = {}
    pos: List[str] = []
    i = 0
    while i < len(args):
        if args[i].startswith("--") and i + 1 < len(args):
            opt[args[i][2:]] = args[i + 1]; i += 2
        else:
            pos.append(args[i]); i += 1
    if argv[1] == "send":
        return send(opt.get("chat") or os.environ.get("PACK_NOTES_CHAT_ID") or PULSE_AGENTS_CHAT, sys.stdin.read().strip("\n"))
    if argv[1] not in ("section", "telegram") or not pos:
        print(__doc__.strip(), file=sys.stderr); return 2
    changelog = open(opt.get("changelog", "CHANGELOG.md"), encoding="utf-8").read()
    try:
        if argv[1] == "section":
            sys.stdout.write(section(changelog, pos[0]) + "\n")
        else:
            sys.stdout.write(telegram(changelog, pos[0], opt.get("release-url", "")) + "\n")
    except LookupError as exc:
        print(f"release_note: {exc}", file=sys.stderr); return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
