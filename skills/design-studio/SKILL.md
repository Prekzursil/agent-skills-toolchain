---
name: design-studio
description: 'ONE entry to the whole design pipeline over a running app (Reframe/momentstudio/WebCoder/bilbo),
  the mode-routed successor to design-review-loop. Runs the full TCR design-review
  loop (8 gates G0-G7, revert-gate) plus a mode router: direct, audit, mirror, critique,
  iterate, implement, verify, loop, drive, session. NOT for a design DOCUMENT (metaswarm
  review-design) nor rubric math (ui-audit).'
metadata:
  origin: user
permalink: dqverify-repo-20261013/skills/design-studio/skill
---

<!-- origin: user (design-SOTA research, 2026-06-30); RENAMED from design-review-loop -> design-studio + thin mode router (gem-hunt 2026-07-12, item C1, evidence MASTER C.1 / UIUX C.1). Implements DESIGN-WORKFLOW.md §0/§2/§3 (the 8 gates + per-gate method + the transpose->discuss->revert micro-loop), DESIGN-SKILLS-AND-EVAL.md §1.2 (the orchestrator row) + §3 (engagement discipline, revert is first-class), FIGMA-SETUP.md (G2/G5/G6 Figma surface). -->


# design-studio Skill

The **design pipeline entry point** — the ONE named surface for the whole design workflow,
and the **TCR Loop orchestrator** underneath it. `design-studio` is the renamed, mode-routed
successor to `design-review-loop`: it drives a design-review pass as **8 sequenced gates**
AND exposes a **thin mode router** so you can jump straight to a single stage instead of the
whole loop. **TCR = Transpose · Critique · Reconcile** — the three verbs that ARE the
*transpose → discuss → revert* motion (gates G2 → G3 → G6).

**Skill location:** `~/.claude/skills/design-studio/`

> Implements `DESIGN-WORKFLOW.md §0` (the 8-gate headline + table), `§2` (each gate's
> canonical named method + standard questions), `§3` (the transpose→discuss→revert
> micro-loop); `DESIGN-SKILLS-AND-EVAL.md §1.2` (the orchestrator row — *keep it thin; it
> orchestrates, the gates live in the leaf skills*) + `§3` (engagement discipline). Figma
> surface (G2/G5/G6): `FIGMA-SETUP.md`. Consolidation rationale: UIUX-CONSOLIDATION §1.1.

---

## The unified entry — the mode router (the ONE surface)

`design-studio` is the single entry to the whole design pipeline. Invoke it as a skill, or
drive the harness with a **mode**:

```
/design-studio <mode> --app <app> [--flow <path>] [--out <dir>]
  modes: direct | audit | mirror | critique | iterate | implement | verify | loop | drive | session
```

**Why one surface (UIUX C.1):** six overlapping design skills collapse to one discovery
surface; the leaves stay lazy in the `~/.agents/skills` vault behind the semantic router
(frees description-budget slots). **Do NOT invoke `/design-review`** — that name collides
with metaswarm's `review-design`, which reviews design *documents*, a different thing.

### The router table — mode → gate → leaf → absorbed trigger vocab

| Mode | Jumps to | Runs (leaf skill / harness) | Absorbs the trigger vocab of | Emits |
|---|---|---|---|---|
| `direct` | G0 PRIME + G4 DIRECT | `ui-ux-pro-max` · `frontend-design-direction` (prose) | "design direction", "define good", "pick a direction", "style / palette / font", "make interfaces feel better" | scope + persona + one committed direction |
| `audit` | G1 AUDIT (+ G7 re-audit) | `ui-audit` (Track-A numbers + Track-B VLM) | "audit the UI", "a11y / contrast check", "dead buttons", "visual review", "screenshot the screens" (metaswarm visual-review) | severity-ranked `audit.json` + shots |
| `mirror` | G2 TRANSPOSE | `transpose-to-figma` (+ `use_figma` surgical) · `design-sync` (alt target) | "transpose to figma", "code to canvas", "mirror the UI to figma / claude design" | `transpose-record.json` + `mirror-manifest.json` |
| `critique` | G3 CRITIQUE | `critique-panel` | "design critique", "persona panel", "I like / I wish / what if", "slop check" | typed, severity-rated verdict list |
| `iterate` | G5 ITERATE | `figma` (`use_figma`) · `design-tokens-pipeline` | "iterate in figma", "design tokens", "figma branch" | node-diff + token-diff on a branch |
| `implement` | G6 RECONCILE | `figma-implement-design` + revert-gate | "implement the design", "figma to code", "build from figma" | code diff (kept only if it passes) |
| `verify` | G7 VERIFY | re-run `ui-audit` + `/self-reflect` + basic-memory | "verify the design change", "did the score move", "re-audit" | before/after rubric delta + durable decisions |
| `loop` | G0 → … → G7 (full) | the state machine (`init`/`gate`/`advance`/`revert`) | "design review", "TCR loop", "run the whole design pass" | `loop-state.json` across all gates |
| `drive` | — (routes OUT) | **`ui-drive`** skill | "drive the app", "point at an element", "interact with the running app", "preview a CSS tweak" | drive-ledger + proposed patch |
| `session` | — (routes OUT) | **`design-studio-session`** skill | "interactive modify", "restyle a live element", "tweak the UI live", "micro-commit a style" | scoped micro-commit + delta re-audit |

### Two modes route OUT of this skill (not gates)

`drive` and `session` are **not** loop gates — they are the low-level app-driving and
interactive-modify capabilities. The router **hands off** rather than running a gate:

- `design-studio drive` → invoke the **`ui-drive`** skill (attach / point / preview / apply
  on the vendored `playwright-core@1.61.1`; never edits app source).
- `design-studio session` → invoke the **`design-studio-session`** skill (overlay-preview →
  element→source pick → scoped micro-commit → incremental re-audit → the SAME
  `revertDecision()` revert-gate).

Both reuse this skill's `loop-state.json`, the DESIGN-EVAL rubric, and the revert-gate —
they do **not** fork a second pipeline (that overlap is exactly what the consolidation kills).

### How an in-loop mode maps to the harness

The eight in-loop modes are **thin jumps into the existing state machine** — a mode is
`init` (if no pass yet) + `gate --gate <G>` for that mode's gate + run the named leaf +
`advance`:

| Mode | Harness call |
|---|---|
| `loop` | `node loop.mjs init …` then `gate` → run leaf → `advance` (G0→G7→G1) |
| `direct` | `node loop.mjs gate --gate G0` (and `--gate G4`) |
| `audit` | `node loop.mjs gate --gate G1` (or `--gate G7`) |
| `mirror` | `node loop.mjs gate --gate G2` |
| `critique` | `node loop.mjs gate --gate G3` |
| `iterate` | `node loop.mjs gate --gate G5` |
| `implement` | `node loop.mjs gate --gate G6` then `node loop.mjs revert …` |
| `verify` | `node loop.mjs gate --gate G7` |
| `drive` | → `ui-drive` skill (no gate) |
| `session` | → `design-studio-session` skill (no gate) |

> **Implementation note (honest):** the mode router is a **documentation-level dispatch**
> today — the SKILL tells you which gate/leaf a mode maps to, and you invoke the existing
> `loop.mjs` subcommands (`init`/`gate`/`advance`/`revert`) accordingly. A native
> `node loop.mjs mode <mode>` sugar subcommand is a ~40-LOC follow-on (UIUX C.1) that only
> wraps these same calls; it is **out of scope for this rename**. The loop-state terminal
> marker id-prefix remains `design-review-<id>` (emitted by the unchanged `loop.mjs`) for
> loop-state backward-compat — the *entry / skill name* is `design-studio`.

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

- You want **one entry** to the design pipeline — pick a `mode` (above) for a single stage,
  or `loop` to run the whole G0–G7 pass on one flow of Reframe / momentstudio / WebCoder /
  bilbo.
- You need a **systematic, named, repeatable** pass (severity 0–4 + Nielsen crit + CDS-30)
  so scores are comparable app-to-app and cycle-to-cycle — that comparability *is* the
  "systematic, named" property (`DESIGN-WORKFLOW.md §4`).
- You want the **transpose → discuss → revert** motion driven end-to-end with a real
  revert-gate, not vibes.
- You want to **drive** the live app / **point** at an element (`drive` → `ui-drive`) or
  **interactively restyle** a live element with micro-commits (`session` →
  `design-studio-session`).

**When NOT to use:**
- Reviewing a design **document** (a spec/PRD) → that is metaswarm `review-design`
  (`/review-design`), NOT this skill.
- A single leaf gate in deep isolation → you may call that skill directly (`ui-audit`,
  `critique-panel`, `transpose-to-figma`, `figma-implement-design`) — but the `mode` router
  is the preferred surface so the artifact contract stays unified.
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

| Gate | Name | Mode | Canonical named method | Leaf skill / tool (invoked) | Emits |
|---|---|---|---|---|---|
| **G0** | **PRIME** | `direct` | scope-setting + source-of-truth decision (loop altitude) | `prime` · `design-system` (Mode 2) · `design-sync` | scope + persona + "truth: repo or Figma?" + altitude |
| **G1** | **AUDIT** | `audit` | NN/g Heuristic Evaluation (Prepare→Evaluate→Consolidate); Nielsen 10 + severity 0–4 | **`ui-audit`** (Track-A numbers + Track-B VLM) | severity-ranked, de-duped findings |
| **G2** | **TRANSPOSE** | `mirror` | code→Figma capture ("Code to Canvas"), altitude-selected | **`transpose-to-figma`** | editable Figma frames w/ Code Connect IDs + token refs |
| **G3** | **CRITIQUE** | `critique` | NN/g Design Critique + CDS-30 + "I Like / I Wish / What If" | **`critique-panel`** (named personas) | typed, severity-rated verdict list |
| **G4** | **DIRECT** | `direct` | severity-prioritized decision; define "good" (Judge/Evaluate/Iterate) | `frontend-design-direction` — **human decides** | one committed direction + explicit out-of-scope |
| **G5** | **ITERATE** | `iterate` | Figma **branch** (safe iterate-then-revert); Tokens Studio for tokens | `figma` (`use_figma`) · `design-tokens-pipeline` | Figma node-diff + token-diff on a branch |
| **G6** | **RECONCILE** | `implement` | Dev Mode + **Code Connect**; token PR; **the revert-gate** | **`figma-implement-design`** + `verification-before-completion` | code diff on a branch — kept only if it passes |
| **G7** | **VERIFY** | `verify` | re-audit delta; capture learnings (no self-certify) | re-run `ui-audit` · `/self-reflect` + basic-memory | before/after rubric delta + durable decisions |

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
$DR = "$HOME/.claude/skills/design-studio/loop.mjs"
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
work — it sequences and re-anchors. (A `mode` maps to one or two of these calls — see the
router table above.)

---

## The gates in detail — method + standard questions

Each gate's canonical named method and standard question bank are encoded in `gates.mjs`
and printed by `loop.mjs gate` / `questions`. Verbatim intent from `DESIGN-WORKFLOW.md §2`:

### G0 — PRIME (scope + source-of-truth) — mode `direct`
**Method:** scope-setting + the source-of-truth decision; pick **loop altitude** — *system
loop* (components + tokens exist → bind to them) vs *audit loop* (greenfield → extract
tokens first). The lens **rewards maturity; it does not manufacture it.**
**Standard questions:** Who is the user and the top job in this flow? · Where is the source
of truth — repo or Figma library? · Which ONE flow is in scope this pass? · System loop or
audit loop?
**Invoke:** `prime` / `design-system` (Mode 2 Visual Audit) · `design-sync` (`@dsCard`
repo→Claude Design).

### G1 — AUDIT (find problems, objectively) — mode `audit`
**Method:** NN/g Heuristic Evaluation (Prepare→Evaluate→Consolidate); Nielsen 10 +
severity 0–4 (severity = frequency × impact × persistence). **VLMs are a recall amplifier,
NOT a judge** (~21% expert overlap, ~24% false-positive).
**Standard questions:** the Nielsen-10 yes/no gates · the a11y gate (AA contrast, focus
order, ≥44px/48dp targets, alt text) · the token gate (every value bound, no raw hex) ·
severity per violation · functional-broken vs sub-optimal.
**Invoke:** **`ui-audit`** — Track-A deterministic numbers + Track-B VLM critique →
`audit.json` + screenshots.

### G2 — TRANSPOSE (code → Figma) — *the transpose edge* — mode `mirror`
**Method:** "Code to Canvas" capture, **altitude-selected** — `story.to.design` (system
loop, low drift) · `generate_figma_design` (live/localhost, medium drift) · `html.to.design`
(audit record only, high drift). Lift the running UI onto canvas so you discuss **reality,
not a stale design file**.
**Standard questions:** Does the imported frame match the live render (incl. **real states**:
empty/error/loading)? · Which screens carry the experience? · Do nodes carry Code Connect
IDs + token refs (system loop) or are they flat (audit only)?
**Invoke:** **`transpose-to-figma`** (the altitude selector + driver).

### G3 — CRITIQUE (discuss) — *the discuss edge* — mode `critique`
**Method:** NN/g Design Critique ritual — **silent individual feedback first** (kills
loudest-voice capture) → **"I Like / I Wish / What If"** → **CDS-30 across 6 perspectives**
(User · Environment · Interface · Components · Design · Visual Marks — *go broad before
pixels*) → **ask "why?"** on every reaction. Optional multi-agent persona panel
(Nielsen / Refactoring-UI / WCAG / Brand-consistency). **The panel TRIAGES; the human is
the decider.** Enforce the **quota** (≥2 wins + 1 fix per screen) even solo.
**Standard questions:** the framing bank · I Like (protect) / I Wish (heuristic # + sev) /
What If (alternative) · the CDS-30 6-perspective bank · "ask why".
**Invoke:** **`critique-panel`** → typed, severity-rated, deduped + ranked verdict.

### G4 — DIRECT (converge / decide) — mode `direct`
**Method:** severity-prioritized decision; **define "good" before building**
(Judge/Evaluate/Iterate); Impact/Effort or RICE. **DEFER DIRECTION TO THE HUMAN** — VLMs are
near-random at *picking* the better design (WiserUI-Bench); agents enumerate + rank, the
user chooses (`DESIGN-SKILLS-AND-EVAL.md §3.2`).
**Standard questions:** must-fix sev-3/4 vs nice-to-have sev-1/2? · which ONE direction? ·
the success criterion (how will we *know* it is better)? · what is explicitly out of scope?
**Invoke:** `frontend-design-direction` / `make-interfaces-feel-better` — **human decides**.

### G5 — ITERATE (in Figma, on a branch) — mode `iterate`
**Method:** open a **Figma branch** off `main` (the safe iterate-then-revert mechanism);
apply the agreed direction; keep `main` untouched. Token changes go through **Tokens Studio**
(structural, not one-off pixel tweaks). Re-critique on the branch.
**Standard questions:** Does the branch resolve sev-3/4 **without new violations**? ·
page-grouped diff vs `main` — every change intentional? · on-system? · **merge, or discard
the branch (= the clean revert) and re-branch?**
**Invoke:** `figma` (`use_figma`) · `design-tokens-pipeline` / Tokens Studio.

### G6 — RECONCILE (Figma → code) — *the revert edge* — mode `implement`
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

### G7 — VERIFY (+ capture) — mode `verify`
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
> the branch*; in code = *git + token diff rollback*. The `session` mode routes its accepted
> micro-commits through this SAME `revertDecision()`.

---

## Design-engagement discipline (enforced across all gates and modes)

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

Every subcommand prints a marker on its last line (`AGENTS.md §4` anti-degeneration). The
loop-state marker id-prefix stays `design-review-*` (emitted by the unchanged `loop.mjs`)
for state backward-compat; the skill/entry is `design-studio`:
- `SUCCESS:design-review-<id>-G0` … `-G7` (init / gate / advance / questions)
- `SUCCESS:design-review-<id>-G6` (revert KEEP) / `FAILED:design-review-<id>-G6 <reason>` (REVERT)
- `SUCCESS:design-review-<id>-status`

The per-gate marker is the typed terminal-state artifact the orchestrator emits
(`DESIGN-SKILLS-AND-EVAL.md §1.2`). The `drive` / `session` modes emit their own markers
(`SUCCESS:ui-drive-<verb>-<id>`, `SUCCESS:design-studio-session-<id>`) from their skills.

---

## Where this sits — the leaf skills each mode wires

```
direct    ─ ui-ux-pro-max / frontend-design-direction (G0/G4 — human decides)
audit     ─ ui-audit (Track-A + Track-B)                 (G1/G7)
mirror    ─ transpose-to-figma (+ use_figma / design-sync) ◀ transpose edge (G2)
critique  ─ critique-panel                                ◀ discuss edge (G3)
iterate   ─ figma (use_figma) / design-tokens-pipeline    (G5)
implement ─ figma-implement-design + revert-gate (this harness) ◀ revert edge (G6)
verify    ─ ui-audit (re-run) + /self-reflect + basic-memory (G7)
loop      ─ the full G0→G7 state machine ──── loop back to G1 ────┘
drive     ─▶ ui-drive skill                (attach / point / preview / apply)
session   ─▶ design-studio-session skill   (overlay → pick → micro-commit → revert-gate)
```

**REQUIRED NEIGHBORS:** `ui-audit` (G1/G7) · `transpose-to-figma` (G2) · `critique-panel`
(G3) · `figma` + `figma-implement-design` (G5/G6) · `design-sync` (G0) ·
`design-tokens-pipeline` (G5/G6 token spine) · `verification-before-completion` (G6 gate) ·
`ui-drive` (`drive` mode) · `design-studio-session` (`session` mode). This skill is the
**entry + sequencer + question-bank + revert-gate** only — the gates' work lives in those
leaves (`DESIGN-SKILLS-AND-EVAL.md §1.2`: *keep the orchestrator thin*).

---

## TDD

```powershell
cd ~/.claude/skills/design-studio
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