#!/usr/bin/env python3
"""One markdown file per thing an agent meets more than once.

A supplier, a customer, a site, a candidate, a project, a machine. The agent reads the live system
every time; this file is only what we knew, when, and what has moved since. Import it, or run it:

    python3 entity_note.py where
    python3 entity_note.py key sap acme 4471
    python3 entity_note.py filename "Acme Tooling GmbH" SAP-ACME-4471
    python3 entity_note.py show <file.md>
    python3 entity_note.py rebuild-index <folder>
    python3 entity_note.py changed <before.json> <after.json>

Four traps this module exists to hold in ONE place, because every caller that re-derives them gets a
different answer and the differences are silent:

  1. WHERE THE NOTES ARE. OBSIDIAN_VAULT_PATH is what the engine's own Obsidian skill reads and what
     the fleet sets on every pod. Resolve it here, once. Note the wording: this is the "notes
     folder", never a bare "vault" - on a clinical cell "the vault" is the credential store, and a
     refusal that says "vault" reads as a password refusal to a provider standing in a corridor.
  2. THE FILENAME. Names arrive with commas, apostrophes, slashes, accents, invisible characters and
     the odd sixty-word legal entity. The name half is for humans; the KEY half is what makes the
     filename unique, and it is recovered from the filename alone with one rsplit.
  3. THE WRITE. A note half-written is a note that reads as complete. Every write is a temp file in
     the same folder plus a rename, 0600, because these files hold the private business of whoever
     the agent works for and on a clinical cell they hold PHI.
  4. THE DIFF. "What changed" must have a line for every fact we compare, including the ones that did
     not change. Silence in a diff reads as "nothing happened" when it meant "nobody looked", so
     changes() returns a `same` row rather than nothing.

This module is STRUCTURE over the engine's Obsidian skill, not a second way to touch the notes
folder. Reading, searching and creating a note by hand is that skill's job; frontmatter, dated
sections, the regenerated block, the index and the diff are this one's.

Standard library only, deliberately: the pack ships no dependencies to a pod, so the frontmatter
parser here is hand-rolled and dumb on purpose. It knows scalars, inline lists and block lists.
Anything else - a nested mapping, a multi-line string - is kept as the exact text it arrived as and
handed back untouched. Dumb and lossless beats clever and lossy: a key some later agent added must
survive an older writer, so untouched keys are re-emitted verbatim rather than re-rendered.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import sys
import tempfile
import unicodedata
from collections import namedtuple

# The pack's contract with anything that imports this. A plugin newer than the pack checks it and
# degrades in words rather than dying on a missing attribute:
#   if getattr(entity_note, "API_VERSION", 0) < 1: ...say so, do the simple thing...
API_VERSION = 1

NOTES_DIRNAME = "Notes"
DEV_NOTES = "~/Notes"          # a development box only, and only when it already exists
FILE_MODE = 0o600              # matches the plugin's Keeper and session caches; these files are private
DIR_MODE = 0o700
NAME_LIMIT = 60
SEPARATOR = " - "              # cannot occur inside a KEY, so the split back is exact
INLINE_LIST_WIDTH = 88

# Illegal in a filename somewhere, or fatal to a wikilink: [[Foo|Bar]] and [[Foo#Head]] mean
# something else entirely, and % breaks a link on the way through a URL.
ILLEGAL_IN_NAME = set('/\\:*?"<>|#^[]%')

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ISO_STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2})?([+-]\d{2}:?\d{2}|Z)?)?$")
_KEY_LINE = re.compile(r"^([A-Za-z0-9_][^:\n]*):(?:[ \t]+(.*))?$")
_LIST_ITEM = re.compile(r"^[ \t]*-[ \t]+(.*)$")
_FENCE = re.compile(r"^\s*(```|~~~)")
_NUMBER = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")


class Refusal(Exception):
    """A refusal in words, with a reason a tool can key on.

    Same vocabulary as the plugin's adapters: needs-a-person means a human is the next step. A
    refusal is never an exception a caller should swallow into a partial write; it means nothing was
    written and the sentence explains why.
    """

    def __init__(self, reason, error):
        super().__init__(error)
        self.reason = reason
        self.error = error

    def as_json(self):
        return {"ok": False, "reason": self.reason, "error": self.error}


# --------------------------------------------------------------- where the notes are

NotesRoot = namedtuple("NotesRoot", "path source note")


def notes_root(env=None):
    """The notes folder, resolved once, with one line of prose when it was not the obvious one.

    Order: OBSIDIAN_VAULT_PATH, the workspace's Notes folder, ~/Notes on a development box. A pod
    always has the first. Nothing is invented: if none of the three is there we refuse rather than
    create a folder somewhere nobody will look for it - a note written to the wrong folder is a note
    that has silently not been kept at all.
    """
    env = os.environ if env is None else env
    configured = (env.get("OBSIDIAN_VAULT_PATH") or "").strip()
    if configured:
        # Set but wrong is worse than unset: falling through would write a pod's notes to a home
        # directory nobody backs up or reads. Name the key and stop.
        if not os.path.isdir(configured):
            raise Refusal("needs-a-person",
                          "OBSIDIAN_VAULT_PATH is set to %s, which is not a folder on this box; "
                          "nothing was written, a person fixes the path" % configured)
        return NotesRoot(os.path.abspath(configured), "OBSIDIAN_VAULT_PATH", "")
    workspace = (env.get("ISTA_WORKSPACE") or env.get("HERMES_WORKSPACE") or "").strip()
    if workspace and os.path.isdir(workspace):
        path = os.path.join(os.path.abspath(workspace), NOTES_DIRNAME)
        return NotesRoot(path, "workspace",
                         "OBSIDIAN_VAULT_PATH is not set here, so the workspace notes folder was "
                         "used (%s)" % path)
    dev = os.path.expanduser(DEV_NOTES)
    if os.path.isdir(dev):
        return NotesRoot(dev, "home",
                         "OBSIDIAN_VAULT_PATH and the workspace are both unset, so the development "
                         "notes folder was used (%s)" % dev)
    raise Refusal("needs-a-person",
                  "there is no notes folder on this box: OBSIDIAN_VAULT_PATH is not set, no "
                  "workspace was found, and %s does not exist; nothing was written" % dev)


def entity_folder(folder_name, root=None, create=True):
    """<notes folder>/<Folder>, e.g. Suppliers. The folder name is the caller's word.

    We do not pluralise a kind for you. Guessing that a "person" lives in "Persons" and a "facility"
    in "Facilitys" is the kind of small invention that splits one set of notes across two folders.
    """
    base = root if root is not None else notes_root().path
    path = os.path.join(base, str(folder_name).strip().strip("/"))
    if create:
        os.makedirs(path, mode=DIR_MODE, exist_ok=True)
    return path


# --------------------------------------------------------------- names, keys, filenames


def clean_name(display):
    """The name half of a filename. Total: any input gives a safe string, possibly empty.

    Apostrophes, hyphens and accents survive on purpose (O'Brien Mary, Munoz Ana, Vandermeer-Katz).
    Case is NOT touched: only the caller knows whether its record system SHOUTS, and title-casing a
    supplier called "ACME GmbH" here would be this layer inventing a spelling it never saw.
    """
    text = unicodedata.normalize("NFC", "" if display is None else str(display))
    text = text.replace(",", "")                       # family name first still sorts like a roster
    out = []
    for ch in text:
        # Cf catches the zero-width and bidi characters. They are invisible in a filename, so a
        # human retyping the name gets a different filename and a second file for one thing.
        if ch in ILLEGAL_IN_NAME or unicodedata.category(ch) in ("Cc", "Cf", "Zl", "Zp"):
            out.append(" ")
        else:
            out.append(ch)
    text = " ".join("".join(out).split())               # collapse runs, trim, kill tabs and newlines
    text = text.lstrip(".")                             # a leading dot hides the note from Obsidian
    text = text.strip()
    if len(text) > NAME_LIMIT:
        head = text[:NAME_LIMIT + 1]                    # +1 so a name of exactly the limit survives
        space = head.rfind(" ")
        text = (head[:space] if space > 0 else text[:NAME_LIMIT]).strip()
    return text


def entity_key(system, tenant, record):
    """<system>-<tenant>-<record>, upper case, one hyphen per run of anything else.

    The tenant is whatever the record number is unique WITHIN - an org code, an account, a company
    id. Two systems reuse numbers; two tenants inside one system reuse them too, and a key without
    that middle part lets one customer's number open another customer's file.
    """
    parts = []
    for label, raw in (("record system", system), ("tenant", tenant), ("record number", record)):
        text = unicodedata.normalize("NFKC", "" if raw is None else str(raw)).strip()
        cleaned = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").upper()
        if not cleaned or cleaned == "UNKNOWN":
            raise Refusal("needs-a-person",
                          "no %s on this read; nothing was written to the entity file, because a "
                          "file without a %s is a file that can be opened for the wrong one"
                          % (label, label))
        parts.append(cleaned)
    return "-".join(parts)


def note_filename(display, key):
    """`<Name> - <KEY>.md`. The KEY has no spaces, so the LAST ' - ' is always the separator."""
    name = clean_name(display)
    if not name:
        raise Refusal("needs-a-person",
                      "nothing survives of that name once the characters a filename cannot hold are "
                      "removed; nothing was written, a person gives the name")
    if not key or " " in str(key):
        raise Refusal("needs-a-person",
                      "the entity key %r is not usable in a filename; nothing was written" % (key,))
    return "%s%s%s.md" % (name, SEPARATOR, key)


def key_from_filename(filename):
    """The KEY back out of a filename, exactly, with no parsing. Empty string when there is none."""
    stem = os.path.basename(str(filename))
    if stem.endswith(".md"):
        stem = stem[:-3]
    if SEPARATOR not in stem:
        return ""
    return stem.rsplit(SEPARATOR, 1)[1].strip()


def identity_fingerprint(values):
    """A dumb, exact identity string for the index: lower case, whitespace collapsed, joined by |.

    It is an EXACT lookup, never a similarity. Two people with the same name are two entities, and
    the fingerprint is only ever a way of asking "is this the same one" when a key has changed.
    """
    parts = []
    for v in values:
        parts.append(" ".join(str("" if v is None else v).split()).lower())
    return "|".join(parts)


# --------------------------------------------------------------- frontmatter


class Frontmatter:
    """An ordered key/value block that re-emits anything you did not touch, byte for byte.

    That is the whole design. A newer writer adds a key this parser has never heard of; an older
    writer opens the file, changes one date and saves. The unknown key must come back out exactly as
    it went in, so we keep the raw lines for every key and only render the ones that were set.
    """

    def __init__(self):
        self._order = []
        self._raw = {}          # key -> the exact lines it arrived as, newline terminated
        self._value = {}        # key -> parsed value (str, int, float, bool, None, list, or raw text)
        self._opaque = set()    # keys whose value we did not understand and will not re-render
        self.preamble = ""      # comments above the first key, kept so they survive a round trip

    # -- reading
    def __contains__(self, key):
        return key in self._value

    def __iter__(self):
        return iter(list(self._order))

    def keys(self):
        return list(self._order)

    def items(self):
        return [(k, self._value[k]) for k in self._order]

    def get(self, key, default=None):
        return self._value.get(key, default)

    def __getitem__(self, key):
        return self._value[key]

    def is_opaque(self, key):
        return key in self._opaque

    def as_dict(self):
        return {k: self._value[k] for k in self._order}

    # -- writing
    def set(self, key, value):
        if key not in self._value:
            self._order.append(key)
        self._value[key] = value
        self._raw.pop(key, None)          # from here on it renders from the value
        self._opaque.discard(key)
        return self

    def update(self, pairs):
        for k, v in (pairs.items() if hasattr(pairs, "items") else pairs):
            self.set(k, v)
        return self

    def drop(self, key):
        """Remove a key. An absent key means the record does not say; never write a zero instead."""
        if key in self._value:
            self._order.remove(key)
            self._value.pop(key, None)
            self._raw.pop(key, None)
            self._opaque.discard(key)
        return self

    def render(self):
        lines = []
        if self.preamble:
            lines.append(self.preamble if self.preamble.endswith("\n") else self.preamble + "\n")
        for key in self._order:
            raw = self._raw.get(key)
            if raw is not None:
                lines.append(raw)
                continue
            lines.append(_render_pair(key, self._value[key]))
        return "".join(lines)

    # -- construction from a parsed file
    def _load(self, key, raw, value, opaque=False):
        if key not in self._value:
            self._order.append(key)
        self._raw[key] = raw
        self._value[key] = value
        if opaque:
            self._opaque.add(key)


Note = namedtuple("Note", "fm body")


def parse_frontmatter(text):
    """(Frontmatter, body). No frontmatter is not an error: an empty block and the whole text back."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    fm = Frontmatter()
    if not text.startswith("---\n"):
        return fm, text
    end = text.find("\n---", 3)
    while end != -1:
        after = text[end + 4:end + 5]
        if after in ("\n", ""):
            break
        end = text.find("\n---", end + 1)
    if end == -1:
        # An opening fence with no closing one is a broken file, not a note with no frontmatter.
        raise Refusal("bad-note", "this note opens a frontmatter block and never closes it; "
                                  "nothing was written, a person looks at the file")
    block = text[4:end + 1]
    body = text[end + 5:]
    if body.startswith("\n"):
        body = body[1:]

    pending = []        # (key, [raw lines], inline text)
    preamble = []
    for line in block.splitlines(keepends=True):
        stripped = line.strip()
        m = _KEY_LINE.match(line.rstrip("\n"))
        if m and not line[:1].isspace():
            pending.append([m.group(1).strip(), [line], m.group(2)])
            continue
        if pending:
            pending[-1][1].append(line)
        elif stripped:
            preamble.append(line)
    fm.preamble = "".join(preamble)
    for key, raw_lines, inline in pending:
        raw = "".join(raw_lines)
        continuation = [l for l in raw_lines[1:] if l.strip()]
        if inline is not None and inline.strip() != "":
            value, opaque = _parse_scalar(inline.strip()), False
        elif continuation and all(_LIST_ITEM.match(l) for l in continuation):
            value = [_parse_scalar(_LIST_ITEM.match(l).group(1).strip()) for l in continuation]
            opaque = False
        elif continuation:
            # A nested mapping or a folded string. We do not understand it, so we do not touch it.
            value, opaque = raw, True
        else:
            value, opaque = None, False
        fm._load(key, raw, value, opaque)
    return fm, body


def parse_note(text):
    fm, body = parse_frontmatter(text)
    return Note(fm, body)


def render_note(note_or_fm, body=None):
    fm = note_or_fm.fm if isinstance(note_or_fm, Note) else note_or_fm
    text = note_or_fm.body if body is None and isinstance(note_or_fm, Note) else (body or "")
    rendered = fm.render()
    head = "---\n%s---\n" % rendered if rendered else ""
    if text and not text.startswith("\n"):
        head += "\n"
    if text and not text.endswith("\n"):
        text += "\n"
    return head + text


def read_note(path):
    with open(path, "r", encoding="utf-8") as fh:
        return parse_note(fh.read())


def write_note(path, note, body=None):
    """Render and write atomically. Returns the path."""
    atomic_write(path, render_note(note, body))
    return path


def _parse_scalar(text):
    text = text.strip()
    if text == "":
        return None
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        inner = text[1:-1]
        if text[0] == '"':
            return inner.replace('\\"', '"').replace("\\\\", "\\")
        return inner.replace("''", "'")
    if text.startswith("[") and text.endswith("]"):
        return [_parse_scalar(item) for item in _split_inline(text[1:-1]) if item.strip() != ""] \
            if text[1:-1].strip() else []
    low = text.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if low in ("null", "~"):
        return None
    if _NUMBER.match(text):
        # A date is not a number and must never become one: 2026-09-07 has to come back as itself.
        try:
            return int(text) if re.match(r"^[+-]?\d+$", text) else float(text)
        except ValueError:
            return text
    return text


def _split_inline(text):
    """Split an inline list on commas that are not inside quotes. Dumb, and enough for what we write."""
    items, buf, quote = [], [], ""
    for ch in text:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
            buf.append(ch)
        elif ch == ",":
            items.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    items.append("".join(buf))
    return items


def _plain_safe(text):
    if text == "" or text != text.strip() or "\n" in text:
        return False
    if text[0] in "-?:,[]{}#&*!|>'\"%@`" or text[0].isspace():
        return False
    if ": " in text or text.endswith(":") or " #" in text:
        return False
    # A comma is legal in a bare scalar and fatal in a list: rendered bare inside [a, b] the value
    # "Camacho, Rosa" reads back as two entries. Brackets and braces are flow syntax for the same
    # reason. Quote them all rather than reasoning about where the value is going to be used.
    if any(ch in text for ch in ",[]{}"):
        return False
    if text.lower() in ("true", "false", "yes", "no", "on", "off", "null", "~"):
        return False
    if _NUMBER.match(text):
        return False
    # A value that starts with a digit is quoted unless it is plainly a date or a stamp. A room
    # "308-B" or a part number "12" must not read as a number to whatever opens this next.
    if text[0].isdigit() and not ISO_STAMP.match(text):
        return False
    return True


def _render_value(value):
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return repr(value) if isinstance(value, float) else str(value)
    text = str(value)
    if _plain_safe(text):
        return text
    return '"%s"' % text.replace("\\", "\\\\").replace('"', '\\"')


def _render_pair(key, value):
    if isinstance(value, (list, tuple)):
        items = [_render_value(v) for v in value]
        inline = "%s: [%s]\n" % (key, ", ".join(items))
        if len(inline) - 1 <= INLINE_LIST_WIDTH:
            return inline
        return "%s:\n%s" % (key, "".join("  - %s\n" % item for item in items))
    if isinstance(value, str) and value.startswith("%s:" % key) and "\n" in value:
        return value if value.endswith("\n") else value + "\n"      # an opaque block, handed back
    return "%s: %s\n" % (key, _render_value(value))


# --------------------------------------------------------------- the write


def atomic_write(path, text, mode=FILE_MODE):
    """Temp file in the SAME folder, fsync, rename. A reader sees the old note or the new one.

    The temp file is dot-prefixed so that a process killed between the write and the rename leaves
    something Obsidian hides and rebuild_index skips, rather than a half note sitting in the folder
    looking like a real one.
    """
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, mode=DIR_MODE, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".entity-note.", suffix=".tmp")
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
        tmp = None
    finally:
        if tmp is not None and os.path.exists(tmp):
            os.unlink(tmp)
    try:
        dirfd = os.open(folder, os.O_RDONLY)
        try:
            os.fsync(dirfd)          # the rename itself has to survive the power going out
        finally:
            os.close(dirfd)
    except OSError:
        pass                          # some filesystems refuse this; the rename is still atomic
    return path


# --------------------------------------------------------------- sections and blocks

Section = namedtuple("Section", "level title start end text")


def sections(body, level=3):
    """Every heading at that level, in file order, with the text under it.

    A section runs to the next heading at that level OR SHALLOWER, so a deeper heading stays inside
    it. Headings inside a fenced code block are not headings; a note with a code sample in it would
    otherwise grow phantom sections and an append would land in the middle of one.
    """
    marker = "#" * int(level) + " "
    found, fence = [], None
    lines = body.splitlines(keepends=True)
    offset, starts = 0, []
    for line in lines:
        f = _FENCE.match(line)
        if f:
            if fence is None:
                fence = f.group(1)
            elif line.strip().startswith(fence):
                fence = None
        elif fence is None and line.startswith("#"):
            hashes = len(line) - len(line.lstrip("#"))
            if line.startswith(marker):
                starts.append((offset, hashes, line[len(marker):].strip()))
            elif hashes < int(level) and line[hashes:hashes + 1] == " ":
                starts.append((offset, hashes, None))
        offset += len(line)
    for i, (start, _hashes, title) in enumerate(starts):
        if title is None:
            continue
        end = len(body)
        for later_start, _h, _t in starts[i + 1:]:
            end = later_start
            break
        found.append(Section(int(level), title, start, end, body[start:end]))
    return found


def section_dates(body, level=3):
    """The leading ISO date of every section heading, in file order. Headings without one are skipped."""
    out = []
    for sec in sections(body, level):
        m = re.match(r"^(\d{4}-\d{2}-\d{2})\b", sec.title)
        if m:
            out.append(m.group(1))
    return out


def find_section(body, title, level=3):
    for sec in sections(body, level):
        if sec.title.strip() == str(title).strip():
            return sec
    return None


def append_section(body, heading, text, level=3, section_id=None):
    """(body, added). Appends at the END of the file and never touches what is above it.

    Oldest first, append only: nothing already written moves, so a wrong write is recoverable and two
    appends cannot corrupt each other. Idempotency is by section_id when you give one - two reads on
    the same day share a heading and are NOT the same encounter, so the heading alone is only the
    fallback.
    """
    if section_id:
        marker = "<!-- section: %s -->" % section_id
        if marker in body:
            return body, False
    else:
        marker = ""
        if find_section(body, heading, level) is not None:
            return body, False
    block = "%s %s\n" % ("#" * int(level), str(heading).strip())
    if marker:
        block += marker + "\n"
    block += "\n" + str(text).strip("\n") + "\n"
    joined = body if body.endswith("\n") or body == "" else body + "\n"
    if joined and not joined.endswith("\n\n"):
        joined += "\n"
    return joined + block, True


def make_block(name, text, start_note=""):
    open_marker = "<!-- %s:start%s -->" % (name, (" " + start_note.strip()) if start_note else "")
    return "%s\n%s\n<!-- %s:end -->" % (open_marker, str(text).strip("\n"), name)


def set_block(body, name, text, start_note=None, insert_before=None):
    """Replace the delimited block, or put one in. Everything outside the markers is untouched.

    This is the one part of a note a writer may overwrite. When the block is already there its
    opening marker is kept exactly as it was found unless you pass a new start_note, so whatever
    prose someone put in that marker survives every regeneration.
    """
    start_re = re.compile(r"<!--\s*%s:start[^\n]*?-->" % re.escape(name))
    end_re = re.compile(r"<!--\s*%s:end[^\n]*?-->" % re.escape(name))
    start, end = start_re.search(body), end_re.search(body)
    if start and end and end.start() > start.start():
        keep = start.group(0) if start_note is None else None
        block = (keep + "\n" + str(text).strip("\n") + "\n<!-- %s:end -->" % name) if keep \
            else make_block(name, text, start_note or "")
        return body[:start.start()] + block + body[end.end():], True
    block = make_block(name, text, start_note or "")
    if insert_before:
        at = body.find(insert_before)
        if at != -1:
            head = body[:at].rstrip("\n")
            return (head + "\n\n" if head else "") + block + "\n\n" + body[at:], True
    joined = body if body.endswith("\n") or body == "" else body + "\n"
    return joined + ("\n" if joined else "") + block + "\n", True


def staleness_banner(read_on, source_label, today_=None, warn_days=30,
                     kind_word="record", extra_lines=()):
    """The callout that goes above every fact in the file. Generic wording; override it if you must.

    It names a date, never "recently". Past warn_days it turns into a danger callout that opens with
    the number of days, because a reader who skims one line has to hit the age before the facts.
    """
    days = days_between(read_on, today_ or today())
    stale = days is not None and days > int(warn_days)
    head = "> [!danger] This file is a memory, not a %s." % kind_word if stale \
        else "> [!warning] This file is a memory, not a %s." % kind_word
    lines = [head]
    if stale and days is not None:
        lines.append("> Last read %d days ago - treat every line below as history." % days)
    lines.append("> Last read from %s on %s. Nothing on this page is today's %s. Read the %s live"
                 % (source_label, read_on or "an unrecorded date", kind_word, kind_word))
    lines.append("> before you act on it; where this file and the %s disagree the %s wins and a "
                 "correction is appended below." % (kind_word, kind_word))
    for line in extra_lines:
        lines.append("> " + str(line).strip())
    return "\n".join(lines)


# --------------------------------------------------------------- the diff

Change = namedtuple("Change", "field kind was now")


def changes(before, after, fields=None):
    """One row per field, ALWAYS, kind in added | removed | changed | same.

    A field that did not change gets a `same` row rather than nothing. Silence in a diff is read as
    "nothing happened" when what it meant was "nobody looked", and those two must never render the
    same. Absent means the key is missing or null: an empty list is a value ("we looked, there are
    none"), which is a different fact and stays a value.
    """
    before = dict(before or {})
    after = dict(after or {})
    if fields is None:
        fields = list(after.keys()) + [k for k in before.keys() if k not in after]
    rows = []
    for field in fields:
        was, now = before.get(field), after.get(field)
        had, has = field in before and was is not None, field in after and now is not None
        if not had and not has:
            kind = "same"
        elif not had:
            kind = "added"
        elif not has:
            kind = "removed"
        elif _same(was, now):
            kind = "same"
        else:
            kind = "changed"
        rows.append(Change(field, kind, was, now))
    return rows


def _same(a, b):
    if isinstance(a, (list, tuple)) or isinstance(b, (list, tuple)):
        return [str(x) for x in (a or [])] == [str(x) for x in (b or [])]
    return str(a) == str(b)


def today(now=None):
    return (now or datetime.date.today()).isoformat()


def days_between(earlier, later):
    """Whole days between two ISO dates (or the first ten characters of two stamps). None if unparsable.

    The only arithmetic this layer does. It never turns an interval into a date - "3 months" stays
    the words somebody said, because computing a due date from them is inventing a decision.
    """
    try:
        a = datetime.date.fromisoformat(str(earlier)[:10])
        b = datetime.date.fromisoformat(str(later)[:10])
    except (TypeError, ValueError):
        return None
    return (b - a).days


# --------------------------------------------------------------- the frontmatter contract


def starter_frontmatter(kind, key, display, cls, source, source_system, created=None):
    """The generic keys every entity note carries, in the order they are read in.

    `cls` has no default on purpose. The confidentiality class decides where a note may go, and a
    defaulted class is one that nobody chose.
    """
    fm = Frontmatter()
    fm.set("type", "entity")
    fm.set("entity_kind", str(kind))
    fm.set("entity_key", key)
    fm.set("entity_keys", [key])
    fm.set("display", str(display))
    fm.set("aliases", [])
    fm.set("class", str(cls))
    fm.set("source", str(source))
    fm.set("source_system", str(source_system))
    fm.set("created", created or today())
    fm.set("updated", created or today())
    # No encounters key yet, deliberately. sync_counters() counts them off the body once there is a
    # body; a file that says 0 before its first section is a claim nobody checked.
    return fm


def set_read(fm, read_at, complete=True, needs_a_person=False):
    """Copy the read stamp VERBATIM and derive read_on from it. Never restamp with our own clock.

    read_at is the moment the live system answered. If the writer stamped it instead, a note written
    from a cached payload an hour later would claim a freshness it does not have.
    """
    stamp = str(read_at or "").strip()
    if not ISO_STAMP.match(stamp):
        raise Refusal("bad-note",
                      "the read stamp %r is not the shape a record read produces; nothing was "
                      "written, because a made-up read time is a made-up freshness" % (read_at,))
    fm.set("read_at", stamp)
    fm.set("read_on", stamp[:10])
    fm.set("last_read_complete", bool(complete))
    fm.set("needs_a_person", bool(needs_a_person))
    return fm


def sync_counters(fm, body, level=3):
    """encounters, first_encounter, last_encounter, updated - all read back off the body.

    Counted from the headings rather than incremented, so the count is a checksum: if somebody edited
    the file by hand the number moves with them instead of quietly disagreeing.
    """
    dates = section_dates(body, level)
    fm.set("encounters", len(sections(body, level)))
    if dates:
        fm.set("first_encounter", min(dates))
        fm.set("last_encounter", max(dates))
    fm.set("updated", today())
    return fm


# --------------------------------------------------------------- the index (never a search)


def index_path(folder):
    return os.path.join(folder, ".index.json")


def load_index(folder):
    """The index is a CACHE. The frontmatter is the truth, so a missing or broken one is not fatal."""
    try:
        with open(index_path(folder), "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {"version": 1, "by_key": {}, "by_identity": {}}
    data.setdefault("version", 1)
    data.setdefault("by_key", {})
    data.setdefault("by_identity", {})
    return data


def save_index(folder, index):
    index["updated"] = today()
    atomic_write(index_path(folder), json.dumps(index, indent=1, sort_keys=True) + "\n")
    return index_path(folder)


def index_put(index, key, filename, identity=None):
    index.setdefault("by_key", {})[key] = os.path.basename(filename)
    if identity:
        index.setdefault("by_identity", {})[identity] = key
    return index


def index_lookup(index, key):
    return (index.get("by_key") or {}).get(key, "")


def index_identity(index, fingerprint):
    return (index.get("by_identity") or {}).get(fingerprint, "")


def rebuild_index(folder, identity_fields=()):
    """(index, problems), rebuilt from the files' own frontmatter. Never from the filenames.

    Two files claiming one key is a problem, not something to resolve by picking one: it means a
    merge went wrong or a file was copied, and a human decides which is which.
    """
    index = {"version": 1, "by_key": {}, "by_identity": {}}
    problems = []
    for entry in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        if entry.startswith(".") or not entry.endswith(".md"):
            continue
        path = os.path.join(folder, entry)
        try:
            note = read_note(path)
        except (OSError, Refusal) as exc:
            problems.append("%s could not be read (%s)" % (entry, exc))
            continue
        keys = note.fm.get("entity_keys") or []
        if isinstance(keys, str):
            keys = [keys]
        anchor = note.fm.get("entity_key")
        if anchor and anchor not in keys:
            keys = [anchor] + list(keys)
        if not keys:
            problems.append("%s has no entity_key in its frontmatter" % entry)
            continue
        for key in keys:
            seen = index["by_key"].get(str(key))
            if seen and seen != entry:
                problems.append("two files claim %s: %s and %s" % (key, seen, entry))
                continue
            index["by_key"][str(key)] = entry
        if identity_fields:
            fingerprint = identity_fingerprint([note.fm.get(f) for f in identity_fields])
            owner = index["by_identity"].get(fingerprint)
            if owner and owner != str(keys[0]):
                problems.append("two entities share the identity %s: %s and %s"
                                % (fingerprint, owner, keys[0]))
            else:
                index["by_identity"][fingerprint] = str(keys[0])
    return index, problems


def verify_note(note, key, identity=None, identity_fields=()):
    """Refuse unless this open file is that entity's. Called again immediately before every write.

    Belt and braces on purpose: a stale or corrupt index must never be able to point a fact at the
    wrong file, and the check that stops it costs one string comparison.
    """
    keys = note.fm.get("entity_keys") or []
    if isinstance(keys, str):
        keys = [keys]
    anchor = note.fm.get("entity_key")
    if anchor:
        keys = list(keys) + [anchor]
    if key not in [str(k) for k in keys]:
        raise Refusal("wrong-file",
                      "that file answers to %s and this read is %s; nothing was written, because a "
                      "fact written into another entity's file is the worst mistake this makes"
                      % (", ".join(str(k) for k in keys) or "no key", key))
    for field in identity_fields or ():
        want = " ".join(str((identity or {}).get(field) or "").split()).lower()
        have = " ".join(str(note.fm.get(field) or "").split()).lower()
        if want != have:
            raise Refusal("identity-mismatch",
                          "that file's %s is %r and this read says %r; nothing was written, a person "
                          "looks at both" % (field, note.fm.get(field), (identity or {}).get(field)))
    return True


Located = namedtuple("Located", "path exists note rename_from how")


def locate(folder, key, display, identity=None, identity_fields=()):
    """Find the one file this key belongs to. An index lookup, then a filename lookup. No search.

    Nothing is resolved by globbing, fuzzy matching or the engine's Obsidian search: two entities
    that look alike to a search are exactly the pair you must never confuse. Read only - a rename is
    the caller's call, and this hands back the old filename rather than moving anything itself.
    """
    expected = os.path.join(folder, note_filename(display, key))
    index = load_index(folder)
    filename = index_lookup(index, key)
    if filename:
        path = os.path.join(folder, filename)
        if os.path.isfile(path):
            note = read_note(path)
            verify_note(note, key, identity, identity_fields)
            rename = None if os.path.basename(path) == os.path.basename(expected) else path
            return Located(expected if rename else path, True, note, rename, "index")
    if os.path.isfile(expected):
        # The index was stale or gone. The filename carries the key, so the folder heals itself.
        note = read_note(expected)
        verify_note(note, key, identity, identity_fields)
        return Located(expected, True, note, None, "filename")
    return Located(expected, False, None, None, "new")


# --------------------------------------------------------------- the command line


def _print(payload, as_json):
    if as_json:
        print(json.dumps(payload, ensure_ascii=False))
    elif isinstance(payload, dict) and not payload.get("ok", True):
        print(payload.get("error", "refused"))
    elif isinstance(payload, dict):
        for key, value in payload.items():
            if key != "ok":
                print("%s: %s" % (key, value))
    else:
        print(payload)


def main(argv):
    args = [a for a in argv[1:] if a != "--json"]
    as_json = "--json" in argv[1:]
    cmd = args[0] if args else ""
    try:
        if cmd == "where":
            root = notes_root()
            _print({"ok": True, "path": root.path, "from": root.source, "note": root.note}, as_json)
        elif cmd == "key" and len(args) == 4:
            _print({"ok": True, "key": entity_key(args[1], args[2], args[3])}, as_json)
        elif cmd == "filename" and len(args) == 3:
            _print({"ok": True, "filename": note_filename(args[1], args[2])}, as_json)
        elif cmd == "show" and len(args) == 2:
            note = read_note(args[1])
            _print({"ok": True, "frontmatter": note.fm.as_dict(),
                    "sections": [s.title for s in sections(note.body)]}, as_json)
        elif cmd == "rebuild-index" and len(args) == 2:
            index, problems = rebuild_index(args[1])
            save_index(args[1], index)
            _print({"ok": not problems, "files": len(set((index.get("by_key") or {}).values())),
                    "keys": len(index.get("by_key") or {}), "problems": problems}, as_json)
        elif cmd == "changed" and len(args) == 3:
            with open(args[1], encoding="utf-8") as fh:
                before = json.load(fh)
            with open(args[2], encoding="utf-8") as fh:
                after = json.load(fh)
            rows = [c._asdict() for c in changes(before, after)]
            _print({"ok": True, "changes": rows} if as_json else
                   "\n".join("%s: %s (%s -> %s)" % (c["field"], c["kind"], c["was"], c["now"])
                             for c in rows), as_json)
        else:
            _print({"ok": False, "reason": "usage",
                    "error": "usage: entity_note.py where | key <system> <tenant> <record> | "
                             "filename <display> <key> | show <file.md> | rebuild-index <folder> | "
                             "changed <before.json> <after.json>  [--json]"}, as_json)
    except Refusal as refusal:
        _print(refusal.as_json(), as_json)
    except (OSError, ValueError) as exc:
        _print({"ok": False, "reason": "error", "error": str(exc)}, as_json)
    return 0            # a refusal is an answer, never a non-zero exit


if __name__ == "__main__":
    sys.exit(main(sys.argv))
