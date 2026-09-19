# Design brief — the implementation workflow for the Space rebuild (read fully before designing or judging)

## Inputs (all under /home/codespace/grills/2026-09-19-qwen38-heretic-space/)
1. `DECISION-QUEUE.md` — READ "Situation", "Resolved decisions" (11 owner decisions + later revisions; five went AGAINST the recommendation and the decision wins), "Lens digests", "Review workflow digest", "Simplification lens — RETRY".
2. `evidence/workflow-findings.md` — 50 code-review findings with verdicts; the CORRECTED CLAIM / CORRECTED RECOMMENDATION lines are the real work-unit specs (skim all titles; read every CORRECTED line).
3. `evidence/reports/lens-4-simplification-retry.md` — module layout, the seam, duplication list, 14 PR-sized steps with proofs, ship-but-flag list, characterisation tests first.
4. `evidence/orchestration/WORKFLOW_TOOL_REFERENCE.md` — the Workflow tool contract (plain JS, `meta` pure literal, `agent()/pipeline()/parallel()`, schemas, null results, resume cache, no Date.now/Math.random, concurrency cap CPUs−2: 2 now, 14-16 after a Codespace resize).
5. `evidence/orchestration/research-1-doctrine.md` — 30 principles D-n, 17 anti-patterns, 9 conflict resolutions (the owner's own skills doctrine).
6. `evidence/orchestration/research-2-tool-native.md` — 25 principles T-n, 12 anti-patterns, full JS skeletons, empirical scheduling data.
7. `evidence/orchestration/research-3-external-sota.md` (25 principles S-n, 14 AP) and `research-3-external-sota-DEEP.md` (22 principles S-n, 12 AP, 88 graded sources) — two independent external research runs; where they disagree, say which you follow and why.
8. `evidence/orchestration/research-4-red-team.md` — 47 failure modes F-1..F-47 with detection/guard/where; the coverage matrix must cover every one.
9. Context only: `evidence/reports/lens-*.md`, `scout-*.md`, `evidence/feature-inventory.md`.

## Non-negotiables (from the owner and the evidence)
- The decisions in DECISION-QUEUE.md are law; where a research principle conflicts with a decision, the decision wins and the design says so.
- One production release; many staging promotions; GitHub repo = source of truth; CI (Trusted Publisher OIDC) is the only production writer; staging Space + 16-token canary + rollback.
- Claude is the single writer; the other agent is stopped (its Windows scheduled tasks may still fire — guard for it).
- Outward-facing actions (GitHub repo creation, Space creation/duplication, secrets, deploys, paid HF Jobs, provider spend) never happen unattended: they become checkpoint/promotion requests the owner executes or explicitly approves between runs.
- No secret may appear in any prompt, trigger message, log, journal, commit or artifact; tokens reach tools only through environment/secret files that are never echoed.
- The build tree must live on a durable path (never the /tmp scratchpad); the cwd repo /workspaces/agent-skills-toolchain must never be mutated by build agents; its CLAUDE.md does not apply to the Space build.
- Python 3.12 for everything the Space runs; LF line endings; pinned library sources under the scratchpad `libsrc/` must be consulted for any gradio/spaces/transformers API claim (or re-downloaded to a durable path).
- The persona boundary: nothing in the workflow authors or restores the clause about wording prompts to get past other AI systems' filters.
- Test authors ≠ implementers; verifiers/auditors/critics/judges are fresh-context agents that never author what they judge; refute-first with mandatory reproduction; deterministic gates decide, LLM judges can only veto.
- Every loop is bounded (max rounds, dry counter, budget reserve) and every exhaustion is a typed `blocked` result, never a silent drop; no silent caps anywhere (log what was dropped).
- Everything the workflow produces is written to durable files under the build repo or the grill folder (both auto-synced to GitHub); the synthesizer reads artifacts, never self-reports.

## Required sections of a design document (identical structure for all three, so judges compare like with like)
1. Adopted principles (ids) and how conflicts between lenses were resolved.
2. Run structure: one script, several `args.stage` runs with an owner checkpoint between runs; for each run: preconditions, what it produces, the checkpoint object it emits.
3. Agent roles and the separation table (who may author, who may vote, effort per role).
4. Task model: the schema of a PR-sized task, how the plan's steps become tasks, DAG/waves, sizing rules, worktree → branch → bundle/SHA lifecycle, integration order, conflict-resolution agent, integration-test agent.
5. Inner loop per task (test author → confirm-RED → implementer → gate → fresh verifier → refuter → bounded fixer → judge) with exact counters and exit conditions.
6. Outer loop per wave and for the whole tree (review → refute → judge panel `satisfied`; dry counter; MAX_ROUNDS; budget reserve).
7. Deterministic gates: exact `gate.sh` contents and where each runs (in-worktree pre-merge, on the merged tree, from a clean checkout).
8. Testability table: proven locally (stub engine, unit, import smoke, gradio_client) vs requires staging Space vs requires the owner; how staging/promotion requests are represented.
9. Schemas for every stage (JSON Schema, required ⊆ properties, enum verdicts, `sha` wherever code was read).
10. Replay/resume, null-result, safeguard-kill and concurrency handling (cap 2 vs cap 14: wave sizing from `args`).
11. Budget and effort plan by role; estimated agent counts and wall-clock at cap 2 and at cap 14.
12. COVERAGE MATRIX: every F-1..F-47 and every anti-pattern from all lenses → guard → phase; unguardable → explicit owner checkpoint.
13. JavaScript skeletons: `meta` pure literal, `args` contract, helpers, every loop (plain JS; no Date.now/Math.random; stable prompts; sorted ids).
14. Authoring checklist the script author ticks before launch.
15. Open questions for the owner (only those whose answer changes the build).
