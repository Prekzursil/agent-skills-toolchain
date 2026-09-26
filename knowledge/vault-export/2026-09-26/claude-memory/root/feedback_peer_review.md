---
name: feedback-peer-review
description: ALWAYS get 1-2 independent agent reviews on every idea/design AND every
  implementation before treating it done — never self-certify; use codex-review +
  Claude reviewers, scale to multi-agent council for big calls
metadata:
  node_type: memory
  type: feedback
  originSessionId: 5cba01b0-b7c2-4f65-96a6-d44199963f4c
permalink: main/claude-memory/root/feedback-peer-review
---

Never self-certify. Every **idea/design** and every **implementation** gets **at least 1-2 independent agent reviews** before it's treated as correct/"perfect." Independent eyes (especially cross-model) catch what the author cannot see.

**Why:** User instruction 2026-05-28 (BC trainer-GUI work): "always have 1-2 other agents review the ideas or implementations, so that you make sure everything is perfect — all forms of /codex-review or even claude if needed or perhaps even coordination and councillation." Pairs with [[feedback-full-rigor]]. Proven the same session: a Codex review caught an over-confident "36xxx is banned" claim in the audit; the 5-agent design gate + Codex surfaced two security BLOCKERs and a date-dependent cache bug that self-review missed.

**How to apply (scale the review to the stakes):**
- **Designs/specs** → multi-agent design-review gate (e.g. PM/Architect/Designer/Security/CTO) **plus** a Codex adversarial pass. Reconcile ALL findings before proceeding.
- **Plans** → plan-review gate (Feasibility / Completeness / Scope) — all must pass.
- **Implementations / work units** → ≥1 independent code review (Claude `code-reviewer`/`security-reviewer` or a `/codex-review`) BEFORE commit; cross-model (Codex + Claude) when feasible — different models catch different bugs.
- **Big/architectural calls** → escalate to coordination/council (the [[model-council]], codex-coordinate/codex-governance).
- Prefer cross-model review (Codex + Claude) over two same-model passes. Treat "I reviewed it myself" as insufficient.