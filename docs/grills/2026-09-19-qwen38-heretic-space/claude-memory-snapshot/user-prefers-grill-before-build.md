---
name: user-prefers-grill-before-build
description: "For wide or fuzzy work the user wants an extensive one-question-at-a-time grill before any fixing, even when production is broken"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ca9aa7a4-16ad-4e9d-bafe-00eed0171063
  modified: 2026-09-19T00:11:53.881Z
---

On 2026-09-19 the user first said "refetch latest version … and start fixing it", interrupted themselves, and replaced it with
"or rather /grill-me-extensive". For large or under-specified work, run the `grill-me-extensive` skill first: scout, fan out distinct
lenses, write a categorized decision queue to a doc, then ask ONE question per turn with a recommended answer and the trade-off,
recording each decision as it lands. Do not implement mid-grill.

**Why:** the user runs several AI agents against the same targets and had just watched one push broken, over-claimed commits straight
to production; they want decisions made deliberately and recorded before anything else is changed.
**How to apply:** when a request is big/fuzzy or touches something another agent is also changing, propose or start the grill rather
than diving into edits; keep questions EVPI-gated (investigate what can be looked up instead of asking).

Related: [[qwen38-heretic-space-grill]], [[toolchain-skills-not-registered-here]]
