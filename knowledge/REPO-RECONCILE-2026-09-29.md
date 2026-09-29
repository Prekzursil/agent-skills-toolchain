# Toolchain repo reconcile — 2026-09-29 11:30 UTC snapshot

**Open PRs (15):** #363 deps-fix osv (fresh today) · #362 git-crypt removal v2 · **#359 McpHub multi-client consolidation (DRAFT — pairs with tonight's daemon repair; the sticky-fix chain below feeds it)** · **#353 hooksmoke E5 — hook-firing measurement (seed of the harness-bench program)** · #348/#347/#345 dependabot (chrome-bridge TS7/zod4/ws, hacktricks @types) · #336 grill docs WIP · #330-#335 IMP waves (6 DRAFT/BLOCKED — stale 09-08, classify: merge-vs-close).

**Local branches (12+):** add-databricks-fanout-harness · agent/detector-fix-fp · backup/sticky-57f4c924a · chore/* ×8 (deps, enshrine-runtime-config, harness-reconcile, hygiene-academic ×2, retire-brace, reunite-mcp-control-plane, statusline) — classify each: PR-backed / local-only / mergeable / dead.

**FINDING-1 (ALWAYS-PUSH violation):** 8 commits on local branches with NO remote twin:
57f4c924a sse-transport-for-McpHub-gateway · 06b5b0e44 cursor/grok-targets+sync · 911caeeb1 sticky-multi-client-SSE+park-heavy-stdio · d750e8251 Grok-Stop-hook-reentry · 6a2f95e1a+f70e1c401+4c95ad0c6+23d609c5d (skills mirrors + manifests).
Per AGENTS-RUNTIME §9 ALWAYS-PUSH: these can be LOST. Owner decision: push branches as-is (safe, non-merging) — flagged, NOT executed post-VM-incident (agent discipline: no unreviewed remote actions today).

**FINDING-2 (uncommitted deletions):** working tree holds mass deletions under browser-profiles/chrome-agent/ (ActorSafetyLists, CertificateRevocation, Crowd Deny...). Unstaged, uncommitted, unexplained in-session. Verify intentional (profile slimming?) before any commit — do NOT blindly commit or restore.

**FINDING-3 (stale draft waves):** IMP PRs #330-#335 all DRAFT/BLOCKED since 09-08 — 3 weeks stale; classify abandon-vs-land at next session.

RECALL: reconcile-all-branches-prs skill exists for exactly this. DEPS: dependabot PRs are auto-managed; McpHub chain feeds #359.

RECALL: gh pr list + git branch/log live snapshot 2026-09-29 11:30 (this doc IS the receipt); vault: workspace-curation-2026-06-11 + reconcile-all-branches-prs skill
DEPS: PRs #330-#335 feed the IMP waves (6 DRAFT); #359+sticky-chain feed McpHub (74-server registry, repaired tonight); #353 feeds harness-bench; browser-profile deletions uncommitted — no downstream consumer until verified
