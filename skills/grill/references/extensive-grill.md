---
title: extensive-grill
type: note
permalink: dqverify-repo-20261013/skills/grill/references/extensive-grill
---

# Extensive Grill — full playbook

The `grill-me` skill is a relentless one-at-a-time interview over a single plan. **grill-me-extensive** scales that to *scoping a whole program or a wide, under-specified decision space*, and adds explicit grill MODES so you can grill into expansion, modification, scope-change, modernization, better-ideas, etc. — not just "answer the open questions in the plan I gave you."

Use it when the user says "grill me extensively", "scope this program", "suggest more / what else could this be", or hands you something big and fuzzy.

## The 7-step method

1. **SCOUT first.** Read the plan/codebase/prior art so questions are grounded, not generic. Pull prior decisions from memory/ledger. Never grill from zero on something you can investigate. If a question is answerable by reading, read instead of asking.

2. **DIVERGE — fan out to surface what the user did NOT ask for.** The biggest value of an extensive grill is options the user has not considered. Run a brainstorm fan-out: several agents, each a DISTINCT lens (e.g. power-user, feature-parity/competitive, depth, intelligence/optimization, infra/maintainability, UX, automation, distribution/safety) — each proposes concrete directions BEYOND the stated scope. Dedup and note cross-lens convergence (an idea raised by 2+ lenses independently is a strong signal). This is what makes "grill into expansion / better-ideas" real instead of you alone guessing.

3. **STRUCTURE into a categorized long decision list.** Synthesize the divergent material into grouped open decisions: scope-inclusion · sequencing · effort/ambition-ceiling · safety/ethics boundaries · legal/data-source · platform reach · process/maintenance. Each item = a crisp question + the options + the trade-off. Write it to a doc (it becomes the decision queue + the audit trail).

4. **FOUNDATION-FIRST.** Lead with the 1-2 framing questions that reframe everything downstream (audience/purpose, ambition envelope, the load-bearing "what is this ultimately FOR"). Their answer prunes or recolors half the later questions — ask them before the details.

5. **WALK ONE-AT-A-TIME.** One question per turn. Each carries YOUR recommended answer as the first option + the honest trade-off. Number them (e.g. "G-7 of 35") so the user feels progress. Let the user decide fresh; if they pick "Other" with a richer answer, absorb it (often it spawns a NEW direction — capture it immediately into the roadmap).

6. **CAPTURE each decision durably as you go.** Checkpoint answers in batches to the ledger / a decision-log section of the doc, so nothing is lost to compaction across a long grill.

7. **CONVERGE to a locked decision log.** When the list is exhausted, consolidate every answer into one authoritative "Resolved Decisions" section. That log is the input to the next gate (design/plan) or the build — the grill's deliverable is a *decided scope*, not just a conversation.

## Grill MODES

State which mode(s) you are running; combine freely.

| Mode | The question it relentlessly asks | When |
|---|---|---|
| **expansion** | "What ELSE could this become? what adjacent features, force-multipliers, whole directions are we missing?" | scoping a new program; "suggest more" |
| **modification** | "What should CHANGE here? what is wrong, stale, or mis-built in the existing design?" | reviewing an existing plan/system |
| **scope-change** | "Should this be bigger or smaller? split or merged? what is truly in vs out? where is the MVP boundary?" | scope feels wrong (bloated or too thin) |
| **modernization** | "Is this approach/stack/pattern CURRENT? what is the up-to-date best-practice version? what is legacy/deprecated?" | inherited or aging design; tech-refresh |
| **better-ideas** | "Is there a fundamentally BETTER approach? steelman 2-3 alternatives an expert would consider." | high-stakes design choice; avoid local optimum |
| **red-team** | "What BREAKS this? failure modes, unverified assumptions, safety/ethics/legal boundaries." | before committing; pairs with falsify-first / fresh-context-verify |
| **simplification** | "What can we CUT? gold-plating, the 80/20, the real MVP?" | over-scoped; deadline pressure |
| **prioritization** | "What ORDER? critical path, biggest unblocker, what to defer?" | many committed items, unclear sequence |

**Defaults:** "scope a new program" -> expansion + red-team. "review my existing plan" -> modification + better-ideas. "this feels too big" -> simplification + scope-change. "is this still the right way" -> modernization + better-ideas.

## Discipline notes (hard-won)

- **One question at a time is a strong user preference** — a wall of questions is worse than a slow walk. Recommend each answer; never rubber-stamp (EVPI-gate: only ask when the answer changes what you do).
- **Capture or lose it** — long grills outlive a context window; checkpoint decisions durably every few questions.
- **A grill is not a build** — converge to a *decision log*, then hand off to the gate/build. Do not start implementing mid-grill.
- **Ethics/safety modes need explicit ratification** — for dual-use work, make the boundary decisions (what is in/out) the user's explicit call, framed honestly, before any build touches them.

---
*Companion to the vendored `grill-me` skill (MIT, mattpocock/skills). This extension is original agent-skills-toolchain content (2026-06-16) — it does NOT modify the vendored skill, so the upstream auto-sync of grill-me cannot clobber it.*