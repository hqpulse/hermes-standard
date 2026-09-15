---
name: brain
version: 0.1.0
description: "Brain: the person's own knowledge base. Look someone up before you answer about them, instead of answering from memory."
triggers:
  - "a person, company, project or place becomes the subject of the exchange"
  - "about to state a detail about someone from memory"
  - "asked who someone is, or what was decided with them"
mutating: false
writes_pages: false
tools: [recall, entity, get_page, query, search, context_pack, get_backlinks, traverse_graph]
---

# The brain: look it up, do not guess

You have a second memory. It is reachable through the `brain` tool set and it holds
what the person actually said and heard, organized by who they said it to.

Your own memory files hold what you have learned about working with this person.
The brain holds the record. When the two disagree, the brain is the evidence.

## What is in it

- **One page per person** they talk to, at `wa/people/<name>`. It carries how many
  messages they have exchanged, over what span, who sent what, and the conversation
  itself in date order.
- **One page per group**, at `wa/groups/<name>`, including who talks in it and how often.
- **The address book**, at `wa/contacts/roster-NN`, every contact with their number
  and the name they show up under.
- Long conversations are split into parts, and the main page links to them.

## When to look something up

Look it up when any of these is true and you have not already opened the page:

- Someone is **the subject** of the message, or a decision about them is being made.
- You are about to **state a non-trivial detail** about someone: what they agreed to,
  what they are owed, where something stands. Check first. "Let me check" is always
  better than a confident wrong answer.
- A name comes up that you **do not recognize** and looks like it matters.
- The person asks anything shaped like "who is", "what did we decide with",
  "where did we land on", "have I heard back from".

Skip it for passing mentions and logistics. Look things up when it makes the answer
better, not out of reflex.

## What to pull, and when to stop

Go only as deep as the question needs.

1. `entity <name>` to confirm who someone is. Cheap and fast. Often enough.
2. `recall <question>` when you need the substance rather than the identity. This
   searches by meaning, so ask it the way the person asked you.
3. `get_page <slug>` when that person is the subject and the details matter.
4. `get_backlinks` or `traverse_graph` only when you need to know how people connect.

Pull the one or two names the question needs. Do not load the whole address book.

## How to talk about what you find

The person linked their own messages on purpose, so knowing them is expected and you
never need to be coy about it. But answer like someone who remembers, not like someone
reading a file out loud. Give the answer and the detail that matters. Do not recite
slugs, page names, message counts or scores, and do not explain how you looked it up.

If the brain does not have it, say so plainly and do not fill the gap with a guess.

## The failure this exists to prevent

Answering generically about someone whose whole history is sitting in a page you did
not open. If you have been discussing a named person for more than a message and have
not looked them up, look them up now.
