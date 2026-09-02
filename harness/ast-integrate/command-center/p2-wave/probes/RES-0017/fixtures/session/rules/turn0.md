# turn-0 rule

Always-on rule text is injected at turn 0. Unique marker: RES0017-RULE-TURN0

Occupancy accounting:
- Use the client's injected snapshot (tokenizer on concatenated classes).
- Do not use tokens_cumulative as the occupancy numerator.
- Do not infer occupancy from file sizes of ~/.claude/rules plus unused files.

Disabled rules in this session directory must not appear in the injection set.
