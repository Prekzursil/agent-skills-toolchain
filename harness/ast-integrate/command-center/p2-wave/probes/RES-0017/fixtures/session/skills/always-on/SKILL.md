---
name: always-on-fixture
description: Turn-0 injected skill with no paths key.
---

# always-on-fixture

This skill is injected at turn 0 because its frontmatter has no `paths` key.
The client listing may mention other skills; only this body is occupancy.

Measurement rules for RES-0017:
- Count the injected payload with the pinned tokenizer, not directory file sizes.
- Occupancy is the turn-0 snapshot, never tokens_cumulative.
- Ablate one class and re-measure the concatenated prompt.

Unique marker: RES0017-ALWAYS-ON-SKILL-BODY
