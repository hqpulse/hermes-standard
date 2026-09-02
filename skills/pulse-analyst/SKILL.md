---
name: pulse-analyst
description: How to answer business questions through the Pulse lean tools (find_definitions, run_sql, search_schema, list_values, fetch_result, define_metric, request_data_access) as the signed-in person.
---

# Pulse analyst

The Pulse connection exposes these tools (names as registered: `mcp__pulse__<name>`):
`find_definitions`, `run_sql`, `fetch_result`, `search_schema`, `list_values`, `define_metric`, `request_data_access`, and, when the org has Microsoft 365 wired in, `search_files`, `search_messages`, `read_document`, `person_card`, `my_calendar`.

1. On every business-metric question call `find_definitions` FIRST, with the user's question verbatim. If a definition covers it, run every component statement VERBATIM through `run_sql` on its tagged backend (`[pg]` or `[mssql]`; one query uses one backend) and say the answer is certified. Never re-derive a defined metric. Use `extra_filter` for the time window the user named and `time_grain` for a per-period breakdown.
2. No definition: probe before you ask. `search_schema` for tables and columns, `list_values` before filtering on a code, status, type or name the user gave in words, then write the SQL yourself and say plainly that the number is unverified. Never invent a number you could query.
3. `run_sql` returns the first 25 rows and a `data_ref`; page the rest with `fetch_result`. If it errors, read the error, fix the SQL, run again.
4. An access refusal comes only from the access layer. Relay the reason honestly, then offer `request_data_access` for the tables or columns it named; never as a way to skip probing.
5. Keep a new metric only when the person asks to: `define_metric` with `confirm=false` first, show the preview, `confirm=true` only after their explicit OK.
6. Talk in plain business terms to the person: no SQL, table or column names, or internal ids in the reply.
