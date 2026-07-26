# `.design/` — the design pipeline artifact contract

One directory, one contract. Every stage of the design pipeline reads and writes a **leaf
artifact** here. A fresh Claude or Codex thread can pick up `.design/` cold and know
exactly where each stage's input and output live (the metaswarm `.beads/` recovery
pattern). **Evidence-bound gates parse these leaves — never an honor-system "it passed"
flag.**

## Leaves

| Leaf | Written by | Read by | Kind |
|------|-----------|---------|------|
| `DESIGN.md` | Mode 1 / DIRECT (G0/G4) | every stage | canon (human) |
| `design-tokens.json` | Mode 1 / token pipeline | tokens, mirror | canon (W3C-DTCG source of truth) |
| `audit.json` | `ui-audit` Track-A (G1) | critique, gates | leaf (deterministic numbers) |
| `critique-output.json` | `ui-audit` Track-B (G3/G7) | gates, revert-gate | leaf (DESIGN-EVAL v1 verdict) |
| `transpose-record.json` | transpose code→canvas (G2) | mirror, gates | leaf |
| `tokens.json` | token pipeline emit | transpose, mirror | leaf (resolved DTCG) |
| `mirror-manifest.json` | mirror `use_figma` (G6) | reverse-drift guard | leaf |
| `loop-state.json` | `loop.mjs advance` | recovery, gates | state machine |
| `baselines/` | `ui-audit visual_diff` | regression | PNG baselines |

## Rules

1. **Rubric = DESIGN-EVAL v1** (9 dims, 0-4). Source of truth:
   `~/.claude/skills/ui-audit/critique_rubric.md` + `critique.schema.json`. The legacy
   10-dim / 0-10 scale is retired.
2. **Canon = `DESIGN.md` + `design-tokens.json`** (DTCG). No second canon format.
3. **`loop-state.json.stages.<G>.artifact`** names each stage's leaf so `advance`
   auto-discovers the next input and a reviewer reconstructs the run from disk.
4. **Gates parse, never trust.** A gate reads `critique-output.json.verdict.score` +
   the critical-error count, or `audit.json.summaryTotals` — it does not accept a boolean.
5. **Shadow first.** When the artifact-contract gates are first wired they run in
   shadow/advisory mode (observe + log, never block) per council C5.

## Seeding a repo

Copy these templates into a repo's `.design/` and replace the `TEMPLATE` / `PLACEHOLDER`
values. Validate with `tests/validate_contract.mjs` (see the staging bundle).
