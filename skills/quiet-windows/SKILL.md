---
name: quiet-windows
description: "Quiet windows: the hours a person is not to be messaged by a scheduled job. Evenings, weekends, days off, personal hours. Record one the moment the person states it; read them before anything unprompted."
---

# Quiet windows

Some hours are not for messages from you. A person says so once, in passing ("not before nine", "I'm off Thursday and Friday", "never on a Sunday"), and expects it kept from then on. This skill is how it is kept: the hours go into a file that the same gate reads before every scheduled job, so nothing unprompted reaches them inside one. You never work out a quiet hour yourself, and you never guess one.

## The command

    quiet-windows list
    quiet-windows add weekly sat,sun 00:00 24:00 weekend
    quiet-windows add weekly mon-fri 19:00 08:00 evenings
    quiet-windows add dates 2026-11-26 2026-11-27 days off
    quiet-windows remove w-3f9a1c

`quiet-windows` means `${HERMES_SKILL_DIR}/scripts/quiet-windows`, the file `scripts/quiet-windows` inside this skill's own folder. Run it with the terminal tool. Times are the person's own clock; a weekly window whose end is earlier than its start runs overnight. A dates window covers whole days, both ends included.

## When to write one

- The person states a quiet hour, a day off, or a standing rule about when not to be messaged. Write it in the same turn, then say in one line what you kept: "Kept: nothing from me before 9am on weekdays." Never ask them to confirm a rule they just stated.
- The person says a window is over, or changes it: remove or replace it the same way, and say so in one line.
- Only what they said. A holiday you assume, an evening you infer from when they go quiet, a weekend nobody mentioned: not yours to write.

## When to read them

Before anything unprompted: a reminder, a notice, a nudge, a scheduled job's output. Their scheduled jobs are held shut inside a window by the gate itself, before you are woken. If you nonetheless find yourself running a scheduled job inside one, your whole answer is exactly `[SILENT]`.

Nothing flushes when a window opens. What waited becomes one message at the next ordinary moment, usually the morning brief, never a burst at the end of the evening.

Inside a conversation they started, you answer. If they write to you inside their own quiet hours, that is their choice; answer as asked and add nothing of your own.

## What it is not

It does not touch what you do when asked, and it does not narrate itself. Never say "since you are in quiet hours" or "as per your window"; the right moment is kept by being absent at the wrong one. A person who keeps an observance calendar has one of their own beside this; both hold, and neither is mentioned to them.
