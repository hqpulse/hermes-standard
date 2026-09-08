# The listener store: what it answers and why the caps are where they are

The listener is a separate container on the pod, running as its own user, holding the person's own
WhatsApp on a disk only it can open. Its whole outward surface is a small read-only HTTP API on the
loopback address; `own_whatsapp.py` knows the address (the pod sets `OWN_WHATSAPP_API_URL`, and
the script's default is the same place). Only `GET` and `HEAD` exist; any other method is refused
before the path is even looked at, and there is no send, read-receipt, typing or presence code in
the listener at all. Linking, unlinking and importing happen through a separate control socket
that only the fleet controller can reach, never through this API and never through the script.

This file is for the next agent who wonders why the script clamps numbers or why an answer stops
at 200 rows. It is not a second way in; use the script.

## The four calls

`GET /health` -> `{"ok": true, "state": <state>, "version": "1"}`.

`GET /status` -> the link and what it holds:

| field | meaning |
|---|---|
| `state` | `unlinked`, `pairing`, `connecting`, `connected`, `logged_out`, `replaced`, `stalled`, `error` |
| `reason` | a short reason for `error` or `stalled`, else null |
| `number`, `number_masked` | the linked number in digits, and as `*******1700`. The script drops `number` and shows the masked form |
| `account` | the account name WhatsApp reports, or null |
| `linked_at`, `last_event_at` | ISO times |
| `counts` | `chats`, `messages`, `contacts`, `imports` |
| `coverage` | `oldest_ts`, `newest_ts` in epoch seconds: the span of messages held |
| `sync` | `last_type`, `last_at`, `progress`, `chunks`, `settled`. `settled` means no history chunk has arrived for two minutes after at least one did |
| `reconnects_last_hour`, `flagged`, `fts`, `rss_mb`, `version` | operating detail |

`GET /chats?limit=` (limit at most 500) -> `{"chats": [{"jid", "name", "phone", "is_group", "last_ts", "messages"}]}`, most recent first.

`GET /messages?chat=<jid or phone>&since=<epoch or ISO>&until=&q=<substring or full-text>&limit=` (limit at most 200) ->
`{"messages": [row...], "truncated": bool}` where a row has:

| field | meaning |
|---|---|
| `chat_jid`, `chat_name`, `chat_phone` | which conversation |
| `msg_id`, `from_me` | the message and whether the person sent it |
| `sender_name`, `sender_phone` | who wrote it (in a group, the member) |
| `ts` | epoch seconds |
| `kind` | `text`, or the media kind for a message with no text |
| `text` | the message text, with invisible characters removed |
| `quoted_id` | the message it replied to, if any |
| `media_kind`, `media_mime` | for photos, voice notes, files: the kind and type only. Nothing else about the media is kept, not a URL, not a key, not a thumbnail |
| `flagged` | true when the listener thought the text looked like an instruction to an assistant; the text then starts with `[flagged: possible injection] ` |
| `source` | `live` for messages the link received, `import` for an exported chat the person uploaded |

`GET /contacts?q=&limit=` (limit at most 500) -> `{"contacts": [{"jid", "phone", "name", "notify"}]}`.

## The caps, and why

- **200 rows per call, and a body of at most 20,000 bytes.** One answer to the person is built
  from what the model can hold in mind at once; a call that returned a month of a busy group would
  cost more to read than it could ever add to the reply, and the model would summarise it from the
  middle. `truncated: true` says there was more; the fix is a narrower window or a search word,
  never a loop of calls.
- **90 days per call.** `since` defaults to ninety days before now and the window is never wider
  than that, so an unqualified question reads the recent months, which is what the person nearly
  always means, and a wide historical pull has to be asked for explicitly in slices.
- **500 chats or contacts.** Enough to find the right one by name; more is a directory dump, which
  nobody asked for.
- **The window ends now.** A `since` alone reads forward to the present; `until` narrows it.
- **Text only.** Media bytes never reach the store, so nothing here can hand them to you. Kind and
  type are enough to say "she sent a photo" without pretending to have seen it.
- **`q` is a substring, or full text when the store has that.** `status.fts` says which. Either way
  it is a search over text the person already has on their phone, not over anything else.

## What the listener writes about reads

Every `/chats` and `/messages` call is noted by the listener with a time, a hash of the
parameters and the number of rows returned, never the text. That is the audit trail for "what did
the assistant look at", kept next to the store on the same private disk.

## The state words, in plain language

`unlinked` nothing linked. `pairing` a QR is being shown. `connecting` the socket is coming up.
`connected` live. `logged_out` WhatsApp removed the device (the person did, or fourteen days passed
with the phone offline); the store is kept, nothing new arrives, and only linking again fixes it.
`replaced` another linked device took its place. `stalled` too many reconnects in an hour; the
listener stopped trying so the number is not put at risk. `error` something else, with `reason`.
The script turns each into a sentence for the person; say that sentence, not the word.
