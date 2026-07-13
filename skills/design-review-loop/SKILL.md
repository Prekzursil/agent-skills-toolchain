---
name: design-review-loop
description: Use to run the full named TCR design-review workflow as 8 sequenced gates — G0 PRIME, G1 AUDIT, G2 TRANSPOSE, G3 CRITIQUE, G4 DIRECT, G5 ITERATE, G6 RECONCILE, G7 VERIFY, then loop back to G1 — over a running app (Reframe, momentstudio, WebCoder, bilbo). The orchestrator that drives the transpose then discuss then revert motion — it invokes ui-audit at G1, transpose-to-figma at G2, critique-panel at G3, and figma-implement-design plus the revert-gate at G6, holding the standard per-gate question banks and the rule that every apply-back is a reversible commit reverted if it regresses any tracked axis or touches logic. Do NOT use for a single leaf gate in isolation (call that skill directly) or for the eval rubric math (that is the ui-audit and critique-panel verdict).
metadata:
  origin: user
---

<!-- origin: user (design-SOTA research, 2026-06-30); implements DESIGN-WORKFLOW.md §0/§2/§3 (the 8 gates + per-gate method + the transpose->discuss->revert micro-loop), DESIGN-SKILLS-AND-EVAL.md §1.2 (the design-review-loop orchestrator row) + §3 (engagement discipline, revert is first-class), FIGMA-SETUP.md (G2/G5/G6 Figma surface). -->


# design-review-loop Skill

> **SUPERSEDED by `design-studio` (mode-routed successor).** The live skill was renamed to
> **`design-studio`**, which runs this SAME TCR design-review loop (G0 PRIME → G7 VERIFY, the
> revert-gate) plus a thin mode router (direct · audit · mirror · critique · iterate ·
> implement · verify · loop · drive · session). For new work use **`design-studio`** (or
> `design-studio loop` for the whole pass). This entry is retained for provenance and so
> in-flight invocations of the old name still resolve — it is **not** deleted.

The **TCR Loop orchestrator** — the named entry point that drives a design-review pass
as **8 sequenced gates** and wires the *existing* leaf skills as the gate implementations.
**TCR = Transpose · Critique · Reconcile** — the three verbs that ARE the *transpose →
discuss → revert* motion (gates G2 → G3 → G6).

**Skill location:** `~/.claude/skills/design-review-loop/`

> Implements `DESIGN-WORKFLOW.md §0` (the 8-gate headline + table), `§2` (each gate's
> canonical named method + standard questions), `§3` (the transpose→discuss→revert
> micro-loop); `DESIGN-SKILLS-AND-EVAL.md §1.2` (the `design-review-loop` row — *keep it
> thin; it orchestrates, the gates live in the leaf skills*) + `§3` (engagement
> discipline). Figma surface (G2/G5/G6): `FIGMA-SETUP.md`.

---

## Overview — keep the orchestrator THIN

This skill **sequences** gates and **holds the question banks + the revert-gate**. It does
**not** re-implement audit, critique, transpose, or implementation — those are leaf skills.
The harness (`loop.mjs`) is **pure plumbing**: it never calls a model, never measures
pixels, never edits app source. It tracks *which gate you are on*, prints that gate's
canonical method + leaf skill + standard questions, advances with ordering checks, and runs
the **G6 revert decision** (`DESIGN-SKILLS-AND-EVAL.md §1.2`).

**The honesty note (cite it):** the *building-block methods* are canonical and
primary-sourced (Nielsen's 10 heuristics, NN/g heuristic-evaluation + design-critique
rituals, CDS-30, severity 0–4, Figma branching/Dev Mode/Code Connect, W3C DTCG tokens).
The **8-gate packaging and the "TCR" name are a synthesis** — there is no single
industry-blessed "design-review loop" product; the SOTA is the *assembly* of named
primitives (`DESIGN-WORKFLOW.md` preamble).

---

## When to use

- You want to run the **whole** design-review workflow on one flow of Reframe /
  momentstudio / WebCoder / bilbo, not just one gate.
- You need a **systematic, named, repeatable** pass (severity 0–4 + Nielsen crit + CDS-30)
  so scores are comparable app-to-app and cycle-to-cycle — that comparability *is* the
  "systematic, named" property (`DESIGN-WORKFLOW.md §4`).
- You want the **transpose → discuss → revert** motion driven end-to-end with a real
  revert-gate, not vibes.

**When NOT to use:**
- A single leaf gate in isolation → call that skill directly (`ui-audit`, `critique-panel`,
  `transpose-to-figma`, `figma-implement-design`).
- The eval-rubric math (per-dimension 0–4, weighted composite, critical-error override) →
  that lives in `ui-audit` Track-B + `critique-panel` (`DESIGN-SKILLS-AND-EVAL.md §2`).

---

## The headline — the 8 named gates

> **G0 PRIME → G1 AUDIT → G2 TRANSPOSE → G3 CRITIQUE → G4 DIRECT → G5 ITERATE →
> G6 RECONCILE → G7 VERIFY → (back to G1)**

- **Transpose edge** = G2 (and the G6 return capture).
- **Discuss edge** = G3 (+ G4 decide).
- **Revert edge** = G6 (the revert-gate: every apply-back is a reversible commit; revert if
  any tracked axis regresses).

Run cheaply-automatable gates (G1 audit, G7 verify) continuously; run G3 critique per
feature; run G5–G6 per approved change-set. Cadence borrows NN/g's 1-hour-critique rhythm —
**narrow scope per pass, do not boil the ocean** (`DESIGN-WORKFLOW.md §0`).

| Gate | Name | Canonical named method | Leaf skill / tool (invoked) | Emits |
|---|---|---|---|---|
| **G0** | **PRIME** | scope-setting + source-of-truth decision (loop altitude) | `prime` · `design-system` (Mode 2) · `design-sync` | scope + persona + "truth: repo or Figma?" + altitude |
| **G1** | **AUDIT** | NN/g Heuristic Evaluation (Prepare→Evaluate→Consolidate); Nielsen 10 + severity 0–4 | **`ui-audit`** (Track-A numbers + Track-B VLM) | severity-ranked, de-duped findings |
| **G2** | **TRANSPOSE** | code→Figma capture ("Code to Canvas"), altitude-selected | **`transpose-to-figma`** | editable Figma frames w/ Code Connect IDs + token refs |
| **G3** | **CRITIQUE** | NN/g Design Critique + CDS-30 + "I Like / I Wish / What If" | **`critique-panel`** (named personas) | typed, severity-rated verdict list |
| **G4** | **DIRECT** | severity-prioritized decision; define "good" (Judge/Evaluate/Iterate) | `frontend-design-direction` — **human decides** | one committed direction + explicit out-of-scope |
| **G5** | **ITERATE** | Figma **branch** (safe iterate-then-revert); Tokens Studio for tokens | `figma` (`use_figma`) · `design-tokens-pipeline` | Figma node-diff + token-diff on a branch |
| **G6** | **RECONCILE** | Dev Mode + **Code Connect**; token PR; **the revert-gate** | **`figma-implement-design`** + `verification-before-completion` | code diff on a branch — kept only if it passes |
| **G7** | **VERIFY** | re-audit delta; capture learnings (no self-certify) | re-run `ui-audit` · `/self-reflect` + basic-memory | before/after rubric delta + durable decisions |

---

## The single load-bearing truth: the round-trip is LOSSY

**"code → Figma → code" is not byte-preserving** (`DESIGN-WORKFLOW.md §1`). The **only**
things that round-trip cleanly: **W3C DTCG design tokens** and **Code-Connected
components**. Design→code transfers visual structure; **business logic, state, API calls do
NOT.** Code→design captures rendering; **React state, routing, integrations vanish.**

**Consequence — why "revert" is a first-class gate (G6):** treat every apply-back as a
**reversible commit on a branch**; diff for logic regressions; **keep only the visual delta,
revert anything that re-touched state/routing/data.** Figma is the source of truth for
*visual* decisions only. The harness encodes this in the `revert` subcommand.

---

## Driving the loop (the harness)

`loop.mjs` keeps a `loop-state.json` so a pass survives across turns/compaction. Every
subcommand prints a terminal-state marker (`AGENTS.md §4`).

```powershell
$DR = "$HOME/.claude/skills/design-review-loop/loop.mjs"
$OUT = "./dr-out"

# G0 — start a pass (records scope + source-of-truth + altitude; opens at G0 PRIME)
node $DR init --app reframe --flow /editor --truth repo --altitude system --out $OUT
#   -> prints the G0 question bank; SUCCESS:design-review-<id>-G0

# Show the CURRENT gate's method + leaf skill + standard questions (the next thing to run)
node $DR gate --out $OUT
#   or a specific gate:  node $DR gate --gate G3 --out $OUT

# After you've actually run the gate's leaf skill, advance (ordering-checked; G7 -> G1)
node $DR advance --out $OUT

# Where am I?
node $DR status --out $OUT

# Just dump a gate's standard question bank (no state needed)
node $DR questions --gate G1
```

**The orchestration contract:** `gate` tells you *which leaf skill to invoke and what to
ask*; **you run that leaf skill**; then `advance`. The orchestrator never does the gate's
work — it sequences and re-anchors.

---

## The gates in detail — method + standard questions

Each gate's canonical named method and standard question bank are encoded in `gates.mjs`
and printed by `loop.mjs gate` / `questions`. Verbatim intent from `DESIGN-WORKFLOW.md §2`:

### G0 — PRIME (scope + source-of-truth)
**Method:** scope-setting + the source-of-truth decision; pick **loop altitude** — *system
loop* (components + tokens exist → bind to them) vs *audit loop* (greenfield → extract
tokens first). The lens **rewards maturity; it does not manufacture it.**
**Standard questions:** Who is the user and the top job in this flow? · Where is the source
of truth — repo or Figma library? · Which ONE flow is in scope this pass? · System loop or
audit loop?
**Invoke:** `prime` / `design-system` (Mode 2 Visual Audit) · `design-sync` (`@dsCard`
repo→Claude Design).

### G1 — AUDIT (find problems, objectively)
**Method:** NN/g Heuristic Evaluation (Prepare→Evaluate→Consolidate); Nielsen 10 +
severity 0–4 (severity = frequency × impact × persistence). **VLMs are a recall amplifier,
NOT a judge** (~21% expert overlap, ~24% false-positive).
**Standard questions:** the Nielsen-10 yes/no gates · the a11y gate (AA contrast, focus
order, ≥44px/48dp targets, alt text) · the token gate (every value bound, no raw hex) ·
severity per violation · functional-broken vs sub-optimal.
**Invoke:** **`ui-audit`** — Track-A deterministic numbers + Track-B VLM critique →
`audit.json` + screenshots.

### G2 — TRANSPOSE (code → Figma) — *the transpose edge*
**Method:** "Code to Canvas" capture, **altitude-selected** — `story.to.design` (system
loop, low drift) · `generate_figma_design` (live/localhost, medium drift) · `html.to.design`
(audit record only, high drift). Lift the running UI onto canvas so you discuss **reality,
not a stale design file**.
**Standard questions:** Does the imported frame match the live render (incl. **real states**:
empty/error/loading)? · Which screens carry the experience? · Do nodes carry Code Connect
IDs + token refs (system loop) or are they flat (audit only)?
**Invoke:** **`transpose-to-figma`** (the altitude selector + driver).

### G3 — CRITIQUE (discuss) — *the discuss edge*
**Method:** NN/g Design Critique ritual — **silent individual feedback first** (kills
loudest-voice capture) → **"I Like / I Wish / What If"** → **CDS-30 across 6 perspectives**
(User · Environment · Interface · Components · Design · Visual Marks — *go broad before
pixels*) → **ask "why?"** on every reaction. Optional multi-agent persona panel
(Nielsen / Refactoring-UI / WCAG / Brand-consistency). **The panel TRIAGES; the human is
the decider.** Enforce the **quota** (≥2 wins + 1 fix per screen) even solo.
**Standard questions:** the framing bank · I Like (protect) / I Wish (heuristic # + sev) /
What If (alternative) · the CDS-30 6-perspective bank · "ask why".
**Invoke:** **`critique-panel`** → typed, severity-rated, deduped + ranked verdict.

### G4 — DIRECT (converge / decide)
**Method:** severity-prioritized decision; **define "good" before building**
(Judge/Evaluate/Iterate); Impact/Effort or RICE. **DEFER DIRECTION TO THE HUMAN** — VLMs are
near-random at *picking* the better design (WiserUI-Bench); agents enumerate + rank, the
user chooses (`DESIGN-SKILLS-AND-EVAL.md §3.2`).
**Standard questions:** must-fix sev-3/4 vs nice-to-have sev-1/2? · which ONE direction? ·
the success criterion (how will we *know* it is better)? · what is explicitly out of scope?
**Invoke:** `frontend-design-direction` / `make-interfaces-feel-better` — **human decides**.

### G5 — ITERATE (in Figma, on a branch)
**Method:** open a **Figma branch** off `main` (the safe iterate-then-revert mechanism);
apply the agreed direction; keep `main` untouched. Token changes go through **Tokens Studio**
(structural, not one-off pixel tweaks). Re-critique on the branch.
**Standard questions:** Does the branch resolve sev-3/4 **without new violations**? ·
page-grouped diff vs `main` — every change intentional? · on-system? · **merge, or discard
the branch (= the clean revert) and re-branch?**
**Invoke:** `figma` (`use_figma`) · `design-tokens-pipeline` / Tokens Studio.

### G6 — RECONCILE (Figma → code) — *the revert edge*
**Method:** Dev Mode + **Code Connect** so generated code **reuses your real components**;
system-wide changes ride the **token PR**. **THE REVERT-GATE:** commit the variant *before*
measuring → re-run G1 audit + a11y/lint + your test/coverage gate → **auto-revert if any
tracked axis regresses** *or* the round-trip re-touched state/routing/data
(`verification-before-completion` / `autoresearch` discipline).
**Standard questions:** 1:1 parity vs intent? · tokens/components reused (Code Connect), no
new hardcoded values / icon packs? · all states implemented? · did the round-trip touch
state/routing/data — kept or reverted? · did contrast/focus/token gates stay green and the
audit score improve (or not worsen)?
**Invoke:** **`figma-implement-design`** + `verification-before-completion`; then the harness:
```powershell
node $DR revert --before 62 --after 81 --critical-before 2 --critical-after 0 --out $OUT
#   -> KEEP   ; SUCCESS:design-review-<id>-G6
node $DR revert --before 62 --after 81 --logic-touched --out $OUT
#   -> REVERT ; FAILED:design-review-<id>-G6  (logic touch not approved)
# flags: --critical-before/--critical-after N | --gates-red | --tests-red | --logic-touched | --logic-approved
```

### G7 — VERIFY (+ capture)
**Method:** re-audit the shipped build; confirm the **delta moved** (per-dimension Δ on 0–4;
critical-error burndown). **Do not self-certify** — peer-review (≥1–2 reviewers). Capture
durable decisions via `/self-reflect` + basic-memory so the next loop does not re-litigate.
Then return to G1.
**Standard questions:** Did the change move the rubric score? · any regression? · does the
live app match the Figma intent? · what design decisions are now durable?
**Invoke:** re-run `ui-audit` (G1) · `/self-reflect` + basic-memory.

---

## The G6 revert-gate — the decision logic (load-bearing)

`revertDecision()` in `gates.mjs` is the named, testable revert rule. An apply-back is
**KEPT** only when **every** tracked axis holds or improves **and** no logic was re-touched
(unless explicitly approved); otherwise **REVERT**:

| Tracked axis | KEEP requires | REVERT trigger |
|---|---|---|
| composite audit score (0–100) | `after >= before` | composite dropped |
| critical errors | `criticalAfter <= criticalBefore` | a new critical appeared |
| contrast / focus / token gate | green | red |
| tests / coverage | green | red |
| state / routing / data touch | not touched, OR explicitly approved | unapproved logic touch (round-trip is lossy for logic) |

> **The point** (`DESIGN-WORKFLOW.md §3`): the **delta between the before-audit and the
> after-audit IS the evidence** the change improved, not moved laterally. A redesign that
> "feels better" but moves no dimension is suspect. In Figma the literal revert = *discard
> the branch*; in code = *git + token diff rollback*.

---

## Design-engagement discipline (enforced across all gates)

From `DESIGN-SKILLS-AND-EVAL.md §3` (forge-discipline applied):

1. **Systematic, not vibes.** Run the named gates with the standard question banks every
   time; emit typed per-gate artifacts. No ad-hoc "looks good to me."
2. **Defer redesign DIRECTION to the user.** The human is the **decider at G4 / critique
   only.** Agents triage (audit, enumerate violations, propose 1–3 directions + rationale);
   they do **not** unilaterally pick the new direction.
3. **No over-design / minimal intervention.** Fix sev-3/4; don't gold-plate. Emphasize by
   *de-emphasizing peers*. A change that moves no rubric dimension is suspect.
4. **Anti-tunnel-vision.** Enforce the **quota** (≥2 wins + 1 fix per screen) even solo;
   re-read the original goal every few gates; go **broad before pixels** (CDS-30 6
   perspectives).
5. **Never self-certify; revert is first-class.** Every G6 apply-back is a reversible
   commit; re-audit; revert anything that regresses a tracked axis or re-touched
   state/routing/data. Peer-review before "done."
6. **Don't let a beta gate the loop.** Code-to-Canvas is render-mediated beta; if it flakes,
   degrade to *screenshot → critique → MCP-fed edit*. The Figma round-trip is a *nicety*.

---

## Terminal-state outputs

Every subcommand prints a marker on its last line (`AGENTS.md §4` anti-degeneration):
- `SUCCESS:design-review-<id>-G0` … `-G7` (init / gate / advance / questions)
- `SUCCESS:design-review-<id>-G6` (revert KEEP) / `FAILED:design-review-<id>-G6 <reason>` (REVERT)
- `SUCCESS:design-review-<id>-status`

The per-gate marker `SUCCESS:design-review-<gate>-<id>` is the typed terminal-state artifact
the orchestrator emits (`DESIGN-SKILLS-AND-EVAL.md §1.2`).

---

## Where this sits — the leaf skills it wires

```
G0 PRIME ─ prime / design-system / design-sync
G1 AUDIT ─ ui-audit (Track-A + Track-B)
G2 TRANSPOSE ─ transpose-to-figma          ◀ transpose edge
G3 CRITIQUE ─ critique-panel               ◀ discuss edge
G4 DIRECT ─ frontend-design-direction (human decides)
G5 ITERATE ─ figma (use_figma) / design-tokens-pipeline
G6 RECONCILE ─ figma-implement-design + revert-gate (this harness) ◀ revert edge
G7 VERIFY ─ ui-audit (re-run) + /self-reflect + basic-memory
        └──────────────── loop back to G1 ────────────────┘
```

**REQUIRED NEIGHBORS:** `ui-audit` (G1/G7) · `transpose-to-figma` (G2) · `critique-panel`
(G3) · `figma` + `figma-implement-design` (G5/G6) · `design-sync` (G0) ·
`design-tokens-pipeline` (G5/G6 token spine) · `verification-before-completion` (G6 gate).
This skill is the **sequencer + question-bank + revert-gate** only — the gates' work lives
in those leaves (`DESIGN-SKILLS-AND-EVAL.md §1.2`: *keep `design-review-loop` thin*).

---

## TDD

```powershell
cd ~/.claude/skills/design-review-loop
node --test tests/gates.test.mjs
```

Covers: all 8 gates defined with method + question bank · canonical name sequence · the
three TCR edges tagged on G2/G3/G4/G6 · `nextGate` cycle + G7→G1 wrap · `initPass` /
`advancePass` full walk + pass-bump · `renderGate` content · and the **revert-gate decision
matrix** (KEEP on improvement; REVERT on composite regression / new critical / red gate /
red tests / unapproved logic touch; KEEP on approved logic touch).

Smoke-test the CLI (no browser, no MCP):
```powershell
node loop.mjs init --app reframe --flow /editor --truth repo --altitude system --out ./_dr
node loop.mjs gate --gate G3 --out ./_dr      # -> CRITIQUE method + question bank
node loop.mjs advance --out ./_dr             # -> G0 -> G1
node loop.mjs revert --before 62 --after 81 --out ./_dr   # -> KEEP
node loop.mjs revert --before 80 --after 74 --out ./_dr   # -> REVERT
```
Expect a `SUCCESS:design-review-*` / `FAILED:design-review-*` marker on the last line of each.
