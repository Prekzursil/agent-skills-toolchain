# Design Skills, Eval-Rubric, and Engagement Discipline

**Synthesized:** 2026-06-30 from the 9 design-research lens digests in this folder.
**For:** code-first power-user (Reframe, momentstudio, WebCoder, bilbo) operating the TCR Loop (see `DESIGN-WORKFLOW.md`).
**Confidence:** 🟢 proven/converged · 🟡 emerging · 🔴 hype.

---

## 1. Skills — what to UPGRADE vs CREATE

You already have the right architecture. Most of this is *extension + orchestration*, not a rebuild. Existing design skills in the harness: `ui-audit`, `figma`, `figma-implement-design`, `design-sync`, `design-system`, `frontend-design-direction`, `forge-discipline`, `make-interfaces-feel-better`, `frontend-a11y`, `design-sync` (DesignSync MCP), plus the `design-sync` slash skill.

### 1.1 UPGRADE — `ui-audit` (the highest-priority change)
`ui-audit` is already the P1/G1 AUDIT and P5/G7 VERIFY engine (Track-A deterministic numbers + Track-B VLM critique against a Refactoring-UI/Material/HIG/Nielsen rubric). The eval research is a **drop-in extension**:
- **Track-A — add two collectors:** **tap-target/affordance** (≥44px HIG / 48dp Material; dead-button crawl; `focus-visible` present) and **motion** (duration in the 200–500ms band; dropped-frames/fps; `prefers-reduced-motion` honored).
- **Track-B — extend the dimension enum 8 → 9** (add `affordance`, `motion`); keep `rating` (pass/warn/fail) but **add a numeric `score` 0–4 per dimension** so deltas are quantitative; keep `confidence`; keep the severity ladder (it *is* Nielsen 0–4: `critical/high/medium/low/info` ≈ `4/3/2/1/0`).
- **Verdict — compute `score` via the §2.4 weighted composite** instead of free-hand; **formalize the critical-error override** (already half-implemented as the critical cap).
- **Reliability — one dimension per VLM call** (kill the halo effect), anchor with few-shot scored exemplars, run N≥2 passes on perceptual dimensions and report Krippendorff α / weighted κ.
- **UIClip prior — keep as a weak prior only** (its own ground-truth α=0.37 proves it can't see wiring/contrast/affordance); RAM-guarded, opt-in.

### 1.2 CREATE — new skills

| New skill | Role (TCR gate) | What it does |
|---|---|---|
| **`design-review-loop`** (orchestrator) | the whole TCR Loop | Named entry point that drives G0→G7 as gates with typed terminal-state artifacts per gate (`SUCCESS:design-review-<gate>-<id>`). Wires the *existing* skills as gate implementations rather than re-inventing them. Holds the standard per-gate question banks. |
| **`critique-panel`** | **G3 CRITIQUE** (discuss) | Spins named heuristic-persona reviewer agents — **Nielsen-evaluator · Refactoring-UI-evaluator · WCAG/A11y-evaluator · Brand/Consistency-evaluator** — each runs "I Like / I Wish / What If" against `get_screenshot` + `get_metadata`, emits a typed, severity-rated verdict. Output deduped + ranked. **Triage accelerator; the human is decider.** Enforces the quota technique (≥2 wins + 1 fix/screen). |
| **`transpose-to-figma`** | **G2 TRANSPOSE** | Altitude selector + wrapper over `generate_figma_design` (live/localhost), `story.to.design` (system loop), `html.to.design` (audit record only). Decides system-loop vs audit-loop and tags nodes with Code Connect IDs + token refs. |
| **`design-tokens-pipeline`** | **G5/G6 token spine** | Stands up + drives Tokens Studio ⇄ Git JSON ⇄ `sd-transforms` ⇄ Style Dictionary; opens the token PR; emits the token-diff that *is* the lossless revert surface. |

> Build these as Agent Skills with the `writing-skills` discipline (terminal-state outputs, no angle-brackets in descriptions). Keep `design-review-loop` thin — it *orchestrates*; the gates live in the leaf skills.

### 1.3 WIRE (no change needed, just bind into the loop)
- `design-system` (Mode 2 — 10-dimension Visual Audit + AI-slop detection) → **G0 PRIME / G1 AUDIT** rubric.
- `figma` + `figma-implement-design` → **G6 RECONCILE** (1:1 node→code, reuse project tokens, never import new icon packs, validate 1:1).
- `design-sync` (DesignSync MCP, `@dsCard` push) → **G0** mirror the real library into Claude Design (repo-as-source-of-truth path).
- `frontend-design-direction` / `make-interfaces-feel-better` → **G4 DIRECT / G5 ITERATE** direction.
- `forge-discipline` → enforced across all gates (see §3).
- `/self-reflect` + basic-memory → **G7** capture.

---

## 2. EVAL-RUBRIC — `DESIGN-EVAL v1` (the scoring dimensions)

The convergent SOTA pattern (5+ independent sources — UIClip, UICrit, Nielsen severity, WCAG 3.0 all agree): **per-dimension ordinal score + critical-error override + weighted composite + reliability protocol.** Never a single magic 0–100 as the *input*.

### 2.1 Scale (0–4, every dimension)
| Score | Band | Meaning |
|---|---|---|
| **4** | Excellent | ship as a reference |
| **3** | Good | only low/info nits |
| **2** | Needs-work | real medium/high defects, recoverable |
| **1** | Poor | pervasive defects |
| **0** | **Critical/fail** | a critical-error condition tripped (§2.3) |

**Ship gate** (WCAG-3.0-style Bronze): mean ≥ 3.0 **AND** no dimension < 2 **AND** zero critical errors. **Reference gate:** mean ≥ 3.5 and no dimension < 3.

### 2.2 The 9 scoring dimensions
| # | Dimension | Deterministic anchor (Track-A) | Critical-error trigger (→0) | Weight |
|---|---|---|---|---|
| 1 | **visual-hierarchy** | #competing focal weights; landmark/heading order | no focal point AND primary CTA indistinguishable | 1.5 |
| 2 | **spacing-rhythm** | % margins/padding/gaps on a 4/8px scale | colliding/overlapping content blocks | 1.0 |
| 3 | **alignment** | (screenshot-judged) + Ngo sequence/equilibrium prior | — (rarely critical) | 0.75 |
| 4 | **type-scale** | # distinct (size,weight,line-height) triples | body text illegibly small/over-set | 1.0 |
| 5 | **color-contrast** | **WCAG ratio** (≥4.5:1 body, ≥3:1 large); APCA; palette-sprawl | **any body text < 4.5:1** | **2.0** |
| 6 | **consistency** | visual-regression % drift; type-triple set diffs | same component renders differently across core screens | 1.0 |
| 7 | **empty-error-states** | pageError; dead-control; near-blank screenshot | render crash / blank where content expected / dead primary action | 1.5 |
| 8 | **affordance** *(new)* | tap-target ≥44px/48dp; dead-button crawl; focus-visible | primary action gives no signifier or no feedback | 1.5 |
| 9 | **motion** *(new)* | duration 200–500ms; dropped-frames/fps; `prefers-reduced-motion` | janky/blocking animation or motion with no reduced-motion escape | 0.75 |

### 2.3 Critical-error override (load-bearing, from WCAG 3.0)
A critical error forces its dimension to **0** and caps the verdict regardless of other scores: **1 critical → overall capped at needs-work (≤~60/100); ≥2 critical → poor.** Same condition zeroes the dimension so the composite can't average a catastrophe away.

### 2.4 Weighted composite (headline 0–100)
```
overall_0_100 = 100 * ( Σ wᵢ·scoreᵢ ) / ( 4·Σ wᵢ )    # then apply the §2.3 cap
```
**Freeze weights, viewport, theme/state, and the anchor set across any before/after pair** — changing them mid-comparison invalidates the delta.

### 2.5 Reliability protocol (what makes it *repeatable*)
One dimension per judge call · few-shot anchor exemplars · N≥2 passes on perceptual dims, report **Krippendorff α (ordinal) / weighted κ**, gate trust on it (targets κ>0.6 / α≥0.8; *expect* low agreement on pure-aesthetic dims — UIClip α=0.37, UICrit κ≈0.30 are the honest baselines) · periodically recalibrate on a gold set · lean on deterministic Track-A numbers as the spine.

### 2.6 Grading a before/after (the point)
Per-dimension delta Δᵢ on 0–4 · composite improvement `after/before − 1` (e.g. 62→81 ⇒ +31%) · **critical-error burndown** (most defensible single claim — binary, non-subjective) · report contrast pass-rate / %-on-scale spacing / tap-target compliance / type-triple count / regression % / motion-duration compliance / fps **before vs after** — the numbers a skeptic can't argue with; perceptual scores ride on top with confidence labels. **The delta IS the evidence the change improved, not moved laterally.**

---

## 3. Design-engagement DISCIPLINE (forge-discipline applied)

A short contract for *how* to behave during design work — guards against the failure modes the research flags:

1. **Systematic, not vibes.** Run the named gates (TCR) with the standard question banks every time; emit typed per-gate artifacts. No ad-hoc "looks good to me."
2. **Defer redesign DIRECTION to the user.** The human is the **decider at the G4/critique gate only.** Agents *triage* (audit, enumerate violations, propose 1–3 directions with rationale) — they do **not** unilaterally pick the new direction. VLMs are near-random at *picking* the better design (WiserUI-Bench) and ~24% false-positive on critique (GPT-4o study) — so they enumerate and rank, the user chooses.
3. **No over-design / minimal intervention.** Fix the sev-3/4 items; don't gold-plate. M3-Expressive's payoff is *faster target acquisition*, **not** decoration — "expressive ≠ decorative." Refactoring-UI: emphasize by *de-emphasizing peers*, start with too much whitespace and reduce, labels are a last resort. Don't redesign what isn't broken; a change that moves no rubric dimension is suspect.
4. **Anti-tunnel-vision.** Enforce the **quota** technique (≥2 wins + 1 fix per screen) even solo; re-read the original goal every few gates; go *broad before pixels* (CDS 6 perspectives before per-node tweaks).
5. **Never self-certify; revert is first-class.** Every G6 apply-back is a reversible commit; re-audit; **revert anything that regresses a tracked axis or re-touched state/routing/data.** Peer-review (≥1–2 independent reviewers) before "done."
6. **Don't let a beta gate the loop.** Code-to-Canvas is render-mediated beta; if it flakes, degrade gracefully to screenshot → critique → MCP-fed edit. The Figma round-trip is a *nicety*, not a hard dependency.
7. **Token cost awareness.** Generative design is token-expensive; prefer WYSIWYG knobs / direct manipulation over re-prompting; lean on Max-tier headroom for heavy 4-app iteration.

---

## 4. Claude Design vs Figma — the recommendation (the call)

**Your thesis (Claude = broad design-as-a-whole; Figma = detailed/collaborative editing) is VALIDATED, with one sharpening:** the real division is **by *who edits and how*** (conversational/whole-screen vs pointer/per-node) and ***where the source of truth lives*** (your **code repo** vs a **Figma library**) — not "broad vs detailed" alone. They overlap more than the clean split implies (Claude Design now round-trips to code + enforces a design system; Figma's MCP now writes to canvas + ingests live browser UI).

| Dimension | **Claude Design** | **Figma** |
|---|---|---|
| Core strength | intent → clickable artifact fast; whole-app direction; brand/system **compliance + auto-correct** | precise per-node editing; multiplayer ops; **tokens/variables at scale**; handoff maturity |
| Source of truth | **your code repo** (`/design-sync`, DesignSync `@dsCard`) | **Figma library** (Code Connect) |
| Code bridge | `/design-sync` (repo→Design), `/design`, **handoff bundle → Claude Code** | Dev Mode MCP (frame→code, write-to-canvas), Code Connect, `generate_figma_design` |
| Best for in TCR | G0, G2 (direction), G3 (whole-screen), G4–G5 (broad), G6 (handoff bundle) | G2 (detail), G3 (pixel), G5 (detail), G6 (1:1 impl + variant mgmt) |
| Watch-out | **token cost** at Pro tier; enterprise React-import robustness unproven | translation lossy without Code Connect; more setup/ceremony for solo speed |

**The call for a solo code-first power-user on 4 apps:**
- **Use Claude Design as the *primary* loop driver.** It's the fastest path for design-as-a-whole, it enforces your system (auto-corrects AI-slop drift), and **the repo is your source of truth** — perfect for code-first apps. Keep **one published Claude Design design-system project per app** (it supports multiple; admin-lock it if you ever collaborate).
- **Drop into Figma only as a scalpel** — pixel-precision, real variant management, or handing a specific node to `figma-implement-design`. Use `generate_figma_design` to pull a running app into Figma *when the detail discussion needs Figma's tooling*.
- **Don't run two sources of truth.** Default to repo-native (Claude Design + DesignSync); treat Figma as a *detail workshop fed from code*, not a parallel canon. Reconcile via Code Connect only if a teammate lives in Figma.
- **Hype check:** "ends the design-to-engineering handoff problem" is a vendor *bet* — it *reduces* lossy translation when one AI sits on both sides; it does **not** eliminate divergence, and the round-trip stays lossy for logic/state.

---

*Sources: `eval-rubric.md`, `claude-design-vs-figma.md`, `ai-design-tools.md`, `design-systems-sota.md`, `methodology.md`, `wildcard.md` in this folder — grounded in UIClip (UIST'24), UICrit (UIST'24), Nielsen severity (NN/g), WCAG 3.0 scoring draft, WiserUI-Bench (arXiv 2505.05026), GPT-4o-usability (arXiv 2506.16345), Anthropic Claude Design docs + Help Center, and the in-session DesignSync tool contract.*
