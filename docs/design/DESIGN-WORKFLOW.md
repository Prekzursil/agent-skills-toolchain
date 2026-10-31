---
title: DESIGN-WORKFLOW
type: note
permalink: dqverify-repo-20261013/docs/design/design-workflow
---

# The TCR Loop — a Systematic, Named Design-Review + Code↔Figma Workflow

**Synthesized:** 2026-06-30 from the 9 design-research lens digests in this folder.
**For:** code-first power-user iterating Reframe, momentstudio, WebCoder, bilbo.
**The motion you asked for** — *transpose → discuss → revert* — is the spine of this loop (gates G2 → G3 → G6).

**Honesty note (adversarial):** the *building-block methods* are canonical and primary-sourced (Nielsen's 10 heuristics, NN/g heuristic-evaluation + design-critique rituals, CDS-30 question bank, severity 0–4, Figma branching/Dev Mode/Code Connect, W3C DTCG tokens). The *8-gate packaging and the "TCR" name are a synthesis* — there is **no single industry-blessed "design-review loop" name**; the SOTA is the *assembly* of named primitives, not a vendor product. 7 of 9 digests independently converged on the same phase skeleton (capture → audit → transpose → critique → iterate → apply-back → verify); the digests called it TCR / SATRA / Reconciliation Loop / 6-Gate / P0–P5 — all the same shape. This doc picks **TCR** (Transpose · Critique · Reconcile) because those three verbs *are* your "transpose → discuss → revert."

---

## 0. The headline — the 8 named gates

> **G0 PRIME → G1 AUDIT → G2 TRANSPOSE → G3 CRITIQUE → G4 DIRECT → G5 ITERATE → G6 RECONCILE → G7 VERIFY → (back to G1)**

- **Transpose edge** = G2 (and the G6 return capture).
- **Discuss edge** = G3 (+ G4 decide).
- **Revert edge** = G6 (the revert-gate: every apply-back is a reversible commit; revert if any tracked axis regresses).

Run cheaply-automatable gates (G1 audit, G7 verify) continuously; run G3 critique per feature; run G5–G6 per approved change-set. Cadence borrowed from NN/g's 1-hour-critique rhythm — **narrow scope per pass, don't boil the ocean.**

| Gate | Name | Named method (canonical) | Tooling | Emits |
|---|---|---|---|---|
| **G0** | **PRIME** | scope-setting; source-of-truth decision | `prime` / `design-system` skill; repo read | scope + persona + "where is truth: repo or Figma?" |
| **G1** | **AUDIT** | NN/g Heuristic Evaluation (Prepare→Evaluate→Consolidate); Nielsen 10 + severity 0–4 | `ui-audit` (Track-A numbers + Track-B VLM); Playwright/Chrome DevTools; UX-Ray/Stark/axe in Figma | severity-ranked, de-duped findings list |
| **G2** | **TRANSPOSE** | code→Figma capture ("Code to Canvas") | Figma MCP `generate_figma_design` (live/localhost→editable frames); `story.to.design` (Storybook→real components); `html.to.design` (audit record only) | editable Figma frames carrying Code Connect IDs + token refs |
| **G3** | **CRITIQUE** | NN/g Design Critique + CDS-30 + "I Like / I Wish / What If"; optional multi-agent critique panel | Figma comments; named-persona reviewer agents | typed, severity-rated verdict list |
| **G4** | **DIRECT** | severity-prioritized decision; define "good" (Judge/Evaluate/Iterate) | Impact/Effort or RICE | one committed direction + explicit out-of-scope |
| **G5** | **ITERATE** | Figma **branch** (the safe iterate-then-revert mechanism) | `use_figma`; Tokens Studio for token changes | Figma node-diff + token-diff on a branch |
| **G6** | **RECONCILE** | Dev Mode handoff + **Code Connect**; token PR; **revert-gate** | `get_design_context`/`get_variable_defs` → Claude Code; `figma-implement-design`; Style Dictionary | code diff on a branch — kept only if it passes |
| **G7** | **VERIFY** | re-audit delta; capture learnings | re-run G1; `/self-reflect` + basic-memory | before/after rubric delta + durable decisions |

---

## 1. The single load-bearing truth: the round-trip is LOSSY

Every digest agrees (confidence HIGH): **"code → Figma → code" is not byte-preserving.**
- `generate_figma_design` does **not** convert code to Figma directly — it spins your dev server, renders in a browser, and **serializes the rendered DOM**. The loop is *render-mediated*.
- Design→code: visual structure transfers; **business logic, state, API calls do NOT.** Code→design: rendering captures; **React state, routing, integrations vanish.**
- The **only** things that round-trip cleanly: **W3C DTCG design tokens** (Tokens Studio ⇄ Git ⇄ Style Dictionary) and **Code-Connected components** (the agent emits *your* `<Button>`, not a re-derived div).

**Consequence — why "revert" is a first-class gate (G6):** treat every apply-back as a **reversible commit on a branch**; diff for logic regressions; **keep only the visual delta, revert anything that re-touched state/routing/data.** Figma is the source of truth for *visual* decisions only.

---

## 2. The gates in detail — what you do + the standard design-questions

### G0 — PRIME (scope + source-of-truth)
Read the repo; locate the component library / Storybook / token source. Decide **loop altitude**: *system loop* (has components + tokens → bind to them) vs *audit loop* (greenfield → extract tokens manually first). The lens **rewards maturity; it does not manufacture it** — a greenfield app with no kit has nothing for Code Connect / tokens to bind to.
**Standard questions:** Who is the user and what is the top job in this flow? Where is the source of truth — **repo or Figma library**? Which one flow is in scope this pass?

### G1 — AUDIT (find problems, objectively)
Drive the running app; capture state. Run `ui-audit` Track-A (deterministic: contrast, spacing-on-scale, tap-targets, dead buttons, visual-regression) + a **VLM critique pass** (Track-B) scoped to where VLMs are *strong* — visual/aesthetic/consistency (Nielsen H2/H8). You + app-driving own *flow/state/interaction* (H3/H6/H7) where VLMs are weak. **VLMs are a recall amplifier, not a judge** (published: GPT-4o ≈21% overlap with experts, ~24% false-positive rate; near-random at *picking* the better design — WiserUI-Bench). De-dup, then **severity-rate 0–4** (Nielsen: 0 not-a-problem … 4 catastrophe; severity = frequency × impact × persistence).
**Standard questions (the Nielsen-10 checklist as yes/no gates):** system-status feedback? match to real world? user control/undo/exit? consistency & standards? error prevention? recognition over recall? flexibility for power users? aesthetic/minimalist? error recovery? help/docs? **+ a11y gate** (AA contrast, focus order, ≥44px targets, alt text) **+ token gate** (every value bound to a token, no raw hex)? What does each violation cost → severity? Functional-broken vs merely sub-optimal?

### G2 — TRANSPOSE (code → Figma) — *the first transpose edge*
Lift the running UI onto the canvas so you audit/discuss **reality, not a stale design file**. Pick the right altitude (this is the key insight from the wildcard lens):
- **System loop:** `story.to.design` (Storybook → *real* Figma components + variants, low drift) — what lands in Figma **is** your component graph.
- **Live UI:** Figma MCP `generate_figma_design` (live/staging/**localhost** → semantic editable frames, medium drift). Works behind auth via the capture path.
- **Audit record only:** `html.to.design` browser-extension capture (DOM-accurate, handles auth/private/localhost) — fine to *look at*, **wrong for the system loop** (screenshot importers cause design-system drift the moment Figma naming diverges from code).
**Standard questions:** Does the imported frame match the live render (fonts/spacing/**real states** — empty/error/loading too)? Which screens *carry the experience* (focus there)? Do nodes carry Code Connect IDs + token refs (system loop) or are they flat layers (audit only)?

### G3 — CRITIQUE (discuss) — *the discuss edge*
Structured critique on the transposed frames — **not bikeshedding**. Use the NN/g Design-Critique ritual (Preparation → Conducting → Post-processing) with **silent individual feedback first** (kills loudest-voice/HiPPO capture), round-robin or **quota** (force "2 wins + 1 fix" per screen — your anti-tunnel-vision law, works even solo). **The signature move: ask "why?"** on every reactive opinion — every comment ties to a persona/scenario/goal. Optionally run a **multi-agent critique panel** of named heuristic personas (Nielsen-evaluator / Refactoring-UI-evaluator / WCAG-evaluator / Brand-consistency-evaluator) each emitting a typed verdict — academically supported as *triage*, **not** an oracle (MLLM-as-UI-judge / ReLook). **The human stays the decider at the gate.**
**Standard questions — three banks combined:**
- **Framing (always):** What problem are we solving? Who is the user? What are constraints? What *specific* feedback am I seeking today?
- **"I Like / I Wish / What If":** what's working and must be protected / what fails a heuristic-or-goal (tie to heuristic # + severity) / what alternative serves the goal better.
- **CDS-30 (the reusable question bank):** 30 heuristic questions across **6 perspectives — User · Environment · Interface · Components · Design · Visual Marks** (go broad before pixels). Plus the visual rubric (hierarchy / spacing / type / color / depth / affordance / states). Ban "I like / I don't like" → require "for *this user and task* the risk is…".

### G4 — DIRECT (converge / decide)
Collapse the critique into **one** ranked, agreed direction — not a list of conflicting opinions.
**Standard questions:** What are the must-fix sev-3/4 vs nice-to-have sev-1/2? What single direction do we commit to? What's the success criterion — how will we *know* it's better (define "good" before building)? What's explicitly **out of scope** this round?

### G5 — ITERATE (in Figma, on a branch)
Open a **Figma branch** off `main` (the safe iterate-then-revert mechanism); apply the agreed direction; keep `main` untouched. Token changes go through **Tokens Studio** (so they're structural, not one-off pixel tweaks). Re-critique on the branch.
**Standard questions:** Does the branch resolve the sev-3/4 items **without introducing new violations**? Page-grouped diff vs `main` — is every change intentional? Does each change stay *on-system* (auto-correct/lint catches drift)? **Merge, or discard the branch (= the clean revert) and re-branch?**

### G6 — RECONCILE (Figma → code) — *the revert edge*
Mark **Ready for dev**; add measurement + text annotations (interaction states, edge cases, motion intent — not just the happy path). Implement from **Dev Mode + Code Connect** so generated code **reuses your real components**, not throwaway markup. For net-new layout, a generator (Visual Copilot CLI) scaffolds, then you wire it to the kit. **The revert-gate:** commit the variant *before* measuring → re-run G1 audit + a11y/lint + your test/coverage gate on the changed build → **auto-revert if any tracked axis regresses** (your `autoresearch` / `verification-before-completion` discipline applies cleanly). System-wide changes ride the **token PR**, not per-file edits, so they're deterministic and revertible (git + token diff).
**Standard questions:** 1:1 parity vs the Figma intent? Tokens/components reused (Code Connect), no new hardcoded values / icon packs? All states implemented? Did the round-trip touch state/routing/data — and if so, is that change kept or reverted? Did contrast/focus/token gates stay green and the audit score improve (or at least not worsen)?

### G7 — VERIFY (+ capture)
Re-audit the shipped build; confirm the **delta moved** (don't self-certify — your peer-review law). Capture durable decisions via `/self-reflect` + basic-memory so the next loop doesn't re-litigate. Then return to G1.
**Standard questions:** Did the change move the rubric score (per-dimension Δ on 0–4; critical-error burndown)? Any regression? Does the live app match the Figma intent? What design decisions are now durable?

---

## 3. The transpose → discuss → revert micro-loop (your stated core)

The three-verb motion you named, isolated as the inner cycle of TCR:

1. **TRANSPOSE** (G2): live app → editable Figma frames (`generate_figma_design` for live UI; `story.to.design` for the component-accurate system loop). Pull *reality* onto the canvas.
2. **DISCUSS** (G3 + G4): named critique (silent-first → "I Like/I Wish/What If" → CDS-30 across 6 perspectives → "ask why" on every reaction), converge on **one** direction, define "good".
3. **REVERT** (G6): apply back to code through Code Connect + tokens as a **reversible commit**; re-audit; **keep only what improves the rubric and breaks no logic — revert the rest.** In Figma the literal revert = *discard the branch (don't merge)*; in code the revert = *git + token diff rollback*.

> The whole point: the **delta between the before-audit and the after-audit IS the evidence** the change was an improvement, not a lateral move. A redesign that "feels better" but moves no dimension is suspect.

---

## 4. Per-app application

- **Reframe / momentstudio** (media/motion-heavy): front-half (AUDIT → TRANSPOSE → CRITIQUE) pays most. Heavy on hierarchy (H8), system-status during long media ops (H1), undo/control (H3). Exploit **Figma Motion + MCP** (animated frame → coding agent) for the timeline/transition layer the static loop ignores. Custom canvases weaken UX-Ray's ecommerce lens — lean on Stark + axe + Nielsen crit for the chrome.
- **WebCoder** (AI/code tool): nondeterministic AI output → lean on **Judge/Evaluate/Iterate** (define "good" output as the rubric). Recognition-over-recall (H6) + error recovery (H9) dominate. Component-based React → best ROI on **Code Connect** for high-fidelity G6.
- **bilbo:** run the full 8-gate loop on its single most-used flow first; recurring 1-hour critique slot rather than one big audit.
- **All four:** stand up **one shared "Audit & Design Review" surface per app**, standardize on the **severity 0–4 + Nielsen crit script + CDS-30** so scores are comparable app-to-app and cycle-to-cycle. *That comparability is the "systematic, named" property you want.*

---

## 5. Hype vs proven (the gate-by-gate honest read)

| Element | Verdict |
|---|---|
| Nielsen 10 / heuristic-eval / severity 0–4 / NN/g critique / CDS-30 / Double Diamond | **Proven** — decades-old, primary-sourced |
| Figma branching + Dev Mode + annotations + Code Connect | **Proven** — first-party, mature |
| `generate_figma_design` (code→canvas, Feb 2026) | **Real but young** — render-mediated, free-beta → becoming usage-based paid |
| Tokens round-trip (Tokens Studio ⇄ Git ⇄ Style Dictionary; W3C DTCG v1.0 Oct 2025) | **Proven** — the only lossless channel |
| Figma Config 2026 "Code Layers" full repo↔canvas | **Unproven at scale** (days old) — keep the MCP-graph path as fallback |
| VLM / multi-agent critique panel | **Triage accelerator, NOT a judge** — ~21% expert overlap, ~24% false positives; near-random at *picking* winners |
| "One-click lossless app→Figma→code round-trip, no human review" | **Hype** — no tool does it; the named critique gate + revert-gate stay mandatory |
| "AI generates production-ready code from a design" | **Hype** — budget 20–40% refactor regardless of tool |

> **Biggest risk to flag:** the round-trip's weakest link is the **Code-to-Canvas beta** (render-mediated, captures visual state not logic). If it flakes, the loop degrades gracefully to *screenshot → VLM+manual critique → MCP-fed code edit* — still fully SOTA. **Don't let a beta feature gate the whole process.**

---

*Sources: the 9 digests in this folder (`methodology.md`, `figma-plugins.md`, `figma-mcp-tools.md`, `code-figma-roundtrip.md`, `design-systems-sota.md`, `claude-design-vs-figma.md`, `ai-design-tools.md`, `eval-rubric.md`, `wildcard.md`) — grounded in ~7 NN/g canonical articles, Figma first-party docs, CDS (arXiv 2508.05325), DC-method SLR (ScienceDirect 2022), W3C DTCG v1.0, and the VLM-critique benchmarks (arXiv 2506.16345 / WiserUI-Bench 2505.05026 / UICrit 2407.08850 / ReLook 2510.11498).*