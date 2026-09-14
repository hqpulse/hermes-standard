---
name: jewish-time
description: "Jewish time: Shabbat, yom tov, fasts and chol hamoed for a person who keeps them. When to be silent, when to come back, what kind of day it is."
---

# Jewish time

Some people keep Shabbat and yom tov. For them, when you speak matters as much as what you say. A message inside Shabbat is an offense they will remember; an hour late costs nothing.

This skill is the rules. Their times are their own, kept in a calendar built for where they live, and you read them with one command. You never work out a time yourself, and you never guess one.

## First, do they keep it

    jewish-time now

`jewish-time` below means `${HERMES_SKILL_DIR}/scripts/jewish-time`: the file `scripts/jewish-time` inside this skill's own folder, the `skill_dir` the skill viewer names. Run it with the terminal tool.

If it says no calendar is kept for this person, this skill does not apply to them: put it down and never raise the subject. Otherwise it tells you where they are right now: inside a quiet window or not, what kind of day today is, when the next window begins, and, on the first morning back, the last day they were working.

For a date ahead, before you put a time or a day in front of them:

    jewish-time on 2026-12-18

## The gate

1. Nothing unprompted goes to them inside a quiet window. Not a reminder, not a notice, not a job's output, not something you thought of yourself.
2. A quiet window runs from forty minutes before candle lighting to seventy two minutes after sunset, and the calendar already holds both ends. A printed calendar shows an earlier end. Do not use it.
3. A yom tov that touches Shabbat leaves no gap: Friday afternoon to Sunday night is one window.
4. Nothing flushes when a window opens. What waited becomes one message the next working morning, never six at nine at night. Usually that one message is the morning brief.
5. Their scheduled jobs are held shut inside a window by the calendar itself, before you are ever woken. If you nonetheless find yourself running a scheduled job inside one, your whole answer is exactly `[SILENT]`.
6. If the calendar says it does not cover today, timing is unknown: say nothing about timing, and treat Friday from noon to the end of Saturday as quiet.
7. Never explain any of it to them. Knowing the time means being absent at the right moment, not narrating it.

Inside a conversation they started, you answer. If they write to you inside a window, that is their choice; answer as asked and add nothing of your own.

## What kind of day it is

- **Full yom tov** is the same as Shabbat: a quiet window. Yom Kippur, the first and last days of Sukkot and Pesach, Shavuot, Rosh Hashana. No US calendar flags any of them, and six a year fall on a weekday where a weekday job fires straight into them.
- **Chol hamoed** is a working week that is not one. Message them, expect half days and people out, and ask for no big decision. A dip in anything on those days is not a problem.
- **A fast day**: they have not eaten since before dawn. Shorter than usual, nothing about food or coffee, nothing heavy in the afternoon, and not a word about the fast.
- **Erev Pesach** is the most compressed day of their year, and **Tisha B'Av** the heaviest. On both, routine scheduled messages stay silent; only something that truly cannot wait, and never a voice note.
- **Chanukah** is a normal working day with a family evening. **Purim** is a working day on paper and gone in practice. **The Nine Days** are subdued: no celebratory framing, no music in a voice note.

The command names today's kind for you. Follow it; do not announce it.

## Going in, and coming back

**Thursday is when you help, not Friday.** In winter the week is over by Friday lunchtime, so anything that needs them on a Friday needs them that morning. Friday morning is the last real window, and it is one message, not a trickle.

**One line before it starts, at most.** Only if a live item of theirs will sit unanswered until the window ends: what it is, and that it will keep, about ninety minutes before quiet begins. Otherwise silence, which is correct. Never "Shabbat is starting soon", never Good Shabbos from a scheduled job. If they say it first, answer warmly and stop.

**Before a three-day window they are gone for three days.** That is worth one line on the day before, naming the day they are back, once. Erev Pesach and erev Yom Kippur get nothing at all.

**Coming back, look back far enough.** The first morning after a window, the brief looks back to their last working day, not to yesterday: after a Shabbat that is Friday, after a long yom tov it can be three or four days. The oldest thing that is genuinely theirs outranks anything on today's calendar. Present what they have to answer, never the backlog.

**Sunday** is a working day for something that cannot wait, never for a routine brief.

## The traps

- Shabbat is not Saturday. A Friday 5pm message in December lands after candle lighting, and a Saturday 8am one is deep inside it.
- A fixed cutoff is wrong most of the year. Candle lighting moves by four hours between June and December, and jumps twice for daylight saving.
- Israel keeps one day of yom tov and a different candle time. The diaspora keeps two. Their calendar is the diaspora one, built for where they live.
- A voice note into a fast day, the Nine Days, or the minutes after Shabbat ends is intrusive in a way text is not.
- A date past the end of their calendar is not an ordinary day. It is an unknown one.
