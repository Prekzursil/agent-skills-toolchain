# two-tier-verify

A process skill that encodes the **two-tier verification discipline** — the fix for the
`edit → rerun-the-whole-suite → re-read all output → edit again` loop that dominates token/time
cost in long agentic repair sessions (ProjDevBench measured ~4.81M tokens/problem; test-impact
selection cuts test time 32–70%).

- **INNER loop** (every edit): only the tests related to the touched files + type-check + lint.
  Seconds. Iteration signal, never a done-signal.
- **OUTER loop** (once, at the commit boundary): full suite + coverage + held-out
  E2E/golden-journey + a scoped mutation check. The merge gate.

`SKILL.md` carries the tier table, the decision rule (including when to escalate INNER→OUTER
early — shared modules, config/dep/test-infra edits, empty selection), concrete command recipes
for JS/TS (jest `--findRelatedTests` / vitest `related` / playwright single-spec / `tsc
--incremental` / eslint) and Python (pytest module/`--testmon`/`--lf`, mypy/pyright, ruff), the
mutation micro-check (Stryker / mutmut), and how to map an OUTER failure back to the change.

## Install

Canonical location (personal skill store):

```
~/.agents/skills/two-tier-verify/
├── SKILL.md
└── README.md
```

Mirror into `~/.claude/skills/two-tier-verify/` if that store is synced separately (the existing
skills are duplicated across both trees).

## Relationship to other skills

- **seed-golden-journey** — provides the held-out acceptance test that the OUTER loop runs. This
  skill decides *when* to run it (commit boundary); that skill defines *what* it is.
- **fresh-context-verify** — the independent-oracle check for a load-bearing *value*; two-tier is
  the analogous discipline for the *test run*. Both anchor "done" to an external signal.

## Provenance

Distilled from `agent-skills-toolchain/docs/agentic-perfection/AGENTIC-REPAIR-RELIABILITY.md`
(2026-07-07), which grounds it in a 7-agent SOTA workflow + deep-research on test-impact
selection (Ekstazi, Microsoft TIA, CloudBees) and the ProjDevBench token-cost finding.
