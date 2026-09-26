---
title: 'A8 scope ruling: UNION both selections + build all divergent (2026-07-24)'
type: project
permalink: main/projects/platform-redesign/a8-scope-ruling-union-both-selections-build-all-divergent-2026-07-24
tags:
- A8
- prompt-two
- scope
- owner-decision
- reconciliation
- '2026-07-24'
---

Owner ruled on the A8 reconciliation fork (2026-07-24) after the wf_3f71ca34 grounding surfaced it.

## Observations
- [decision] A8 canonical selection = UNION BOTH. #union — The executed PRs #139-160 followed the 1.9R 92-ID gate; the spec defined a hand-worked 38 (only 8/18 merged units overlap). Owner chose **union both** (widest): anything in EITHER selection is in-scope; build the full superset, nothing dropped. I must write the missing `CC/23-SELECTED-OPTIONS.json` to formalize the union as canonical (spec IN-1 was "one decision away").
- [decision] C22 & G-05 divergent units = build ALL FOUR. #divergent — Owner chose options 1+2: build BOTH the adjudicated siblings (C22->I3 COMPOSE_WITH H-22, G-05->D07 SPLIT_REQUIRED) AND the spec-38 survivors (C22, G-05). Maximal, consistent with union-both.
- [decision] B2 outstanding to pursue = mcp-parity + api-perm-script. #b2 — mcp-parity: cheapest first = enable the ~10 already-configured-but-DISABLED Codex servers (ghidra/ida/frida/semgrep/binary-ninja/cheatengine/hexstrike/kaggle/github_cli) then port high-value RE+quality; pair with the "Codex loads zero hooks" fix. api-perm-script: READ session idx 7918 first to pin the deliverable (account-section fix + toolchain adoption) — under-specified, don't build blind. awesome-game-security = STAYS owner-deferred (idx 3684).
- [reference] Build constraints (from grounding). #constraints — Real parallelism limiter = the 2-concurrent-local cap (box freezes on commit-exhaustion), NOT the 18 file-disjoint count -> run ~2 worktrees/wave. #170 monitor code is merged (19ef859) but its LIVE acceptance (R0-R2, killed-unit) is UNRUN -> blocks ONLY Databricks scaling past 2-local, NOT local Wave-1. Each unit: throwaway clone (git clone --no-hardlinks), scoped adds (git add -A BANNED), --no-ff integrate, gates vs STORED BLOBS (LF not CRLF), ruff pinned, TDD+100%+mutation+fresh-adversarial-review, G-A..G-H. Deployment boundary: BUILD+INTEGRATE only, NO push/install (G-4 open). 3 items Windows-not-a-fit (E17/F09/I18 -> contract-only). Plan doc: unified-continuation/20260723T190727Z/PROMPT-TWO-A8-PLAN.md.

## Relations
- part_of [[C16 + H-20 both BUILT (2026-07-24) — propose-only, review-pending]]
- relates_to [[Use the github MCP for all GitHub ops, not gh-CLI / github_cli (2026-07-24)]]


## a8-prep FINALIZED (2026-07-24) — canonical file written, queue = 73

- [milestone] Canonical `23-SELECTED-OPTIONS.json` WRITTEN. #canonical — at `prompt2-readiness/20260720-174550/23-SELECTED-OPTIONS.json` (= the spec's CC/ IN-1 path, SPEC:774-788). Carries: owner UNION-BOTH header, the 94-ID union, per-ID {provenance, status, evidence}, E08/C10 verdicts, the C16/H-20 finding, the full ordered build queue. JSON-validated (94 distinct, 0 missing/extra). NOTE: distinct from SEL/23-AUDIT-CONVERGENCE.json.
- [decision] UNION=94, DONE=21, BUILD QUEUE=73. #queue — a8-prep content-verified 21 DONE (13 MORE than the plan's 10: +C12/F02/G-04/G-06/G-10/I5/J10/L13/M02/M04 merged non-spec-38 units + C10), against HEAD a919578 (plan predated at 46fd639). Queue-73 = 67 full-build + 1 thin (E08) + 2 wire-residual (C16,H-20) + 3 contract-only (E17/F09/I18).
- [gotcha] C16 + H-20 are CODE-MERGED (#181) but NOT fully accepted — "pure libraries, no runtime wiring", and NEITHER test is in quality.yml. #not-wired — So they RE-ENTER the A8 queue as Step-0 THIN wire+gate units (add their tests to quality.yml + runtime-wire C16→fan-out-barrier, H-20→SessionStart). C16 sign-off also needs an in-module two-strikes content-verify (inf/nan defect already fixed). This is the shadow-first→wired transition I flagged as owner-gated.
- [decision] E08 → BUILD (thin: detector+both-states tests exist but unnamed in quality.yml = decorative gate per SPEC G-C; add the step). C10 → DONE (fanout_schema.mjs CI-gated). #e08-c10
- [reference] ORDERED QUEUE (in the file): Step0 = C16/H-20 wire+gate · E08 quality.yml step · C10 no-op · C22/G-05=all-four · Monitor R0-R2 (blocks Databricks ONLY). Step1 seq = E02→K22. Step2 (2-wide smalls) = A06 A14 A21 D03 F01 F13 G-01 I2 J01 +C02(Win)+1.9R-smalls. Step3 (medium, H-03 LAST) = B22 D05 E04 F15 I4 L16 + C22/I3/G-05/D07 + 1.9R-mediums(D12). Contract-only = E17/F09/I18. #build-order — UNVERIFIED: 56 1.9R-only IDs' effort/order → read SEL/33-BUILD-PLAN.json (75-unit BUILD_SEQUENCE) at execution; 20 merged units not re-audited to full per-item bar (conf 55-80%). HARD cap = 2 local workers (SPEC:624).