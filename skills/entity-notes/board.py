#!/usr/bin/env python3
"""One board, one HTML file, from a folder of entity notes and a board spec.

    board.py --spec <spec.json> --vault <dir> --out <file.html> [--context <c.json>]
             [--as-of YYYY-MM-DD] [--title <string>] [--demo] [--spec-version]

The Bases in `vault/` are the board you get inside Obsidian. This is the board you get when there is
no Obsidian: a self-contained page you can open off a disk, mail to nobody, and print. It reads the
same notes and answers the same question - what do we know about each of these, how old is it, and
what moved since last time.

WHAT THIS FILE MAY NOT KNOW. Nothing about any one domain. It draws dates, strings, lists, numbers
and "how old is this"; it has never heard of a customer, a supplier or a machine, and the words
for those things arrive in the SPEC, which the caller owns. That is the seam: a plugin ships a spec plus
whatever knowledge it takes to fill the rows, and this file never grows a special case for it. There
is a grep in tests/check_entity_notes.py that fails if a domain word turns up in here, and it is
there because the cheapest way to ship a feature is always to put one word in the wrong layer.

THE OUTPUT IS OFFLINE, AND THAT IS ENFORCED, NOT INTENDED. The page carries a Content-Security-
Policy meta that forbids every network origin, so a stylesheet, a font or a tracker pasted in later
is refused by the browser rather than fetched. Nothing is stored in the browser either: a board can
carry confidential rows, and a residue in a browser profile outlives the file it came from.

The renderer never invents a value. A row that has no value for a column gets an em dash meaning "we
have not looked"; a row whose note says the record was silent gets those words. Those two are drawn
differently on purpose, and the legend at the foot says which is which.
"""
from __future__ import annotations

import argparse
import datetime
import html
import json
import os
import re
import sys

sys.dont_write_bytecode = True   # the pack ships a file list; a __pycache__ beside it fails the check
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import entity_note as EN          # noqa: E402  the notes, the frontmatter, the dates

SPEC_VERSIONS = (1,)              # frozen once shipped: new capability is spec 2, spec 1 keeps drawing
DIR_MODE = 0o700
FILE_MODE = 0o600
LEVELS = ("fresh", "ageing", "old", "history", "unknown")


# --------------------------------------------------------------------- reading the spec and the rows

def load_spec(path):
    with open(path, "r", encoding="utf-8") as fh:
        spec = json.load(fh)
    version = spec.get("spec")
    if version not in SPEC_VERSIONS:
        raise EN.Refusal("bad-spec",
                         "that board spec says spec %r and this renderer draws %s; nothing was "
                         "written, because a spec it does not understand is a board with silent "
                         "gaps in it, not a board with a few odd columns"
                         % (version, " or ".join(str(v) for v in SPEC_VERSIONS)))
    return spec


def rows_from_folder(folder, spec):
    """Every note in the folder as a row: its frontmatter, plus the body under `_body`.

    Read in filename order, which is the record's own sort. A file that will not parse is not
    skipped quietly - it comes back as a row that says so, because a note missing from a board reads
    as an entity nobody is tracking.
    """
    rows, trouble = [], []
    if not os.path.isdir(folder):
        return rows, trouble
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".md") or name.startswith("."):
            continue
        path = os.path.join(folder, name)
        try:
            note = EN.read_note(path)
        except (EN.Refusal, OSError, UnicodeDecodeError) as exc:
            trouble.append("%s could not be read (%s)" % (name, exc))
            continue
        row = dict(note.fm.as_dict())
        row["_body"] = note.body
        row["_file"] = name
        row["_path"] = path
        rows.append(row)
    return rows, trouble


def load_rows(args, spec):
    if args.rows:
        with open(args.rows, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        rows = payload["rows"] if isinstance(payload, dict) else payload
        return [dict(r) for r in rows], list((payload or {}).get("trouble") or []) if isinstance(payload, dict) else []
    folder = args.vault
    sub = spec.get("folder")
    if sub and os.path.isdir(os.path.join(folder, sub)):
        folder = os.path.join(folder, sub)
    return rows_from_folder(folder, spec)


def keep_row(row, spec):
    """The two filters that are the spec's own, applied before anything is drawn.

    class_required is a refusal, not a filter: a board told to draw one confidentiality class and
    handed a note of another has been pointed at the wrong folder, and drawing the rest of it
    quietly would hide that.
    """
    kind = spec.get("entity_kind")
    if kind and str(row.get("entity_kind") or "") != str(kind):
        return False
    want = spec.get("class_required")
    if want and str(row.get("class") or "") != str(want):
        raise EN.Refusal("wrong-class",
                         "%s is class %r and this board draws only %r; nothing was rendered, because "
                         "a board pointed at the wrong folder is how one set of files ends up on a "
                         "screen meant for another"
                         % (row.get("_file") or row.get("entity_key") or "a note",
                            row.get("class"), want))
    return True


# --------------------------------------------------------------------- dates, ages, staleness

def _iso(value):
    text = str(value or "")[:10]
    return text if EN.ISO_DATE.match(text) else ""


def fmt_date(value, style="mm/dd/yy"):
    iso = _iso(value)
    if not iso:
        return ""
    y, m, d = iso.split("-")
    if style == "iso":
        return iso
    if style == "dd/mm/yy":
        return "%s/%s/%s" % (d, m, y[2:])
    return "%s/%s/%s" % (m, d, y[2:])


def fmt_num(values, value):
    """A number written to the precision the SERIES was written in, not to Python's shortest form.

    4.0 printed as "4" reads as a different measurement from the one in the note. The decimals come
    from the widest value in the series, so a caution quoting two of them quotes them alike.
    """
    places = 0
    for v in values:
        text = ("%.4f" % float(v)).rstrip("0")
        places = max(places, len(text.split(".")[1]) if "." in text else 0)
    return ("%%.%df" % min(places, 3)) % float(value)


def age_words(days):
    """13d, 4 mo, 2 yr. Rounded down, because a rounded-up age reads younger than it is."""
    if days is None:
        return ""
    if days < 0:
        return "in %dd" % abs(days)
    if days < 60:
        return "%dd" % days
    if days < 730:
        return "%d mo" % (days // 30)
    return "%d yr" % (days // 365)


def ladder_level(days, ladder):
    if days is None:
        return "unknown"
    for step in ladder:
        cap = step.get("upto_days")
        if cap is None or days <= int(cap):
            return step.get("level") or "unknown"
    return "history"


def row_staleness(row, spec, as_of):
    """(level, days, the date it was read). The one clock every faded row on the page runs on."""
    cfg = spec.get("staleness") or {}
    key = cfg.get("key")
    if not key:
        return "unknown", None, ""
    read_on = _iso(row.get(key))
    days = EN.days_between(read_on, as_of) if read_on else None
    return ladder_level(days, cfg.get("ladder") or []), days, read_on


# --------------------------------------------------------------------- the tiny filter language

def raise_flag(row, name):
    """A flag a cell noticed while drawing. Idempotent: a row drawn into two sections raises the
    same flag twice, and a count that grew because of where a row appears is a wrong count."""
    flags = row.setdefault("_flags", [])
    if name not in flags:
        flags.append(name)


def matches(row, when, ctx):
    """A JSON filter, evaluated by hand. No eval, no expression string, on purpose.

    A board spec is configuration that arrives from another repo; an expression language in it is an
    execution path in it. Six operators cover every view the design asked for.
    """
    if not when:
        return True
    if "all" in when:
        return all(matches(row, w, ctx) for w in when["all"])
    if "any" in when:
        return any(matches(row, w, ctx) for w in when["any"])
    if "not" in when:
        return not matches(row, when["not"], ctx)
    op = when.get("op") or "truthy"
    field = when.get("field")
    value = row.get(field) if field else None
    if op == "truthy":
        return bool(value) and str(value).lower() not in ("false", "0", "no")
    if op == "falsy":
        return not (bool(value) and str(value).lower() not in ("false", "0", "no"))
    if op == "empty":
        return value in (None, "", [], {})
    if op == "not_empty":
        return value not in (None, "", [], {})
    if op == "eq":
        return str(value) == str(when.get("value"))
    if op == "ne":
        return str(value) != str(when.get("value"))
    if op == "in":
        return str(value) in [str(v) for v in (when.get("value") or [])]
    if op == "staleness_in":
        return row["_level"] in [str(v) for v in (when.get("value") or [])]
    if op == "flag":
        return str(when.get("value")) in (row.get("_flags") or [])
    raise EN.Refusal("bad-spec", "this board spec uses a filter operator this renderer does not "
                                 "have: %r; nothing was rendered" % op)


# --------------------------------------------------------------------- the cells

E = html.escape
NOT_LOOKED = '<span class="dash" title="not in the note">&mdash;</span>'


def as_list(value):
    if value is None or value == "":
        return []
    return list(value) if isinstance(value, (list, tuple)) else [value]


def sub_text(row, col, style):
    """The 12px line under a cell. `sub` is one key or several joined by a middle dot."""
    keys = as_list(col.get("sub"))
    parts = []
    for key in keys:
        raw = row.get(key)
        if raw in (None, "", []):
            continue
        if isinstance(raw, str) and _iso(raw):
            raw = fmt_date(raw, style)
        parts.append(str(raw))
    return " &middot; ".join(E(p) for p in parts)


def absent_markup(row, key, spec):
    """The three-way absence, which is the whole reason this renderer exists.

    A key that is not on the note at all means nobody looked, and prints as a dash with that in the
    hover. A key whose value is the spec's absent word means somebody looked and the record was
    silent, and prints as those words. They must never draw the same.
    """
    word = spec.get("absent_word") or "not documented"
    if key not in row or row.get(key) in (None, ""):
        return NOT_LOOKED
    if str(row.get(key)).strip().lower() == str(word).lower():
        return '<span class="pill unknown">%s</span>' % E(word)
    return None


def cell_text(row, col, spec, style):
    """Text, and optionally the state word beside it as a pill.

    The pill lives in the same cell rather than a column of its own because a state belongs to the
    thing it is about; a column apart from it reads as a separate fact and sorts as one."""
    gap = absent_markup(row, col.get("key"), spec)
    if gap is not None:
        return gap
    main = E(str(row.get(col["key"])))
    if col.get("pill") and row.get(col["pill"]) not in (None, ""):
        palette = (spec.get("palettes") or {}).get(col.get("palette") or "", {})
        value = str(row.get(col["pill"]))
        token = palette.get(value) or palette.get(value.upper()) or "unknown"
        main += ' <span class="pill %s">%s</span>' % (E(token), E(value))
    sub = sub_text(row, col, style)
    return main + ('<span class="sub">%s</span>' % sub if sub else "")


def cell_identity(row, col, spec, style):
    name = E(str(row.get(col["key"]) or row.get("_file") or "?"))
    sub = sub_text(row, col, style)
    return ('<span class="ident">%s</span>' % name) + ('<span class="sub mono">%s</span>' % sub if sub else "")


def cell_pill(row, col, spec, style):
    gap = absent_markup(row, col.get("key"), spec)
    if gap is not None:
        return gap
    value = str(row.get(col["key"]))
    palette = (spec.get("palettes") or {}).get(col.get("palette") or "", {})
    token = palette.get(value) or palette.get(value.upper()) or "unknown"
    sub = sub_text(row, col, style)
    return ('<span class="pill %s">%s</span>' % (E(token), E(value))) + \
           ('<span class="sub">%s</span>' % sub if sub else "")


def cell_pills(row, col, spec, style):
    """One list drawn solid, an optional second list drawn outline. Both carry their own words.

    Solid is for the list whose presence changes what somebody does today; the spec decides which
    that is. An empty pair is an absence and prints as one, not as blank space.
    """
    groups = [(col.get("key"), col.get("style") or "solid")]
    for extra in col.get("also") or []:
        groups.append((extra.get("key"), extra.get("style") or "outline"))
    out = []
    looked = False
    for key, kind in groups:
        if key in row:
            looked = True
        for item in as_list(row.get(key)):
            out.append('<span class="pill %s-med" title="%s">%s</span>'
                       % (E(kind), E(str(key).replace("_", " ")), E(str(item))))
    if out:
        return '<span class="pillrow">%s</span>' % "".join(out)
    if not looked:
        return NOT_LOOKED
    return '<span class="pill unknown">%s</span>' % E(col.get("none_word") or "none")


def cell_date_age(row, col, spec, style):
    iso = _iso(row.get(col.get("key")))
    if not iso:
        gap = absent_markup(row, col.get("key"), spec)
        return gap if gap is not None else NOT_LOOKED
    days = EN.days_between(iso, row["_as_of"])
    return ('<span class="mono">%s</span>' % E(fmt_date(iso, style))) + \
           ('<span class="sub mono">%s</span>' % E(age_words(days)) if days is not None else "")


def cell_staleness(row, col, spec, style):
    """The chip that has to be true at a glance, and honest when there is nothing to be true about."""
    level, days, read_on = row["_level"], row["_days"], row["_read_on"]
    label = (spec.get("staleness") or {}).get("label") or "read"
    if not read_on:
        return '<span class="chip alert" title="no read date on this note">never read</span>'
    if level == "fresh":
        word = "today" if days == 0 else "%dd" % days
        token = "quiet"
    elif level == "ageing":
        word, token = "%d days" % days, "attention"
    elif level == "old":
        word, token = "%d days" % days, "attention"
    else:
        word, token = "%s %d days ago &middot; treat as history" % (E(label), days), "alert"
    return ('<span class="chip %s">%s</span>' % (token, word)) + \
           ('<span class="sub mono print-only">[%s %s]</span>' % (E(label), E(fmt_date(read_on, style))))


_INTERVAL = re.compile(r"(\d+(?:\.\d+)?)\s*(day|week|month|year)s?", re.I)
_UNIT_DAYS = {"day": 1, "week": 7, "month": 30, "year": 365}


def interval_days(text):
    """"3 months" as a number of days, or None. It is never turned into a DATE, anywhere.

    The words somebody said stay the words somebody said: a due date computed from them reads as a
    decision that was made, and nobody made it. The number is used for one thing only - deciding
    whether to say "past the interval" beside both of the dates it was worked out from.
    """
    m = _INTERVAL.search(str(text or ""))
    if not m:
        return None
    return int(float(m.group(1)) * _UNIT_DAYS[m.group(2).lower()])


def cell_interval_watch(row, col, spec, style):
    since = _iso(row.get(col.get("since")))
    interval = row.get(col.get("interval"))
    if not interval:
        return ('<span class="pill attention">%s</span>' % E(col.get("none_word") or "none asked for")) + \
               ('<span class="sub">%s</span>' % E(col.get("none_sub") or "")) if col.get("none_sub") \
            else '<span class="pill attention">%s</span>' % E(col.get("none_word") or "none asked for")
    days = EN.days_between(since, row["_as_of"]) if since else None
    want = interval_days(interval)
    over = days is not None and want is not None and days > want
    if over:
        raise_flag(row, "past_interval")
    main = '<span class="%s">%s</span>' % ("word past" if over else "word", E(str(interval)))
    if days is None:
        return main
    sub = "%s since %s" % (age_words(days), fmt_date(since, style))
    return main + '<span class="sub mono">%s</span>' % E(sub)


def sparkline(values, good_direction):
    """68x20, one line, a dot on the last point. Fewer than two points is not a trend and is not drawn."""
    nums = [float(v) for v in values]
    lo, hi = min(nums), max(nums)
    span = (hi - lo) or 1.0
    step = 64.0 / (len(nums) - 1)
    pts = " ".join("%.1f,%.1f" % (2 + i * step, 17 - ((v - lo) / span) * 14) for i, v in enumerate(nums))
    last = pts.split(" ")[-1].split(",")
    return ('<svg class="spark" width="68" height="20" viewBox="0 0 68 20" aria-hidden="true">'
            '<polyline points="%s" fill="none" stroke="currentColor" stroke-width="1.5" '
            'stroke-linejoin="round" stroke-linecap="round" opacity="0.7"/>'
            '<circle cx="%s" cy="%s" r="2.5" fill="currentColor"/></svg>' % (pts, last[0], last[1]))


def cell_series(row, col, spec, style):
    """The numbers over time, the change since the one before, and a caution when the note's own
    word for the trend and the numbers point opposite ways.

    That last check is the only judgement on the page, and it is made from two things the SPEC
    supplies: which direction counts as good, and what each status word leads you to expect. This
    file compares two abstractions and knows what neither of them means.
    """
    # Two shapes, because the frontmatter parser keeps flat lists and leaves a nested mapping
    # opaque: a note writes `lead_time_values:` and `lead_time_dates:` as two block lists, while a
    # caller handing rows in as JSON can pass one object. Both mean the same series.
    raw = row.get(col["key"])
    data = raw if isinstance(raw, dict) else {"values": raw, "dates": row.get(col.get("dates"))}
    values = [float(v) for v in as_list(data.get("values")) if isinstance(v, (int, float))]
    dates = [_iso(d) for d in as_list(data.get("dates"))]
    unit = data.get("unit") or col.get("unit") or ""
    text = row.get(col.get("text")) if col.get("text") else None
    measured = _iso(row.get(col.get("measured_on"))) if col.get("measured_on") else ""
    if not values:
        gap = absent_markup(row, col.get("text") or col["key"], spec)
        return gap if gap is not None else NOT_LOOKED
    body = ""
    caution = ""
    if len(values) >= 2:
        delta = values[-1] - values[-2]
        good = col.get("good_direction") or "none"
        token = "muted"
        if delta != 0 and good in ("down", "up"):
            improving = (delta < 0) if good == "down" else (delta > 0)
            token = "good" if improving else "attention"
        sign = "−" if delta < 0 else "+"
        was_on = fmt_date(dates[-2], style) if len(dates) >= 2 else ""
        label = "%s%s %s%s" % (sign, fmt_num(values, abs(round(delta, 6))), unit,
                               " since " + was_on if was_on else "")
        aria = "%s %s, %s to %s, %s" % (
            ", ".join(fmt_num(values, v) for v in values), unit or "units",
            fmt_date(dates[0], style) if dates else "", fmt_date(dates[-1], style) if dates else "",
            "falling" if values[-1] < values[0] else ("rising" if values[-1] > values[0] else "flat"))
        spark = sparkline(values, col.get("good_direction"))
        expect = (col.get("expect") or {}).get(str(row.get(col.get("expect_from")) or ""))
        if expect in ("down", "up", "flat"):
            moved = "rose" if delta > 0 else ("fell" if delta < 0 else "did not move")
            disagrees = (expect == "down" and delta > 0) or (expect == "up" and delta < 0) or \
                        (expect == "flat" and values[-2] and abs(delta) / abs(values[-2]) > 0.2)
            if disagrees:
                raise_flag(row, "disagreement")
                words = _caution_words(row, col, values, moved, unit, measured, style)
                # The badge stays in the cell; the SENTENCE goes on the row's own full-width line,
                # where there is room for it and where it prints. It used to live in title= and
                # aria-label= only, so the one judgement on the page needed a hover to read and did
                # not survive a laser printer at all.
                row["_caution"] = words
                caution = ('<span class="caution" role="img" aria-label="%s">!</span>' % E(words))
        body = ('<span class="trend" role="img" aria-label="%s">%s'
                '<span class="deltarow"><span class="delta %s">%s</span>%s</span></span>'
                % (E(aria), spark, token, E(label), caution))
        caution = ""
    else:
        body = '<span class="sub">%s</span>' % E(col.get("first_word") or "first measurement")
    below = E(str(text)) if text else ""
    if measured:
        below = (below + " &middot; " if below else "") + E(fmt_date(measured, style))
    return body + caution + ('<span class="sub mono">%s</span>' % below if below else "")


def _caution_words(row, col, values, moved, unit, measured, style):
    return "documented %s on %s; the last two measurements %s (%s → %s %s). %s" % (
        str(row.get(col.get("expect_from")) or "?"), fmt_date(measured, style) or "an unrecorded date",
        moved, fmt_num(values, values[-2]), fmt_num(values, values[-1]), unit,
        col.get("caution_hint") or "Check the source record.")


CELLS = {"text": cell_text, "identity": cell_identity, "pill": cell_pill, "pills": cell_pills,
         "date_age": cell_date_age, "staleness": cell_staleness, "series": cell_series,
         "interval_watch": cell_interval_watch}


# --------------------------------------------------------------------- the look

CSS = """
:root{
  --bg:#FBFAF8; --surface:#FFFFFF; --surface-hover:#F5F3EF; --line:#E6E2DB; --line-soft:#EFECE6;
  --text:#1C1B19; --muted:#6B665E; --accent:#1F5F8B;
  --good:#0F6B45; --progress:#0B5F6B; --attention:#8A5A00; --alert:#96201F;
  --good-bg:#E2F2E9; --good-br:#BFE0CE; --prog-bg:#DFF0F2; --prog-br:#B9DDE2;
  --att-bg:#FAEFD8; --att-br:#E7D2A2; --alert-bg:#F9E5E4; --alert-br:#E9BEBB;
  --closed:#57534C; --closed-bg:#EFEDE8; --closed-br:#DCD8D0;
  --solid-bg:#2A2621; --solid-fg:#FFFFFF; --outline-fg:#4A463F; --outline-br:#B8B2A8;
  --sans:-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
}
@media (prefers-color-scheme:dark){
  :root{
    --bg:#171613; --surface:#1F1E1A; --surface-hover:#26241F; --line:#33312B; --line-soft:#2A2823;
    --text:#F2EFE9; --muted:#A19B90; --accent:#7EB8DE;
    --good:#7FE0AE; --progress:#78D6E2; --attention:#EFB964; --alert:#F3928E;
    --good-bg:#12301F; --good-br:#1E4A33; --prog-bg:#0F2C30; --prog-br:#1B4A50;
    --att-bg:#35270D; --att-br:#5A431A; --alert-bg:#3A1A1A; --alert-br:#5E2B29;
    --closed:#ADA79D; --closed-bg:#26241F; --closed-br:#3A362F;
    --solid-bg:#EDE9E2; --solid-fg:#171613; --outline-fg:#C6C0B5; --outline-br:#4A463F;
  }
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 var(--sans);
     -webkit-font-smoothing:antialiased}
.wrap{max-width:1320px;margin:0 auto;padding:24px}
.mono{font-family:var(--mono);font-variant-numeric:tabular-nums}
h1{font-size:22px;font-weight:600;margin:0;letter-spacing:-0.01em}
.sub-head{font-size:13px;color:var(--muted);margin-top:4px}
.sub-head.warn{color:var(--attention)}
.counts{font-size:13px;margin-top:4px}
.counts b{font-weight:600}

.banner{margin:16px 0 0;padding:12px 16px;border-left:3px solid var(--attention);
        background:var(--att-bg);color:var(--text);font-size:13px;line-height:1.5;border-radius:0 8px 8px 0}

.tiles{display:flex;gap:8px;margin:16px 0 0;flex-wrap:wrap}
.tile{flex:1 1 148px;min-width:148px;background:var(--surface);border:1px solid var(--line);
      border-radius:12px;padding:12px;text-align:left;cursor:pointer;font:inherit;color:inherit;
      transition:border-color .12s ease,background .12s ease}
.tile:hover{background:var(--surface-hover)}
.tile .n{display:block;font-size:28px;font-weight:600;font-family:var(--mono);
         font-variant-numeric:tabular-nums;line-height:1.1}
.tile .l{display:block;font-size:12px;color:var(--muted);text-transform:uppercase;
         letter-spacing:.04em;margin-top:4px}
.tile[aria-pressed="true"]{border:2px solid var(--accent);padding:11px;background:var(--surface-hover)}
.tile.zero{opacity:.45;cursor:default}
.tile:focus-visible,.grp:focus-visible,.row:focus-visible{outline:2px solid var(--accent);outline-offset:2px}

.bar{position:sticky;top:0;z-index:5;display:flex;gap:12px;align-items:center;flex-wrap:wrap;
     margin:16px 0 0;padding:8px 0;background:var(--bg);border-bottom:1px solid var(--line)}
.bar input{font:inherit;padding:6px 10px;border:1px solid var(--line);border-radius:8px;
           background:var(--surface);color:var(--text);min-width:220px}
.bar .showing{font-size:13px;color:var(--muted)}
.bar button{font:inherit;font-size:13px;background:none;border:1px solid var(--line);
            border-radius:8px;padding:5px 10px;cursor:pointer;color:var(--text)}
.nomatch{font-size:13px;color:var(--muted);padding:12px 0}

h2.sec{font-size:14px;font-weight:600;letter-spacing:.03em;text-transform:uppercase;
       margin:32px 0 0;color:var(--text)}
.sec-empty{font-size:13px;color:var(--muted);margin-top:8px}

/* An author rule beats the browser's own [hidden]{display:none} whatever the specificity, so a
   .grp told to hide by the filter stayed on screen with nothing under it. Every display rule in
   this sheet that sits on something the filter can hide needs its own [hidden] partner. */
[hidden]{display:none!important}
.grp{display:flex;gap:8px;align-items:baseline;width:100%;text-align:left;font:inherit;
     background:none;border:0;border-bottom:1px solid var(--line);padding:16px 0 6px;cursor:pointer;
     color:inherit;margin-top:8px;flex-wrap:wrap}
.grp .name{font-size:14px;font-weight:600;letter-spacing:.03em;text-transform:uppercase}
.grp .meta{font-size:12px;color:var(--muted)}
.grp .caret{font-size:11px;color:var(--muted);width:12px}

table{width:100%;border-collapse:collapse;table-layout:fixed}
thead th{font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.04em;
         color:var(--muted);text-align:left;padding:8px 12px 6px;border:0}
tr.row{border-top:1px solid var(--line-soft);cursor:pointer}
tr.row-since+tr.row{border-top:1px solid var(--line-soft)}
tr.row:hover{background:var(--surface-hover)}
tr.head-row{border:0}
td{padding:10px 12px;vertical-align:top;font-size:13px;line-height:1.3;overflow-wrap:anywhere}
tr.row-since td{padding:0 12px 10px;font-size:13px;color:var(--muted);border:0}
tr.row-since{cursor:pointer}
tr.row-since:hover{background:var(--surface-hover)}
tr.row-since .tag{text-transform:uppercase;letter-spacing:.04em;font-size:11px;margin-right:6px;
                  color:var(--muted);opacity:.75}
tr.row+tr.row-since td{padding-top:0}
.ident{font-size:14px;font-weight:600;display:block}
.sub{display:block;font-size:12px;color:var(--muted);margin-top:2px}
.dash{color:var(--muted)}
.word.past{color:var(--attention);font-weight:600}

.pill{display:inline-block;font-size:11px;font-weight:600;text-transform:uppercase;
      letter-spacing:.04em;padding:2px 7px;border-radius:999px;border:1px solid transparent;
      white-space:nowrap}
.pillrow{display:flex;flex-wrap:wrap;gap:4px}
.pill.good{color:var(--good);background:var(--good-bg);border-color:var(--good-br)}
.pill.progress{color:var(--progress);background:var(--prog-bg);border-color:var(--prog-br)}
.pill.attention{color:var(--attention);background:var(--att-bg);border-color:var(--att-br)}
.pill.closed{color:var(--closed);background:var(--closed-bg);border-color:var(--closed-br)}
.pill.alert{color:var(--alert);background:var(--alert-bg);border-color:var(--alert-br)}
.pill.unknown{color:var(--muted);background:transparent;border:1px dashed var(--line);
              text-transform:none;letter-spacing:0;font-weight:400}
.pill.solid-med{color:var(--solid-fg);background:var(--solid-bg);border-color:var(--solid-bg);
                text-transform:none;letter-spacing:0;white-space:normal;max-width:100%}
.pill.outline-med{color:var(--outline-fg);background:transparent;border-color:var(--outline-br);
                  text-transform:none;letter-spacing:0;font-weight:500;white-space:normal;max-width:100%}
.chip{display:inline-block;font-size:11px;font-weight:600;padding:2px 7px;border-radius:6px;
      border:1px solid transparent;line-height:1.35;max-width:100%}
.chip.quiet{color:var(--muted);background:transparent;border-color:var(--line)}
.chip.attention{color:var(--attention);background:var(--att-bg);border-color:var(--att-br)}
.chip.alert{color:var(--alert);background:var(--alert-bg);border-color:var(--alert-br)}

.trend{display:flex;flex-direction:column;align-items:flex-start;gap:1px}
.spark{flex:0 0 auto;color:var(--text)}
.deltarow{display:flex;align-items:flex-start;gap:4px}
.delta{font-family:var(--mono);font-size:11px;font-variant-numeric:tabular-nums}
.delta.good{color:var(--good)} .delta.attention{color:var(--attention)} .delta.muted{color:var(--muted)}
.caution{flex:0 0 auto;display:inline-flex;align-items:center;justify-content:center;width:15px;height:15px;
         border-radius:50%;background:var(--att-bg);border:1px solid var(--att-br);
         color:var(--attention);font-size:10px;font-weight:700}
.cautionline{display:block;margin-bottom:3px;color:var(--attention);opacity:1}
.cautionline .caution{margin-right:6px;vertical-align:1px}

tr.lvl-old td.ages{opacity:.62}
tr.lvl-old td.ages .dated{border-bottom:1px dotted var(--muted)}
tr.lvl-old{box-shadow:inset 3px 0 0 var(--attention)}
tr.row-since.lvl-old{box-shadow:inset 3px 0 0 var(--attention)}
tr.lvl-history td.ages{opacity:.5}
tr.lvl-history td.ages .pill,tr.lvl-history td.ages .chip{color:var(--muted);background:transparent;
  border-color:var(--line)}
tr.lvl-history td.ages .delta,tr.lvl-history td.ages .spark{color:var(--muted)}
tr.lvl-history,tr.row-since.lvl-history{box-shadow:inset 3px 0 0 var(--alert);
  background-image:repeating-linear-gradient(45deg,transparent 0 9px,var(--line-soft) 9px 10px)}
tr.lvl-history td.ident-cell,tr.lvl-history td.ident-cell *{opacity:1}
tr.lvl-old td .caution,tr.lvl-history td .caution{opacity:1;color:var(--attention);
  background:var(--att-bg);border-color:var(--att-br)}
tr.nonote{border-top:1px dashed var(--line)}
tr.nonote td{opacity:.85}
tr.person,tr.row-since.person{box-shadow:inset 3px 0 0 var(--alert)}

.legend{margin-top:32px;padding-top:16px;border-top:1px solid var(--line);font-size:12px;
        color:var(--muted);line-height:1.6}
.legend b{color:var(--text);font-weight:600}
.print-only{display:none}

.scrim{position:fixed;inset:0;background:rgba(20,18,15,.38);opacity:0;pointer-events:none;
       transition:opacity .16s ease-out;z-index:9}
.scrim.on{opacity:1;pointer-events:auto}
.drawer{position:fixed;top:0;right:0;bottom:0;width:min(420px,92vw);background:var(--surface);
        border-left:1px solid var(--line);transform:translateX(100%);transition:transform .16s ease-out;
        z-index:10;overflow-y:auto;padding:24px}
.drawer.on{transform:translateX(0)}
.drawer h3{margin:0;font-size:18px;font-weight:600}
.drawer .key{font-family:var(--mono);font-size:12px;color:var(--muted);margin-top:2px}
.drawer .memory{margin:16px 0;padding:8px 12px;border-left:2px solid var(--attention);
                font-size:12px;color:var(--muted);line-height:1.5}
.drawer dl{display:grid;grid-template-columns:auto 1fr;gap:4px 12px;margin:16px 0;font-size:13px}
.drawer dt{color:var(--muted);font-size:12px}
.drawer dd{margin:0}
.drawer h4{font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);
           margin:24px 0 8px;font-weight:600}
.drawer .note-sec{border-top:1px solid var(--line-soft);padding-top:12px;margin-top:12px;font-size:13px}
.drawer .note-sec h5{margin:0 0 6px;font-size:13px;font-weight:600}
.drawer .note-sec p{margin:6px 0}
.drawer .note-sec ul{margin:6px 0;padding-left:18px}
.drawer .note-sec blockquote{margin:6px 0;padding-left:10px;border-left:2px solid var(--line);
                             color:var(--muted)}
.drawer .path{margin-top:24px;font-family:var(--mono);font-size:11px;color:var(--muted);
              word-break:break-all}
.drawer .close{position:absolute;top:16px;right:16px;background:none;border:1px solid var(--line);
               border-radius:8px;font:inherit;padding:4px 9px;cursor:pointer;color:var(--text)}
@media (prefers-reduced-motion:reduce){.drawer,.scrim{transition:none}}

@media screen and (max-width:1000px){
  thead{display:none}
  tr.row{display:block;padding:12px 0}
  tr.row td{display:block;padding:2px 0}
  tr.row-since td{padding:6px 0 0}
  tr.row td::before{content:attr(data-label);display:block;font-size:11px;text-transform:uppercase;
                    letter-spacing:.04em;color:var(--muted);margin-bottom:2px}
  tr.row td.ident-cell::before{content:none}
  tr.row td.blank{display:none}
  .drawer{width:100vw}
}
@media print{
  @page{size:A4 landscape;margin:12mm}
  :root{--bg:#fff;--surface:#fff;--surface-hover:#fff;--line:#bbb;--line-soft:#ddd;--text:#000;--muted:#444}
  .tiles,.bar,.scrim,.drawer,.grp .caret{display:none!important}
  .print-only{display:block}
  body{font-size:8.5pt}
  .wrap{max-width:none;padding:0}
  /* the column percentages are drawn for a 1272px screen; on paper the content sizes itself */
  table{table-layout:auto}
  td,thead th{padding:5px 6px}
  h1{font-size:15pt}
  .spark{display:none}
  tr.row,tr.row-since,.grp,h2.sec{page-break-inside:avoid}
  tr.row{page-break-after:avoid}
  tr.lvl-old td.ages,tr.lvl-history td.ages{opacity:1}
  tr.lvl-history{background-image:none}
  .pill,.chip{border:1px solid #999!important;background:none!important;color:#000!important}
  .cautionline{color:#000;font-weight:600}
  .cautionline .caution{border-color:#000;color:#000;background:none}
  .banner{background:none;border-left:3px solid #000}
}
"""


JS = """
(function(){
  var state = {tiles:{}, q:""};
  var rows = Array.prototype.slice.call(document.querySelectorAll("tr.row"));
  var tiles = Array.prototype.slice.call(document.querySelectorAll(".tile"));
  var data = JSON.parse(document.getElementById("board-data").textContent);

  function on(){ var k=[]; for (var t in state.tiles) if (state.tiles[t]) k.push(t); return k; }
  function visible(r){
    var t = on();
    for (var i=0;i<t.length;i++){ if ((" "+r.dataset.tiles+" ").indexOf(" "+t[i]+" ") < 0) return false; }
    if (state.q && r.dataset.search.indexOf(state.q) < 0) return false;
    return true;
  }
  function apply(){
    var shown = 0;
    rows.forEach(function(r){
      var v = visible(r); r.hidden = !v; if (v) shown++;
      var s = r.nextElementSibling;
      if (s && s.classList.contains("row-since")) s.hidden = !v;
    });
    // A group or a section with nothing left in it is noise, not information.
    Array.prototype.forEach.call(document.querySelectorAll("[data-group]"), function(g){
      var any = g.querySelectorAll("tr.row:not([hidden])").length;
      g.hidden = !any;
      var head = document.querySelector('[data-group-head="'+g.dataset.group+'"]');
      if (head) {
        head.hidden = !any;
        var c = head.querySelector(".gcount");
        if (c) c.textContent = any + " row" + (any === 1 ? "" : "s")
                             + (any < +c.dataset.total ? " of " + c.dataset.total : "");
      }
    });
    Array.prototype.forEach.call(document.querySelectorAll("[data-section]"), function(s){
      var any = s.querySelectorAll("tr.row:not([hidden])").length;
      var empty = s.querySelector(".sec-empty-filtered");
      if (empty) empty.hidden = !!any || !(on().length || state.q);
    });
    var t = on().map(function(k){ return data.tileLabels[k] || k; });
    document.getElementById("showing").textContent =
      "showing: " + (t.length ? t.join(" + ") : "all") + (state.q ? ' matching "' + state.q + '"' : "");
    var none = document.getElementById("nomatch");
    none.hidden = shown > 0;
    none.textContent = shown ? "" : "Nothing matches. " + rows.length + " on the board.";
  }
  tiles.forEach(function(b){
    if (b.classList.contains("zero")) return;
    b.addEventListener("click", function(){
      var k = b.dataset.tile;
      state.tiles[k] = !state.tiles[k];
      b.setAttribute("aria-pressed", state.tiles[k] ? "true" : "false");
      apply();
    });
  });
  var box = document.getElementById("q");
  box.addEventListener("input", function(){ state.q = box.value.trim().toLowerCase(); apply(); });
  document.getElementById("reset").addEventListener("click", function(){
    state = {tiles:{}, q:""}; box.value = "";
    tiles.forEach(function(b){ b.setAttribute("aria-pressed","false"); });
    apply();
  });
  Array.prototype.forEach.call(document.querySelectorAll("[data-group-head]"), function(h){
    h.addEventListener("click", function(){
      var g = document.querySelector('[data-group="'+h.dataset.groupHead+'"]');
      var openNow = h.getAttribute("aria-expanded") === "true";
      h.setAttribute("aria-expanded", openNow ? "false" : "true");
      h.querySelector(".caret").textContent = openNow ? "\\u25B8" : "\\u25BE";
      g.style.display = openNow ? "none" : "";
    });
  });

  var drawer = document.getElementById("drawer"), scrim = document.getElementById("scrim");
  var body = document.getElementById("drawer-body"), lastRow = null;
  function open(id, row){
    var html = data.drawers[id];
    if (!html) return;
    body.innerHTML = html; lastRow = row;
    drawer.classList.add("on"); scrim.classList.add("on");
    drawer.setAttribute("aria-hidden","false");
    document.getElementById("drawer-close").focus();
  }
  function close(){
    drawer.classList.remove("on"); scrim.classList.remove("on");
    drawer.setAttribute("aria-hidden","true");
    if (lastRow) lastRow.focus();
  }
  rows.forEach(function(r){
    if (!r.dataset.id) return;
    r.addEventListener("click", function(){ open(r.dataset.id, r); });
    var s = r.nextElementSibling;
    if (s && s.classList.contains("row-since"))
      s.addEventListener("click", function(){ open(r.dataset.id, r); });
    r.addEventListener("keydown", function(e){
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(r.dataset.id, r); }
    });
  });
  scrim.addEventListener("click", close);
  document.getElementById("drawer-close").addEventListener("click", close);
  document.addEventListener("keydown", function(e){ if (e.key === "Escape") close(); });
  // Focus stays in the sheet while it is open: a tab that walks out of it lands on rows the reader
  // cannot see, and the next Enter opens the wrong one.
  drawer.addEventListener("keydown", function(e){
    if (e.key !== "Tab" || !drawer.classList.contains("on")) return;
    var f = drawer.querySelectorAll("button, [href], [tabindex]:not([tabindex='-1'])");
    if (!f.length) return;
    var first = f[0], last = f[f.length-1];
    if (e.shiftKey && document.activeElement === first){ e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last){ e.preventDefault(); first.focus(); }
  });
  apply();
})();
"""


# --------------------------------------------------------------------- the note's own words

def markdown_lite(text):
    """Enough markdown to show a note section as it was written, and no more.

    Bold, bullets, blockquotes, paragraphs. Everything is escaped first, so a note containing angle
    brackets or a stray tag renders as the characters somebody typed. A full markdown parser here
    would be a second way to interpret a note, and the note is the record.
    """
    out, buf, mode = [], [], None

    def flush():
        if not buf:
            return
        if mode == "ul":
            out.append("<ul>%s</ul>" % "".join("<li>%s</li>" % b for b in buf))
        elif mode == "quote":
            out.append("<blockquote>%s</blockquote>" % "<br>".join(buf))
        else:
            out.append("<p>%s</p>" % "<br>".join(buf))
        del buf[:]

    for raw in (text or "").splitlines():
        line = raw.rstrip()
        if not line.strip():
            flush(); mode = None; continue
        if line.lstrip().startswith("- "):
            want, content = "ul", line.lstrip()[2:]
        elif line.lstrip().startswith(">"):
            want, content = "quote", line.lstrip()[1:].strip()
        else:
            want, content = "p", line
        if want != mode:
            flush(); mode = want
        buf.append(re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", E(content)))
    flush()
    return "".join(out)


def drawer_html(row, spec, style):
    """The sheet: who this is, when it was last read, the numbers over time, and the note's own
    dated sections, verbatim. Nothing here is editable. The board is a reader."""
    cfg = spec.get("drawer") or {}
    parts = ['<h3>%s</h3>' % E(str(row.get(cfg.get("title_key") or "display") or row.get("_file")))]
    if cfg.get("key_key"):
        parts.append('<div class="key">%s</div>' % E(str(row.get(cfg["key_key"]) or "")))
    memory = row.get(cfg.get("memory_line_key") or "_memory_line")
    if memory:
        parts.append('<div class="memory">%s</div>' % E(str(memory)))
    fields = []
    for f in cfg.get("fields") or []:
        value = row.get(f.get("key"))
        if value in (None, "", []):
            continue
        if isinstance(value, str) and _iso(value):
            value = fmt_date(value, style)
        if isinstance(value, (list, tuple)):
            value = ", ".join(str(v) for v in value)
        fields.append("<dt>%s</dt><dd>%s</dd>" % (E(f.get("label") or f.get("key")), E(str(value))))
    if fields:
        parts.append("<dl>%s</dl>" % "".join(fields))
    for block in cfg.get("blocks") or []:
        items = as_list(row.get(block.get("key")))
        if not items:
            continue
        parts.append("<h4>%s</h4>" % E(block.get("label") or ""))
        parts.append("<ul>%s</ul>" % "".join("<li>%s</li>" % E(str(i)) for i in items))
    for sec in (row.get(cfg.get("sections_key") or "_sections") or []):
        parts.append('<div class="note-sec"><h5>%s</h5>%s</div>'
                     % (E(str(sec.get("title") or "")), markdown_lite(sec.get("text") or "")))
    if row.get("_note_path"):
        parts.append('<div class="path">%s</div>' % E(str(row["_note_path"])))
    return "".join(parts)


# --------------------------------------------------------------------- assembling the page

def order_key(row, fields):
    key = []
    for f in fields or []:
        v = row.get(f)
        key.append((1, "") if v in (None, "", []) else (0, str(v)))
    key.append((0, str(row.get("_sortname") or "")))
    return key


def apply_context(rows, context, spec):
    """The caller's own list for the day laid over the notes: a slot on a row, a note on a group,
    and a row for anything on that list we have no note for at all.

    That last one is the point. A board built only from the notes cannot show you the person nobody
    has looked up yet, which is exactly the person you needed to be told about.
    """
    match_on = spec.get("context_match") or "entity_key"
    by_key = {}
    for row in rows:
        if row.get(match_on):
            by_key[str(row[match_on])] = row
    extra = []
    for item in (context.get("rows") or []):
        target = by_key.get(str(item.get("id") or ""))
        if target is not None:
            for k, v in item.items():
                if k != "id":
                    target["context_" + k if k in ("slot", "group", "label") else k] = v
            continue
        if not item.get("no_note"):
            continue
        stub = {"_file": str(item.get("label") or item.get("id") or "?"),
                "display": item.get("label") or item.get("id"),
                "context_slot": item.get("slot"), "context_group": item.get("group"),
                "_no_note": True, "_sortname": str(item.get("label") or "")}
        for k, v in item.items():
            if k not in ("id", "label", "slot", "group", "no_note"):
                stub[k] = v
        extra.append(stub)
    return rows + extra


def render_row(row, spec, style, section_id):
    """One row of columns, and - when the note has one - a second row carrying the whole width for
    what moved since last time.

    Two `tr` elements rather than one cell with a big colspan: a fixed table lays a colspan out
    against columns that do not exist, and the row above it stops keeping its widths. The pair is
    kept together by the class on the second, which the filter hides and shows with the first.
    """
    cols = spec.get("columns") or []
    tds = []
    for col in cols:
        label = col.get("label") or ""
        classes = ["ages"] if col.get("ages") else []
        if col.get("type") == "identity":
            classes.append("ident-cell")
        if row.get("_no_note") and col.get("type") not in ("identity", "text"):
            inner = NOT_LOOKED
        elif row.get("_no_note"):
            inner = CELLS["identity" if col.get("type") == "identity" else "text"](row, col, spec, style)
        else:
            inner = CELLS[col.get("type") or "text"](row, col, spec, style)
        tds.append('<td class="%s" data-label="%s">%s</td>' % (" ".join(classes), E(label), inner))

    cls = ["row", "lvl-" + row["_level"]]
    if row.get("_no_note"):
        cls.append("nonote")
    if row.get("_needs_person"):
        cls.append("person")
    row_id = "" if row.get("_no_note") else (row.get("_id") or "")
    first = ('<tr class="%s" data-id="%s" data-tiles="%s" data-search="%s" tabindex="0">%s</tr>'
             % (" ".join(cls), E(row_id), E(" ".join(row.get("_tiles") or [])),
                E(row.get("_search") or ""), "".join(tds)))

    since_cfg = spec.get("secondary_line") or {}
    if row.get("_no_note"):
        text = row.get("_no_note_words") or spec.get("no_note_words") or "no note yet"
    else:
        text = row.get(since_cfg.get("key") or "")
    # Set while the cells above were rendered. It goes FIRST and at full contrast even on a row the
    # staleness ladder has faded: a caution about the source disagreeing with itself is exactly the
    # line an old row still has to be able to say.
    caution = row.get("_caution")
    if not text and not caution:
        return first
    body = ""
    if caution:
        body += ('<span class="cautionline"><span class="caution" aria-hidden="true">!</span>%s</span>'
                 % E(str(caution)))
    if text:
        body += ('<span class="tag">%s</span>%s'
                 % (E(since_cfg.get("label") or ""), E(str(text))))
    return first + ('<tr class="row-since %s"><td colspan="%d">%s</td></tr>'
                    % (" ".join(cls[1:]), len(cols), body))


def column_widths(spec):
    """Every column as a percentage, because a fixed table cannot lay out `fr`.

    The spec is written in the units a designer thinks in - pixels for a column that holds a time or
    a date, shares for the ones that hold prose. Both are resolved here against one nominal width,
    so the proportions are the designed ones at any window size and no column collapses to a
    character per line, which is what a `fr` in a `col` actually does.
    """
    cols = spec.get("columns") or []
    nominal = float(spec.get("nominal_width") or 1272)
    fixed, shares = {}, {}
    for i, col in enumerate(cols):
        w = col.get("width")
        if isinstance(w, str) and w.endswith("fr"):
            shares[i] = float(w[:-2] or 1)
        else:
            fixed[i] = float(str(w or 100).replace("px", ""))
    used = sum(fixed.values()) / nominal * 100.0
    spare = max(100.0 - used, 8.0)
    total_share = sum(shares.values()) or 1.0
    out = []
    for i in range(len(cols)):
        pct = fixed[i] / nominal * 100.0 if i in fixed else spare * shares[i] / total_share
        out.append("%.3f%%" % pct)
    return out


def render_table(spec, rows, style, section_id, group=None):
    cols = spec.get("columns") or []
    widths = column_widths(spec)
    head = "".join('<th scope="col">%s</th>' % E(c.get("label") or "") for c in cols)
    body = "".join(render_row(r, spec, style, section_id) for r in rows)
    return ('<table><colgroup>%s</colgroup>'
            '<thead><tr class="head-row">%s</tr></thead><tbody>%s</tbody></table>'
            % ("".join('<col style="width:%s">' % w for w in widths), head, body))


def render_section(spec, section, rows, context, style):
    sid = section.get("id") or "s"
    keep = [r for r in rows if matches(r, section.get("when"), context)]
    if not keep and section.get("hide_when_empty"):
        return ""
    out = ['<h2 class="sec">%s</h2>' % E(section.get("title") or "")]
    if not keep:
        out.append('<div class="sec-empty">%s</div>' % E(section.get("empty_words") or "Nothing here."))
        return "".join(out)
    out.append('<div data-section="%s">' % E(sid))
    if section.get("grouped") and spec.get("group_by"):
        buckets = {}
        for row in keep:
            name = str(row.get("context_group") or row.get(spec["group_by"]) or "Unassigned")
            buckets.setdefault(name, []).append(row)
        for name in sorted(buckets):
            gid = "%s-%s" % (sid, re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower())
            note = ((context.get("groups") or {}).get(name) or {})
            meta = []
            # In its own span: the filter rewrites it, and a head that says "2 rows" over one row is
            # a count the reader has no reason to distrust.
            meta.append('<span class="gcount" data-total="%d">%d row%s</span>'
                        % (len(buckets[name]), len(buckets[name]),
                           "" if len(buckets[name]) == 1 else "s"))
            if note.get("note"):
                token = note.get("level") or "quiet"
                meta.append('<span class="chip %s">%s</span>' % (E(token), E(str(note["note"]))))
            collapsed = bool(section.get("collapsed"))
            out.append('<button class="grp" data-group-head="%s" aria-expanded="%s">'
                       '<span class="caret">%s</span><span class="name">%s</span>'
                       '<span class="meta">%s</span></button>'
                       % (E(gid), "false" if collapsed else "true", "&#9656;" if collapsed else "&#9662;",
                          E(name), " &middot; ".join(meta)))
            out.append('<div data-group="%s"%s>%s</div>'
                       % (E(gid), ' style="display:none"' if collapsed else "",
                          render_table(spec, buckets[name], style, sid)))
    else:
        out.append('<div data-group="%s-flat">%s</div>'
                   % (E(sid), render_table(spec, keep, style, sid)))
    out.append('<div class="sec-empty sec-empty-filtered" hidden>Nothing in this section matches '
               'the filter.</div>')
    out.append("</div>")
    return "".join(out)


def build_page(spec, rows, context, as_of, title, source_label):
    style = spec.get("date_format") or "mm/dd/yy"
    rows = apply_context(rows, context, spec)

    # Pass one: the clock. Everything else on the page is drawn relative to it.
    for i, row in enumerate(rows):
        row["_as_of"] = as_of
        row["_flags"] = []
        row["_id"] = str(row.get("entity_key") or row.get("_file") or i)
        row["_sortname"] = str(row.get(spec.get("sort_name") or "display") or row.get("_file") or "")
        level, days, read_on = row_staleness(row, spec, as_of)
        row["_level"], row["_days"], row["_read_on"] = level, days, read_on
        if row.get("_no_note"):
            row["_level"], row["_days"], row["_read_on"] = "unknown", None, ""
        person_field = ((spec.get("counts") or {}).get("person_field")) or "needs_a_person"
        flag = row.get(person_field)
        row["_needs_person"] = bool(flag) and str(flag).lower() not in ("false", "no", "0")
        row["_search"] = " ".join(
            str(row.get(k) or "") for k in (spec.get("search_fields") or ["display"])).lower()

    # Pass two: draw the cells. Some of them raise a flag as they draw (a series that disagrees with
    # its own status word, an interval that has run out), so the tiles are counted AFTER this and
    # never before it.
    for row in rows:
        for col in spec.get("columns") or []:
            if not row.get("_no_note"):
                CELLS[col.get("type") or "text"](row, col, spec, style)

    # Pass three: the tiles, then the sections.
    tiles = []
    for tile in spec.get("tiles") or []:
        hits = [r for r in rows if matches(r, tile.get("when"), context)]
        for row in hits:
            row.setdefault("_tiles", []).append(tile.get("id"))
        tiles.append((tile, len(hits)))

    body = []
    for section in spec.get("sections") or [{"id": "all", "title": "Everything", "grouped": True}]:
        body.append(render_section(spec, section, rows, context, style))

    counts = spec.get("counts") or {}
    ready = [r for r in rows if not r["_needs_person"] and not r.get("_no_note")]
    stuck = [r for r in rows if r["_needs_person"] or r.get("_no_note")]
    reasons = {}
    for row in stuck:
        why = str(row.get(counts.get("person_field") or "needs_a_person") or "no note yet")
        if why.lower() in ("true", "yes"):
            why = "reason not recorded"
        reasons[why] = reasons.get(why, 0) + 1
    count_line = "<b>%d</b> %s" % (len(ready), E(counts.get("ready_label") or "on the board"))
    if stuck:
        count_line += ", <b>%d</b> %s (%s)" % (
            len(stuck), E(counts.get("person_label") or "need a person"),
            E(", ".join("%s x%d" % (k, v) for k, v in sorted(reasons.items()))))

    oldest = max([r["_days"] for r in rows if r["_days"] is not None] or [0])
    built = datetime.datetime.now().strftime("%H:%M")
    subhead = "Built %s from %d note%s in %s" % (built, len(rows) - len([r for r in rows if r.get("_no_note")]),
                                                 "" if len(rows) == 1 else "s", E(source_label))
    if oldest:
        subhead += " &middot; oldest %s %d days" % (E((spec.get("staleness") or {}).get("label") or "read"), oldest)

    tile_html = []
    labels = {}
    for tile, n in tiles:
        labels[tile.get("id")] = tile.get("label")
        tile_html.append('<button class="tile%s" data-tile="%s" aria-pressed="false"%s>'
                         '<span class="n">%d</span><span class="l">%s</span></button>'
                         % (" zero" if not n else "", E(tile.get("id") or ""),
                            ' disabled aria-disabled="true"' if not n else "", n, E(tile.get("label") or "")))

    drawers = {}
    for row in rows:
        if not row.get("_no_note"):
            drawers[row["_id"]] = drawer_html(row, spec, style)
    island = json.dumps({"drawers": drawers, "tileLabels": labels}).replace("<", "\\u003c")

    legend = list(spec.get("legend") or [])
    legend.append('<b>&mdash;</b> means we have not looked. "%s" means we looked and the record was '
                  "silent." % E(spec.get("absent_word") or "not documented"))

    head_title = title or spec.get("title") or "Board"
    page = TEMPLATE % {
        "title": E(head_title),
        "css": CSS,
        "js": JS,
        "head_line": E(head_title) + (" &middot; " + E(context["header"]) if context.get("header") else "") +
                     " &middot; " + E(_long_date(as_of)),
        "subhead": subhead,
        "counts": count_line,
        "banner": E(spec.get("banner") or ""),
        "tiles": "".join(tile_html),
        "body": "".join(body),
        "legend": "<br>".join(legend),
        "island": island,
        "footer": E(spec.get("footer") or ""),
    }
    return len(rows), page


def _long_date(iso):
    try:
        d = datetime.date.fromisoformat(iso)
    except ValueError:
        return iso
    return "%s %d %s %d" % (d.strftime("%A"), d.day, d.strftime("%B"), d.year)


TEMPLATE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:; script-src 'unsafe-inline'; form-action 'none'; base-uri 'none'">
<title>%(title)s</title>
<style>%(css)s</style>
</head><body>
<div class="wrap">
  <header>
    <h1>%(head_line)s</h1>
    <div class="sub-head">%(subhead)s</div>
    <div class="counts">%(counts)s</div>
  </header>
  <div class="banner">%(banner)s</div>
  <div class="tiles">%(tiles)s</div>
  <div class="bar">
    <input id="q" type="search" placeholder="search" aria-label="search this board">
    <span class="showing" id="showing">showing: all</span>
    <button id="reset" type="button">reset</button>
  </div>
  <div class="nomatch" id="nomatch" hidden></div>
  %(body)s
  <div class="legend">%(legend)s<br>%(footer)s</div>
</div>
<div class="scrim" id="scrim"></div>
<aside class="drawer" id="drawer" role="dialog" aria-modal="true" aria-hidden="true" aria-label="detail">
  <button class="close" id="drawer-close" type="button">close</button>
  <div id="drawer-body"></div>
</aside>
<script type="application/json" id="board-data">%(island)s</script>
<script>%(js)s</script>
</body></html>
"""


# --------------------------------------------------------------------- the command line

def write_out(path, text):
    """0700 on the folder, 0600 on the file, and never under a shared temp directory.

    A board is a rendering of whatever the notes hold, so it inherits their confidentiality without
    inheriting their folder. /tmp is world-readable on most boxes and is swept by things nobody
    watches, which makes it the one place this must not land.
    """
    full = os.path.abspath(path)
    if full.startswith("/tmp/") and not os.environ.get("ENTITY_BOARD_ALLOW_TMP"):
        raise EN.Refusal("bad-out",
                         "that output path is under /tmp, which is readable by every account on the "
                         "box; nothing was written. Give a path inside the workspace")
    folder = os.path.dirname(full) or "."
    os.makedirs(folder, mode=DIR_MODE, exist_ok=True)
    fd = os.open(full, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, FILE_MODE)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.chmod(full, FILE_MODE)
    return full


def main(argv=None):
    ap = argparse.ArgumentParser(add_help=True, description="render one board as one HTML file")
    ap.add_argument("--spec")
    ap.add_argument("--vault")
    ap.add_argument("--rows")
    ap.add_argument("--out")
    ap.add_argument("--context")
    ap.add_argument("--title")
    ap.add_argument("--as-of", dest="as_of")
    ap.add_argument("--source-label", dest="source_label")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--spec-version", action="store_true")
    args = ap.parse_args(argv)

    if args.spec_version:
        print(" ".join(str(v) for v in SPEC_VERSIONS))
        return 0
    here = os.path.dirname(os.path.abspath(__file__))
    if args.demo:
        args.spec = args.spec or os.path.join(here, "boards", "entities.board.json")
        args.vault = args.vault or os.path.join(here, "boards", "demo")
        args.out = args.out or os.path.join(os.getcwd(), "entities-board.html")
        args.as_of = args.as_of or "2026-09-08"
    try:
        if not (args.spec and args.out and (args.vault or args.rows)):
            raise EN.Refusal("usage", "board.py needs --spec, --out and one of --vault or --rows; "
                                      "nothing was written")
        spec = load_spec(args.spec)
        as_of = _iso(args.as_of) or EN.today()
        context = {}
        if args.context:
            with open(args.context, "r", encoding="utf-8") as fh:
                context = json.load(fh)
        as_of = _iso(context.get("as_of")) or as_of if not args.as_of else as_of
        rows, trouble = load_rows(args, spec)
        rows = [r for r in rows if keep_row(r, spec)]
        source = args.source_label or context.get("source_label") or (args.vault or args.rows)
        drawn, page = build_page(spec, rows, context, as_of, args.title, source)
        path = write_out(args.out, page)
    except EN.Refusal as exc:
        print("ERROR: %s" % exc.error)
        return 0
    except (OSError, TypeError, ValueError, KeyError) as exc:
        print("ERROR: the board was not written (%s: %s)" % (type(exc).__name__, exc))
        return 0
    note = "" if not trouble else " %d note(s) could not be read: %s." % (len(trouble), "; ".join(trouble))
    print("Wrote %s: %d row%s, as of %s.%s"
          % (path, drawn, "" if drawn == 1 else "s", as_of, note))
    return 0


if __name__ == "__main__":
    sys.exit(main())
