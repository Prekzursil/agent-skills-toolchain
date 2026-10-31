# LANE DOCS — grounding artifact (scratch, untracked)

Lane: DOCS — "find what the docs promise that the code does not do".
Repo: C:/Users/Prekzursil/source/ast-integrate @ ae8205a4 (worktree of agent-skills-toolchain,
branch main). Measured 2026-08-12. GROUNDING lane: no production code written.

## COVERAGE — all rows MEASURED

- [x] inventory: 187 files under docs/, 153 .md in lane scope (docs/** + README/AGENTS/CLAUDE)
- [x] mechanical dead-path detector, 3-state (EXACT / SHORTHAND / ABSENT)
- [x] detector control: 3-state, present=silent, shorthand=SHORTHAND, absent=ABSENT — PASSES
- [x] use-vs-mention classifier reuse probe — existing classifier has NO fitting kind
- [x] documented npm scripts vs package.json
- [x] stale counts vs executed collectors
- [x] documented behaviour vs code: rollback/edit-checkpoints, roadmap vs topology
- [x] prior art census: which gates already cover which doc trees
- [x] external SOTA
- [ ] NOT MEASURED: docs/ code fences are not executed (no doctest harness) — see plan item 4
- [ ] NOT MEASURED: 175 ABSENT refs inside dated archive dirs were excluded, not adjudicated

## HEADLINE

The naive "documented path does not exist" sweep is NEAR-ZERO YIELD on this corpus:
249 raw hits -> 45 detector noise -> 204 ABSENT -> 29 in live (non-archive) docs ->
**0 genuine broken promises**. Every one of the 29 is a retirement notice, an honest
declared residual, a superseded-banner frozen record, explicitly deferred work, or an
out-of-repo path. This repo's docs are unusually disciplined about naming absent things.
A dead-path linter over docs/** would be ~100% false-positive and would generate churn.

The real defects were found by reading BEHAVIOUR, not paths.

## DOC-VS-REALITY TABLE

| # | claim | measured reality | verdict | fix |
|---|---|---|---|---|
| 1 | `commands/rollback.md`: an `edit-checkpoints` PreToolUse hook "snapshots the pre-edit state once per turn" | live `_dispatch/manifest.json` PreToolUse n=5 vs repo n=7; `edit-checkpoints` + `mcp-liveness/pretool` absent live. `grep -c edit-checkpoints ~/.claude/settings.json` = 0. Newest `~/.claude/checkpoints/*/index.ndjson` = 2026-07-18 (25 d stale, 12 dirs) | CONFIRMED defect | FIX CODE (deploy/wire). Doc is right, repo code is right, deployment is stale. OUT of docs file scope |
| 2 | `docs/roadmap.md` "## Now": keep `tools/web/` a primary execution surface; `skills/` is "only a temporary compatibility layer" | `tools/web/` holds README.md only, whose own text says "This surface is currently empty"; `skills/` holds 338 tracked SKILL.md. Both docs committed 2026-08-09 | CONFIRMED contradiction | FIX DOC (roadmap) — topology is deliberate |
| 3 | `README.md:60` "22 offline policy/gate tests" | `pytest tests/test_policy.py --collect-only` = **24 tests collected** | CONFIRMED stale count | FIX DOC |
| 4 | `README.md:58` "8 tools" + names | `python list_tools.py` = "scholarly-access: 8 tools", names match exactly | ACCURATE | none |
| 5 | `README.md:62` "10 live end-to-end checks" | 10 counted in tests/test_live.py | ACCURATE | none |
| 6 | `AGENTS.md:75` `cd tools/fanout-schema && npm run lint` | fanout-schema package.json has `lint` | ACCURATE | none |
| 7 | `npm run mcp:serve` (README:130) | absent from package.json — but the sentence says it was deleted | ACCURATE (retirement notice) | none |
| 8 | 29 live ABSENT path refs (README:134/203, AGENTS:52/62, quickstart:8, codex-as-mcp:4, codex-consult-analysis ×7, R-M18 ×4, program-b ×2, cyberstrike:76, mcp-consolidation ×2, …) | each sits in an explicit "deleted / retired / closed / NOT WRITTEN / deferred / does not exist" sentence, or names an out-of-repo path | NOT DEFECTS | none — do not "fix" these |

## DETECTOR NOTES (my instrument, disclosed)

- 3-state control passes. Shorthand arm is load-bearing: without it 45/249 (18%) were noise
  (`schrodinger-mcp/VALIDATION.md` really is `tools/mcp/schrodinger-mcp/VALIDATION.md`).
- Residual FP class: out-of-repo paths (`~/.agents/...`, `.codex/config.toml`, another repo).
- `hooks/_shared/use_vs_mention.py` (860 lines, corpus + tests) is the right FRAMEWORK but has
  no fitting kind: `kind="path"` -> UNKNOWN/"unknown-kind"; `kind="marker"` -> MENTION under
  BOTH hypotheses (inert control shape); `kind="pathword"` answers a different question.

## PRIOR ART (do not rebuild)

Already in repo and CI-wired: `ci/tests/test_rules_doc_contracts.py`,
`test_rules_doc_coherence.py`, `test_rules_integrity.py` (incl. a relative-link filesystem
walk), `test_deploy_doc_consistency.py`, `test_coverage_authority_consistency.py`,
`hooks/git-hygiene/test_docs_hygiene.py`, `tools/re-harness/mcp_doc_drift.py`,
`tools/harness-drift/`, `hooks/_shared/use_vs_mention.py`.
GAP: every one is scoped to `rules/`, `agents/`, `commands/`, `agent-self/config/` or the
deployable `~/.claude` docs. **`docs/**` is gated only for `docs/program-b/`.**

## EXTERNAL SOTA

Executable documentation is the durable answer (rustdoc doctests, mdbook test, rust-skeptic):
the doc's claim is RUN, so it cannot silently lie. Prose-scanning is the weak form. lychee is
the mature link-rot checker (Rust, async, CI action, JSON output) — relevant only for URLs.

## RANKED PLAN

1. Wire `edit-checkpoints` (+ `mcp-liveness/pretool`) into the live dispatch manifest, or
   state in rollback.md that it requires deployment. Row 1 is the only user-visible breakage.
2. Fix `docs/roadmap.md` "## Now" (rows 2). Two-line edit; do not touch topology.
3. Fix the 22 -> 24 count in README.md (row 3).
4. If a gate is wanted for docs/**, gate EXECUTABLE claims (counts, `npm run X`, collector
   output) — not path mentions. Extend use_vs_mention with a `docref` kind rather than
   writing a new classifier.
5. Do NOT ship a dead-path linter over docs/**. Measured 0/29 precision on live docs.
