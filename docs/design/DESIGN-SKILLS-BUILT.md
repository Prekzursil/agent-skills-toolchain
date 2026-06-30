# DESIGN-SKILLS-BUILT — the 5 TCR design-review skills, wired

**Built / validated:** 2026-06-30 · **Origin:** design-SOTA research (this `design-research/` corpus).
**Status:** all 5 skills pass `quick_validate.py` (5/5).

Implements `DESIGN-WORKFLOW.md` (the 8 gates + transpose→discuss→revert micro-loop),
`DESIGN-SKILLS-AND-EVAL.md` (the leaf-skill table, DESIGN-EVAL v1 rubric, engagement
discipline), and `FIGMA-SETUP.md` (the Figma round-trip surface).

---

## 1. The five skills

| # | Skill | Path | Role in the loop | Validates |
|---|---|---|---|---|
| 1 | **ui-audit** | `~/.claude/skills/ui-audit/` | **G1 AUDIT / G7 VERIFY** — drives a running web/Electron app, Track-A deterministic numbers (a11y, contrast, spacing, tap targets, dead buttons, motion, visual-diff) + Track-B VLM verdict on DESIGN-EVAL v1. READ-ONLY. | ✅ |
| 2 | **transpose-to-figma** | `~/.claude/skills/transpose-to-figma/` | **G2 TRANSPOSE** (*transpose edge*) — altitude selector for code→Figma capture (story.to.design / generate_figma_design / html.to.design); reasons about the lossy round-trip. | ✅ |
| 3 | **critique-panel** | `~/.claude/skills/critique-panel/` | **G3 CRITIQUE** (*discuss edge*) — 4 named personas (user-advocate / systems-consistency / a11y / brand-aesthetic) reason over ui-audit's numbers + screenshot, run I Like/I Wish/What If, score 0–4, synthesize into ranked findings + weighted composite. TRIAGE, not oracle. | ✅ |
| 4 | **design-tokens-pipeline** | `~/.claude/skills/design-tokens-pipeline/` | **G5/G6 token spine** — DTCG round-trip: extract (code→DTCG), validate (5 round-trip-breaking rules), diff (forward + **inverse revert patch**). Tokens are the one thing that round-trips losslessly → the revert surface. | ✅ |
| 5 | **design-review-loop** | `~/.claude/skills/design-review-loop/` | **The TCR orchestrator** — sequences the 8 gates (G0–G7), holds the per-gate question banks + the G6 revert-gate. Stays THIN: it wires the leaf skills, never re-implements them. | ✅ |

**TCR = Transpose · Critique · Reconcile** — the three verbs that ARE the transpose→discuss→revert
motion (gates G2 → G3 → G6).

---

## 2. Validation results

Validator: `~/.codex/skills/.system/skill-creator/scripts/quick_validate.py` (same engine as
`validate-all-skills.ps1`).

| Skill | Initial result | Fix applied | Final |
|---|---|---|---|
| ui-audit | FAIL — `origin` not an allowed frontmatter key | moved `origin: user` under `metadata:` | ✅ valid |
| design-review-loop | FAIL — same `origin` key | moved under `metadata:` | ✅ valid |
| critique-panel | FAIL — no `SKILL.md` (only `.mjs` + `panel_rubric.md`) | authored `SKILL.md` | ✅ valid |
| transpose-to-figma | ✅ valid (origin already in HTML comment, not frontmatter) | — | ✅ valid |
| design-tokens-pipeline | FAIL — no `SKILL.md` (only `.mjs` + fixtures) | authored `SKILL.md` | ✅ valid |

**Final: 5 / 5 pass.** No angle-bracket-in-description issues were present. The allowed
frontmatter keys are `allowed-tools, description, license, metadata, name` — the `origin`
provenance now rides under `metadata` (or an HTML comment, as transpose-to-figma already did).

---

## 3. Wiring map — how design-review-loop's gates invoke each skill

The orchestrator's gate table + per-gate detail already cross-reference every leaf skill.
Confirmed cross-references in `design-review-loop/SKILL.md`:

| Gate | Name | Invokes (leaf skill / tool) | Edge |
|---|---|---|---|
| **G0** | PRIME | `prime` · **`design-system`** (Mode 2 Visual Audit) · **`design-sync`** (`@dsCard` repo→Claude Design) | — |
| **G1** | AUDIT | **`ui-audit`** (Track-A numbers + Track-B VLM) → `audit.json` + screenshots | — |
| **G2** | TRANSPOSE | **`transpose-to-figma`** (altitude selector) | *transpose* |
| **G3** | CRITIQUE | **`critique-panel`** (4 personas → ranked verdict) | *discuss* |
| **G4** | DIRECT | `frontend-design-direction` / `make-interfaces-feel-better` — **human decides** | — |
| **G5** | ITERATE | **`figma`** (`use_figma`, Figma branch) · **`design-tokens-pipeline`** / Tokens Studio | — |
| **G6** | RECONCILE | **`figma-implement-design`** (Dev Mode + Code Connect) · **`design-tokens-pipeline`** (inverse patch) · `verification-before-completion` + the harness `revert` subcommand | *revert* |
| **G7** | VERIFY | re-run **`ui-audit`** · `/self-reflect` + basic-memory | — |

**Existing skills cross-referenced (the "integration"):**
- **`figma`** → G5 (open a Figma branch, fetch nodes, MCP setup).
- **`figma-implement-design`** → G6 (Figma→code apply-back via Dev Mode + Code Connect).
- **`design-sync`** → G0 (`@dsCard` repo→Claude Design source-of-truth handoff).
- **`design-system`** → G0 (Mode 2 Visual Audit / component-system priming).
- **`forge-discipline`** → cross-gate **engagement discipline** (`SKILL.md` §discipline: systematic-not-vibes,
  defer-direction-to-human, no-over-design, anti-tunnel quota, never-self-certify, revert-is-first-class).

**New leaf skills the loop owns:** `ui-audit` (G1/G7), `transpose-to-figma` (G2),
`critique-panel` (G3), `design-tokens-pipeline` (G5/G6).

The data spine: `ui-audit` emits `audit.json` → `critique-panel` consumes it → both share the
DESIGN-EVAL v1 rubric (9 dimensions, weights, critical-error override). `design-tokens-pipeline`
emits the inverse patch consumed by the G6 revert-gate.

---

## 4. How the TCR loop invokes each skill (the run sequence)

```
node loop.mjs init --app <app> --flow <path> --truth <repo|figma> --altitude <system|audit>   # G0 opens
node loop.mjs gate           # prints CURRENT gate's method + leaf skill + question bank
  └─ you run that leaf skill, then:
node loop.mjs advance        # ordering-checked; G7 -> G1 wraps
node loop.mjs revert --before <N> --after <N> [--critical-* | --gates-red | --tests-red | --logic-touched]   # G6 KEEP/REVERT
node loop.mjs status
```

Per gate:
- **G0 PRIME** → invoke `design-system` (Mode 2) / `design-sync`; set scope + source-of-truth + altitude.
- **G1 AUDIT** → invoke `ui-audit` (Track-A + Track-B) → `audit.json` + screenshots.
- **G2 TRANSPOSE** → invoke `transpose-to-figma` (pick story.to.design / generate_figma_design / html.to.design).
- **G3 CRITIQUE** → invoke `critique-panel`: `assemble` (route `audit.json` onto persona briefs) → Claude fills each persona → `validate` (quota gate) → `synthesize` (ranked findings + weighted composite).
- **G4 DIRECT** → `frontend-design-direction`; **human picks** one of the enumerated directions.
- **G5 ITERATE** → `figma` branch + `design-tokens-pipeline` (extract/validate; structural token changes via Tokens Studio).
- **G6 RECONCILE** → `figma-implement-design` (Code Connect) + `design-tokens-pipeline token_diff --revert` (inverse patch) → `loop.mjs revert` decides KEEP/REVERT (auto-revert if composite drops, a new critical appears, a gate/test goes red, or unapproved state/routing/data was touched — the round-trip is lossy for logic).
- **G7 VERIFY** → re-run `ui-audit`; confirm the rubric delta moved; capture durable decisions via `/self-reflect` + basic-memory; loop back to G1.

**The honesty note (carried from the research):** the *building-block methods* (Nielsen 10,
NN/g heuristic-eval + critique rituals, CDS-30, severity 0–4, Figma branching/Dev Mode/Code
Connect, W3C DTCG) are canonical and primary-sourced; the **8-gate packaging + the "TCR" name
are a synthesis** (no single industry-blessed "design-review loop" product). VLM critique is a
**recall amplifier / triage accelerator, not a judge** (~21% expert overlap, near-random at
*picking* a winner) — **the human is the decider at G4**.

---

## 5. Terminal-state markers (for anti-degeneration / orchestration)

- `ui-audit`: `SUCCESS:ui-audit-<gate>` per audit gate.
- `critique-panel`: `SUCCESS:critique-panel-<persona>-<id>` (validate), `SUCCESS:critique-panel-<id>` (synthesize).
- `design-tokens-pipeline`: `SUCCESS:design-tokens-{extract,validate,diff} …` / `FAILED:…`.
- `design-review-loop`: `SUCCESS:design-review-<id>-G0…G7`, and the G6 gate `SUCCESS:…-G6` (KEEP) / `FAILED:…-G6 <reason>` (REVERT).
