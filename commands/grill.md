---
description: Stress-test a plan or program by resolving its open decisions, grounded in prior decisions.
---

# Grill

Load and follow the canonical skill at `~/.agents/skills/grill/SKILL.md`.
Use the shared behavior contract at `.agents/workflows/grill.yaml`.

Apply it to `$ARGUMENTS`.

Pick a depth and say which: **quick** for one plan, **program** for a wide or
under-specified scope (then also read `references/extensive-grill.md`).

Ground in basic-memory and the event ledger before asking anything. Investigate
discoverable facts instead of asking. Ask a whole dependency tier at once, each
option carrying variants ranked best/most-viable/worst, your recommendation, and
the upsides and downsides of each. Record every decision as it lands. Converge
with no silent drops: every question answered or deferred with an owner into
`knowledge/OPEN-LOOPS.md`. Do not implement while the grill is active.
