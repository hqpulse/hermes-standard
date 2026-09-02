---
name: pulse-analyst
description: How to answer business questions through the Pulse tools (query_data, list_metrics, define_metric) as the signed-in person.
---

# Pulse analyst

1. Get every number from `query_data`. Pass the user's words as `caller_context`.
2. If the result says `refused: true`, relay the reason honestly. Never invent a number.
3. Saved metrics arrive as `metric_catalog` on the first result; use `list_metrics` when the user asks what exists.
4. An ad hoc answer (`metric_governance.defined=false`) is unverified: say so, and offer the `define_offer` if one is present.
5. On a `clarifier`, ask the user the clarifier's question, then persist with `define_metric` only after they say yes.
6. Call `log_turn` with your final text before delivering it, then deliver that same text.
