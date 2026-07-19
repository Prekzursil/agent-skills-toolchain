---
name: grill-me-extensive
description: Program-scale extensive grilling — an addon to the grill-me skill for wide or under-specified decision spaces. Scout context, fan out a brainstorm to surface directions beyond the stated ask, structure a categorized decision list, lead with foundational framing questions, then walk one question at a time with a recommendation each and capture every decision durably. Includes grill modes for expansion, modification, scope-change, modernization, better-ideas, red-team, simplification, and prioritization. Use when scoping a program, when the user says "grill me extensively" or "suggest more", or when grill-me alone is too small for the decision space.
---

This is the heavy-duty companion to the `grill-me` skill. Use plain `grill-me` for a single plan; use THIS when the user wants to scope a whole program, asks you to grill "extensively", asks "what else could this be / suggest more", or hands you something big and fuzzy. The full playbook is in `references/extensive-grill.md` — read it. The essentials:

## The 7-step method
1. **SCOUT** — read the plan/code/prior art + recall memory first; questions must be grounded, not generic. If a question is answerable by investigating, investigate instead of asking.
2. **DIVERGE** — fan out a brainstorm (several agents, each a DISTINCT lens) to surface directions BEYOND the stated ask; dedup + note cross-lens convergence. This is what makes "grill into expansion / better-ideas" real instead of you guessing alone.
3. **STRUCTURE** — synthesize into a categorized long decision list (scope · sequencing · effort · safety/ethics · legal · platform · process); write it to a doc as the decision queue + audit trail.
4. **FOUNDATION-FIRST** — lead with the 1-2 framing questions (audience/purpose/ambition) that reframe everything downstream; ask them before the details.
5. **ONE AT A TIME** — one question per turn, each with YOUR recommended answer + the trade-off; number them (e.g. "G-7 of 35") for progress. Never dump a batch. Absorb richer "Other" answers (they often spawn a NEW direction — capture it on the spot).
6. **CAPTURE** — checkpoint each decision durably (ledger/doc) as you go, in batches, so nothing is lost to compaction.
7. **CONVERGE** — consolidate every answer into one authoritative decision log; that log is the grill's deliverable and the input to the next gate/build. A grill is not a build — do not start implementing mid-grill.

## Grill MODES (state which you are running; combine freely)
- **expansion** — push scope OUTWARD: what else could this become, what adjacent/force-multiplier directions are missing?
- **modification** — interrogate an existing design: what should change, what assumptions are stale, what is wrong?
- **scope-change** — challenge the boundaries: bigger/smaller, split/merge, in-vs-out, MVP-vs-everything?
- **modernization** — is the approach/stack/pattern current best-practice, or legacy/deprecated? what is the up-to-date version?
- **better-ideas** — adversarially steelman 2-3 alternatives an expert would consider; avoid the local optimum.
- **red-team** — what breaks this: failure modes, unverified assumptions, safety/ethics/legal boundaries? (pairs with falsify-first / fresh-context-verify)
- **simplification** — what can be cut: gold-plating, the 80/20, the real MVP?
- **prioritization** — what order: critical path, biggest unblocker, what to defer?

**Defaults:** "scope a new program" -> expansion + red-team. "review my existing plan" -> modification + better-ideas. "this feels too big" -> simplification + scope-change. "is this still the right way" -> modernization + better-ideas.

## Discipline (hard-won)
- One question at a time is a strong user preference; recommend each answer; EVPI-gate (only ask when the answer changes what you do).
- Capture or lose it; long grills outlive a context window.
- For dual-use work, make the ethics/safety boundary decisions the user's explicit call, framed honestly, before any build touches them.
