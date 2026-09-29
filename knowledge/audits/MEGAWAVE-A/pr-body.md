# McpHub multi-client consolidation (preserved + classified)

## What this PR is

This branch (`fix/mcp-hub-multi-client-sticky-2026-09-24` work, HEAD `d9e1ce4b4`) preserves FEATURE work recovered from an unattended working tree on the mega-wave branch, classified file-by-file on 2026-09-28 before committing. Nothing here was hand-merged or re-authored: each path was read and binned as FEATURE (harness-capability source/docs/tests), MACHINE (local runtime state), or EXCLUDE (regenerable/junk/banned-pattern).

## What is NOT in this PR (deliberate)

- All 141 tracked modifications/deletions under `browser-profiles/**` remain UNCOMMITTED in the working tree. The lane's git rules ban committing any path matching `browser-profiles` (also `secrets|*token*|*.pem|*.key|node_modules`). Because the ONLY tracked machine-state changes in the tree are browser-profiles, the planned machine-state snapshot commit was skipped entirely — there is nothing committable in that class.
- Untracked local state also stays uncommitted: `.video_agent/` (plugin-cache pointer), `.worktrees/` (nested worktree checkouts — never commit nested git trees), `harness-audits/health/` (daily telemetry JSON + reap-log), `zai-lanes/.remember/`, `zai-lanes/mitm_mcp_traffic.db`, `zai-lanes/.video_agent`, `zai-lanes/out/` (empty), `command-center/p2-wave/_r2_tmp/`, and `command-center/p2-wave/probes/IMP-0003/` (probe fixture junk; contains a `node_modules/` path — banned).

## Classification counts

- COMMITTED as FEATURE (commit `d9e1ce4b4`): **30 files, +1,935 lines** across 17 paths:
  - Delegation-program docs: `.agents/GRILL-DECISIONS_workflow-delegation_2026-09-22.md`, `.agents/HARNESS-COMMIT-PLAN_2026-09-22.md`, `.agents/PROGRAM-REPORT_2026-09-22.md`
  - Restricted agent pair: `agents/reader.md`, `agents/writer.md`
  - Command: `commands/pvc-verify.md`
  - Depth-dial probe: `docs/PROBE-depth-dial.md` + `docs/probe-g7a-evidence/` (8 files)
  - Golden harness-contract reference: `golden/AGENTS.md` + `golden/SHA256.txt`
  - Guard hook: `hooks/claude-code-mcp-guard/` (7 files: guard.py, selftest.py, verify-entry.ps1, validate-and-pipetest.ps1, mirror-to-repo.ps1, BOTH-STATES-VERIFICATION + SELFTEST-EVIDENCE docs)
  - Rules: `rules/common/mcp-process-hygiene.md`, `rules/common/native-capability-map.md`
  - ZAI lane sources: `zai-lanes/claude-free.cmd`, `zai-lanes/glm-free-shim.py`, `zai-lanes/register-zai-guard.ps1`, `zai-lanes/zai-bridge-guard.ps1`
- 18 ambiguous entries from the pre-pass were each read and resolved: 12 → FEATURE (committed above), 6 → EXCLUDE with reasons (`.video_agent/`, `.worktrees/`, `_r2_tmp/`, IMP-0003 fixture, harness-audits/health, zai-lanes state files).
- Excluded machine/untracked: 141 tracked browser-profiles entries + 55 untracked browser-profiles entries + the state dirs listed above.
- Pre-add safety: secret-shape scan (sk-/hf_/ghp_/AKIA/xox/glpat/PEM blocks + key=value credential-assignment patterns) over the entire staged set: NO hits. Banned-filename filter: NO hits. (VERIFIED, grep receipts in lane artifact.)

## Merge gate (before this PR leaves draft)

1. CI green on the PR head.
2. Adversarial review (independent reviewer, fresh context) of the diff.
3. No-downgrade check: confirm no capability downgrade vs main (owner rule: never silently remove a feature/downgrade capability).

## Provenance

Work was authored 2026-09-22 during the workflow-delegation program (`wf_c8e4c79c-1c8`) and sat uncommitted in an unattended working tree. Classified and committed 2026-09-28 by the MEGAWAVE-A lane. Draft PR — DO NOT MERGE until the merge gate passes.
