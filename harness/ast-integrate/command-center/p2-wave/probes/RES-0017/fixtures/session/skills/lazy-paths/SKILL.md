---
name: lazy-paths-fixture
description: Full body must not enter turn-0 occupancy; only a catalog stub may.
paths:
  - "**/*.lazy-trigger"
---

# lazy-paths-fixture

This SKILL.md is in the skills tree so a file-size census would count it.
Turn-0 injection must NOT include this body because `paths:` makes it lazy.

Unique marker: RES0017-LAZY-SKILL-BODY-NOT-TURN0

Padding so tree_bytes >> injected stub bytes. The following paragraphs are
inventory only. They would dominate a naive `find | wc -c` of ~/.claude/skills
and that is exactly the rejected occupancy numerator.

Lorem measurement padding one. Context window occupancy is not the sum of
every file under the skill directory. Lazy skills load on a matching path
touch. If this paragraph appears in the turn-0 concatenated prompt, the
injector is broken.

Lorem measurement padding two. A second independent signal is UTF-8 byte
length of the injected payload, taken with wc -c on the rendered class
blocks, not on the whole tree.

Lorem measurement padding three. Cumulative token totals from later turns
must not be used as the occupancy numerator. That confusion already cost
one wrong restart.

Lorem measurement padding four. MCP server source and this lazy body stay
out of turn-0. Tool schemas and always-on rules stay in.

Lorem measurement padding five. Repeat distinctive tokens: lazy-not-injected
lazy-not-injected lazy-not-injected lazy-not-injected lazy-not-injected.

Lorem measurement padding six. More unused inventory so the skills tree is
larger than the injected skills class: alpha beta gamma delta epsilon zeta
eta theta iota kappa lambda mu nu xi omicron pi rho sigma tau.

Lorem measurement padding seven. Keep going so bytes_div4 of the tree cannot
accidentally equal the tokenizer count of the injected stub.

Lorem measurement padding eight. If a probe finds RES0017-LAZY-SKILL-BODY-NOT-TURN0
inside occupancy text, fail hard.
