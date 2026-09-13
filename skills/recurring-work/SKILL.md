---
name: recurring-work
description: When a person asks for work on a clock (a report, a summary, a check, every day or every week) or asks to stop one. Tells a run apart from a reminder and files it through Pulse.
---

# Recurring work

A person says "every Monday at 7, pull last week's admissions and discharges for all buildings and summarize them against budget." That is not a reminder. It is work you do on a clock, and it is filed in Pulse with the `recurring_work` tool, never with your own cron job tool. This skill is how you tell the two apart, how you say the job back before you file it, and what you say when a job cannot run on a clock.

## Run or reminder

Ask one question of the request: before anything is said, does the job have to read, look up, count, compare or compute something?

- **No.** It is a reminder: a nudge to the person at a time ("remind me at 3 to call the DON", "ping me Monday mornings to submit timesheets"). The assistant-standard skill has the rules; it is your cron job tool, it delivers to their phone, and it is done at rung 2, say so in one line.
- **Yes.** It is recurring work: a report, a summary, a brief, a check, a comparison, a list pulled from the data. It goes through `recurring_work`. A run you make with your own cron job tool has nobody watching it and no gate in front of it, so a person's recurring work is never one of those, however natural it feels.

"Send me a summary every morning" is work: the summary has to be built before anything is sent, and the sending is the answer landing where the run puts it, not a message you send. "Remind me every morning to read the summary" is a reminder.

## What a scheduled run is, in their words

A run wakes on its clock, reads what the job says, and writes its answer into a conversation of its own on the agent's page, under Recurring work. The run has no memory of the chat it was made in: the one fixed prompt is all it knows. It only reads. It can look anything up that you can look up for them in a conversation; it cannot send mail or messages, post anywhere, save or file anything, book or change anything. It runs at most once an hour, and an agent carries at most five.

When a person asks where the result goes, say that: on the agent's page under Recurring work, as a conversation of its own, and that you can read it to them when they ask.

## How to file one

1. **Read what they said before you ask anything.** The day, the time and what to produce are usually all there. Their time zone is the one you run on unless they name another. Ask at most one question, and only when the request truly cannot be filed without it. Never ask for something they already said.
2. **Write the prompt as a complete instruction to a future run that knows nothing about this chat.** Name the buildings, the period, the comparison and the shape of the answer. "The report we discussed" is a prompt that fails at seven on Monday.
3. **Call `recurring_work` with `action=add`, a short title, the schedule as five cron fields, the time zone, the prompt, and no confirm.** Nothing is filed. The tool hands back the one line to say: the schedule in words, the zone, and the prompt.
4. **Say that line back to the person, in one line, and wait.** "Every Monday at 7:00 AM Eastern: pull last week's admissions and discharges for all buildings and summarize them against budget. Set it up?" If they change the time or the wording, say the new line back before you file.
5. **On their yes, call again with the same arguments and `confirm=true`.** Their own direct instruction, once the line has been said back, is the yes. Then say it is set up and where it shows, in one line. Nothing is set up unless the tool said so and you saw the result.

The cron line: minute, hour, day of month, month, weekday. The minute is a number, never a star, so nothing runs more than once an hour. `0 7 * * 1` is Mondays at 7:00. `0 7 * * 1-5` is weekdays at 7:00. `30 17 * * *` is every day at 5:30 PM. `0 8 * * 1,4` is Mondays and Thursdays at 8:00.

## When the job would send or change something

The tool refuses a prompt that plainly asks to send, post, publish, save, file, book or change something, and gives you the sentence to say. Say it in your own words, in one line, and never as an apology: a scheduled run only reads and looks things up; the part that sends or changes something stays with them, or with the people who set you up. Then offer the reading half as the schedule. "I can pull the numbers every Monday at 7 and have them ready on your agent's page. Sending them to the team is yours to do when you have read them. Set up the Monday pull?" The person may take the half or leave it.

Never promise to send the result to anyone. Never file the job with the send left out quietly and let them find out on Monday.

## Stopping and listing

"Stop the Monday report", "what do you run on your own", "cancel the daily summary":

1. Call `recurring_work` with `action=list`. Each row says what it is, when it runs, whether it ran, and whether it can be removed from a chat.
2. Name the one they mean, in one line, and ask: "Remove Monday census, Mondays 7:00 AM Eastern?" If two rows could be the one, name both and ask which; never guess, never remove both.
3. On their yes, call again with `action=remove`, the row's name and `confirm=true`. Say it is removed only when the tool said so.

A row that says it was set up by hand cannot be removed from a chat. Say so in one line and that the people who set you up can take it off. Do not offer to try another way.

## What not to do

- Never use your own cron job tool for work a person wants on a clock, even once, even for a test.
- Never file without saying the line back and getting the yes. Never change a filed job's time or words without saying the new line back first.
- Never say a job is set up, changed or stopped unless the tool said so and you saw the result.
- Never describe a run as something that sends, posts or delivers to other people.
