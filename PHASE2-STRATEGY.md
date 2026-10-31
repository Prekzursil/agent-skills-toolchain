---
title: PHASE2-STRATEGY
type: note
permalink: dqverify-repo-20261013/phase2-strategy
---

# Phase 2 Strategy — Dependabot PR Merge & Dependency Hardening

**Timeline:** Execute once Phase 1 achieves 3 consecutive green quality.yml runs  
**Scope:** Merge identified Dependabot PRs; achieve clean dependency gate  
**Governance:** osv-scanner.toml defines all active ignores (2 reasoned ignores as of 2026-09-24)

## Current Dependency State

### Active Ignores (Reasoned & Dated)

| CVE/GHSA | Package | Status | Exit Condition |
|----------|---------|--------|-----------------|
| GHSA-67mh-4wv8-2f99 | esbuild (vendored ralph-orchestrator) | Unfixable without breaking change | Re-vendor ralph when drizzle-kit 1.0 stable released |
| GHSA-82fw-gwwq-j7x9 | vitest (vendored ralph-orchestrator) | Dev-only in CI execution | Re-vendor ralph-orchestrator to safe vitest version |

### Lockfiles Under Scan

1. `package-lock.json` (root npm tree)
2. `tools/mcp/hacktricks-mcp-server/package-lock.json` (hardened MCP)
3. `browser-bridge/chrome-bridge-mcp/package-lock.json` (browser bridge)
4. `tools/editor/ralph-orchestrator/vendor/package-lock.json` (vendored upstream snapshot)

**Policy:** Every lockfile is committed and scanned. Clean-zero is the target; ignores are only for genuinely-unfixable vulnerabilities with dated review notes.

## Phase 2 Priority PRs

### Tier 1: Critical Dependency Updates
These require immediate merge (likely High/Critical CVSS):
- PR #338-#343: Batch updates (TBD on specifics)
- PR #351: Single update (TBD on specifics)

### Tier 2: Security Updates
- PR #344: Single update (TBD on specifics)

### Tier 3: Linked/Coordinated Updates
- PR #315/#324: Linked PRs (may have merge dependencies)

### Tier 4: Standard Dependency Upgrades
- PR #311: Single update (TBD on specifics)

## Execution Checklist

### Before Phase 1 is Green
- [ ] Document each PR's dependency changes
- [ ] Identify merge order constraints
- [ ] Note any package.json vs lockfile-only updates
- [ ] Verify no branch conflicts with current main

### When Phase 1 Reaches Green
1. **Verify Phase 1 Success**
   - [ ] 3 consecutive green quality.yml runs confirmed
   - [ ] All 8 gates passing (lint, types, tests×2, secrets, deps, sast, platform-audit)
   - [ ] Self-hosted runner functional (if deployed)

2. **Prepare Merge Pipeline**
   - [ ] Rebase each Dependabot PR onto current green main
   - [ ] Run local checks on each PR:
     - ruff lint/format
     - basedpyright type check (Python packages)
     - pytest coverage (Python)
     - npm test (Node workspaces)
     - gitleaks (secrets)
     - osv-scanner (dependencies)
   - [ ] Verify no new CVEs introduced by upgrades

3. **Execute Merge Sequence**
   - [ ] Merge in dependency order (lowest-level deps first)
   - [ ] Watch for test failures
   - [ ] If blocker found: revert, document, defer to next phase
   - [ ] Confirm main stays green after each merge

4. **Confirm Phase 2 Complete**
   - [ ] All identified Dependabot PRs merged or explicitly deferred
   - [ ] Quality gates still green
   - [ ] No regressions in security/performance gates
   - [ ] Dependency vulnerability count unchanged or decreased

## Known Constraints

1. **Vendored ralph-orchestrator tree:**
   - Contains 2 reasoned ignores (esbuild, vitest)
   - Upstream snapshots may have stale dependencies
   - Re-vendoring requires manual intervention

2. **Dependabot PR workflow:**
   - Do NOT force-push to Dependabot branches (Dependabot manages them)
   - Rebase via merge commits, not force-push
   - If PR drifts, Dependabot may regenerate it

3. **Security scanning:**
   - osv-scanner runs with explicit --config=osv-scanner.toml
   - No per-lockfile config; ignores apply repo-wide
   - Audit findings must satisfy "genuinely unfixable" policy

## Decision Points

### If a PR Introduces New Vulnerabilities
- Do not merge that PR
- Document the finding in this file
- Flag for owner review
- Consider if osv-scanner ignore is warranted (unlikely)

### If PRs Have Merge Conflicts
- Likely due to simultaneous dependency updates
- Rebase conflicts resolve via newer lock file generation
- May require coordinated npm/npm install cycle

### If Phase 1 Green is Delayed Beyond Oct 1, 2026
- GitHub billing cycle resets
- Re-assess whether actions minutes are needed
- Self-hosted runner may come online
- Revisit merge strategy if new minutes available

## Success Criteria

Phase 2 is complete when:
- ✅ All identified Dependabot PRs reviewed, tested, and merged (or explicitly deferred)
- ✅ quality.yml gates remain green after all merges
- ✅ No new security vulnerabilities introduced
- ✅ Dependency vulnerability count same or improved
- ✅ No regressions in type checking, tests, or audit gates

---

## Next: Fetch PR Details

Once Phase 1 is green, pull latest PR status for the 5 PR numbers listed above.