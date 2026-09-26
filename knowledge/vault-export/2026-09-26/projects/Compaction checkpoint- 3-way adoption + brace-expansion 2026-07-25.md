---
title: 'Compaction checkpoint: 3-way adoption + brace-expansion 2026-07-25'
type: report
permalink: main/projects/compaction-checkpoint-3-way-adoption-brace-expansion-2026-07-25
tags:
- compaction-checkpoint
- agent-skills-toolchain
- adoption
- cyberstrike
- hacktricks
- complete
---

# COMPLETE — agent-skills-toolchain 3-way adoption + brace-expansion (2026-07-25)

Repo: Prekzursil/agent-skills-toolchain. Final main = f22c256. Ran under `/loop` (10h autonomous). **All agent-doable work DONE; loop stopped (out of goals). Only operator human-gates remain.**

## LANDED ON MAIN (all verified via gh+git, CI green)
- **#188 workflow-harness** — governed-run orchestrator template + validation test vendored into skills/workflow-authoring (dual-write). Merged.
- **#186 cyberstrike** — license-neutral skill wrapper + 4 default-off companion MCP declarations (cloud-audit/github-security/osint/cve-mcp) in canonical-mcp-servers.json + adoption docs. Merged. RUNTIME also installed on the box: cyberstrike@1.1.15 CLI (postinstall reviewed clean), Chromium, Bun 1.3.11, cloud-audit-mcp cloned @e32c53a1 to ~/.local/opt (inert/default-off, 1 bun postinstall left blocked). ~/.mcp.json backed up. Held at guard line: nothing promoted/enabled.
- **#187 hacktricks** — real MCP server runtime (7 tools, 100% cov, 71 tests) on main (15 src files). Merged (squash 47aaa38). NOTE: repo AUTO-MERGED #187 at 0dc8476 before my adversarial critic finished + before my CI-wire commit landed.
- **#197 hacktricks CI-wire** — the critic FAILED #187 on a real vacuous-gate: the package was absent from CI so gate-tests-coverage silently skipped its 71 tests. Follow-up PR #197 added an explicit `gate-tests-coverage hacktricks-mcp-server` step (mirrors agentify-desktop) — VERIFIED the step now runs green (job step `-> success`, 100% enforced). Merged. Vacuous gate closed.
- **#192 brace-expansion** — forced brace-expansion->5.0.8 via overrides in tools/web/agentify-desktop (GHSA-mh99-v99m-4gvg ReDoS on dev deps 1.1.16+2.1.2). Merged. (#191 added a temp ignore by the auto-process; #194 retired it after my real fix.)

## OPERATOR HUMAN-GATES REMAINING (NOT agent-doable — handed back, not faked)
- **cyberstrike G3 promote** (needs ALL Claude closed): promote-mcp-userscope.ps1 -DryRun then -Yes + merge docs/cyberstrike-adoption/default-off-fragment.json into ~/.claude/.mcp-disabled-defaults.json. **G5 guard** (fail-closed HMAC gateway + Claude-side MCP guard) MUST be built before enabling any of the 4 companion MCPs — user chose "stop at guard line" (option 1), NOT to build the guard now. G4: run cyberstrike TUI. cloud-audit blocked-postinstall: review via `bun pm untrusted` at enable-time.
- **hacktricks**: corpus -> D:\knowledge\hacktricks; deploy install-hacktricks-mcp-server.ps1; promote (Claude closed); live tools/list==7.

## KEY LESSONS
- Read the actual detector output before acting (brace-expansion: I first bumped 5.0.7 which wasn't even flagged; osv flagged 1.1.16+2.1.2; real fix = override to 5.0.8).
- This repo has an AUTO-MERGE process for green PRs (merged #185/#187/#190/#191/#194 without me) — a critic can finish AFTER the PR merges; wire CI gates INTO the PR before it can go green, or the vacuous-gate lands on main.
- git show ref:path MSYS-mangles->empty (use ls-tree+cat-file). Box has npm allow-scripts + bun untrusted-postinstall guards (review then allow-once). mergeStateStatus CLEAN hides PR-overlap (verify index/marketplace merges preserve sibling routes).
