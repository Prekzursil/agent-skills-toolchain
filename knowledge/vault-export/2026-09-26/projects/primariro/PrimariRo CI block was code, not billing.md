---
title: PrimariRo CI block was code, not billing
type: note
permalink: main/projects/primariro/primari-ro-ci-block-was-code-not-billing
tags:
- primariro
- ci
- corrected-diagnosis
- single-signal
---

# PrimariRo CI block was CODE, not billing

`valid_as_of: 2026-08-07`. **Supersedes** the "Actions availability/billing, 75-90%" claim recorded in
[[PrimariRo finish workflow wf_549c7956-0a3]]. That claim was WRONG. Fixed in commit `4760c5e`.

## The actual cause

`.github/workflows/ci.yml` hardcoded the pre-backfill cycle tuple `(2016, 2020, 2024)` in three
places (`:316` loop, `:338` `expected_coverage_inputs`, `:356` cycle-set compare). The 1992-2008
backfill shipped `terms/1996|2000|2004|2008|2012.json` and regenerated `coverage.json`, so both
exact-set comparisons went red on 2026-07-25 and stayed red. Every CI run since then died at
`FAILED:release-relations coverage-inputs`.

Fix: derive the cycle set from `RELEASE_ARTIFACTS` (already exact-set gated against disk in the same
step) instead of hardcoding. Not a self-check — `coverage.json` is generated independently, so the
comparison still catches drift both ways. `.isdigit()` excludes the `2020.sample.json` fixtures;
an empty derived set fails closed.

## Why the wrong diagnosis survived so long — three separate single-signal errors

1. **"3-16s with steps=0" read as a starved runner.** That signature is produced BY DESIGN here:
   `dependabot-auto-merge.yml` triggers on `pull_request_target: synchronize` (every push to the PR)
   and its only job is gated `if: github.actor == 'dependabot[bot]'`. Actor is `Prekzursil`, so it
   skips — seconds, zero steps, conclusion `skipped`. A healthy skip, not a block.
2. **A 403 on the annotation was treated as evidence about the cause.** No fine-grained PAT can
   carry `checks:read`, so both `gh` and the GitHub MCP failed. A tool's auth failure is a DETECTOR
   failure, never a verdict.
3. **Nobody could run the gate.** These gates are inline python inside the workflow YAML, so no
   local command exercises them. All nine `pipeline/verify/*.py` modules were green — truthfully —
   while the inline block was red. The PR body's "9 gates SUCCESS" table was accurate and did not
   cover the thing that was failing.

## The probes that settled it (all mechanically independent of the originals)

- **Offline reproduction, zero GitHub access:** extract the `run: |` block's python heredoc and
  execute it. Pre-fix → `FAILED:release-relations coverage-inputs` exit 1. Post-fix →
  `SUCCESS:release-relations terms=24361 coverage-inputs=9` exit 0.
- **`curl https://prekzursil.github.io/PrimariRo/` → HTTP 200**, title "Atlasul primarilor din
  România · PrimariRo". Plain HTTP, no auth. Refutes "Pages disabled / private repo needs Pro"
  outright, and proves the deploy chain has worked.
- **`main` has not moved since 2026-07-20.** `ci.yml:477` only uploads `gated-site` on a push to
  `main`, and `deploy-pages.yml:51-55` requires `event == 'push' && head_branch == 'main'`. So a PR
  run can NEVER deploy — PR #6's redness was never what blocked the deploy. Nothing has been
  *eligible* to deploy for 11 days.

## Durable lessons

- **A gate that lives in workflow YAML cannot be run, so it cannot be trusted.** Every gate should
  be a module with a local entry point. Interim tool: `scratchpad/run_ci_inline_gate.py` extracts and
  runs an inline block offline in ~2s.
- **Extracting a `run: |` block verbatim gives you SHELL, not python.** First attempt produced
  `SyntaxError: python - <<'PY'` in BOTH states — a detector failing identically either way measures
  nothing. Unwrap the heredoc.
- **After replacing a hardcoded expectation with a derived one, mutation-test it.** Derivation is the
  exact shape that becomes a silent no-op. Measured: dropping a cycle fires `coverage-cycles`,
  corrupting a sha256 fires `coverage-hash`, dropping a source artifact is caught earlier by the
  schema gate. 3/3 caught.

## Relations

- supersedes [[PrimariRo finish workflow wf_549c7956-0a3]]
- relates_to [[Single-signal verification]]
