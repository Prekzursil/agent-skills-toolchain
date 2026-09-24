# Phase 2 Prep — Dependabot PR Triage

**Status:** Initial scan and planning  
**Target:** Merge all identified Dependabot PRs once main is green from Phase 1

## Dependabot PRs to Triage

The following PRs require review, rebase, local test, and merge sequencing (scanned 2026-09-24):

### Tier 1: Security-Critical Dependency Updates

| PR | Package | Type | Current | Proposed | Status |
|----|---------|------|---------|----------|--------|
| #338 | hono | npm | 4.13.1 | 4.13.8 | Open (hacktricks-mcp-server) |
| #340 | fast-uri | npm | 3.1.5 | 3.1.8 | Open (hacktricks-mcp-server) |
| #342 | qs | npm | 6.15.3 | 6.16.0 | Open (hacktricks-mcp-server) |
| #345 | @types/node | npm | 26.2.0 | 26.6.1 | Open (hacktricks-mcp-server, dev) |

### Tier 2: Cross-Repo Updates (Browser Bridge)

| PR | Package | Type | Current | Proposed | Status |
|----|---------|------|---------|----------|--------|
| #339 | qs | npm | 6.15.3 | 6.16.0 | Open (browser-bridge/chrome-bridge-mcp) |
| #341 | fast-uri | npm | 3.1.5 | 3.1.8 | Open (browser-bridge/chrome-bridge-mcp) |
| #346 | ws | npm | 8.21.1 | 8.21.3 | Open (browser-bridge/chrome-bridge-mcp, minor-patch) |
| #347 | zod | npm | 3.25.76 | 4.6.5 | Open (browser-bridge/chrome-bridge-mcp) |
| #348 | typescript | npm | 5.9.3 | 7.0.2 | Open (browser-bridge/chrome-bridge-mcp, dev) |

### Tier 3: Build & CI Updates

| PR | Package | Type | Current | Proposed | Status |
|----|---------|------|---------|----------|--------|
| #343 | uv | toolchain | N/A | update | Open (uv group across 3 directories) |
| #344 | GitHub Actions | ci | N/A | updates | Open (actions-all group with 3 updates) |

## Phase 2 Actions

### 1. Identify PR Details
- [ ] Fetch PR metadata for each number
- [ ] Determine dependency types (npm, python, GitHub Actions, etc.)
- [ ] Identify any conflicts or interdependencies
- [ ] Check for existing test results

### 2. Rebase if Needed
- [ ] Pull latest from main
- [ ] Rebase each PR branch onto current main if behind
- [ ] Resolve any conflicts
- [ ] Push rebased branches

### 3. Run Local Checks
- [ ] ruff lint/format check
- [ ] type checking (basedpyright for Python)
- [ ] test coverage (pytest for Python, npm test for Node)
- [ ] security scanning (gitleaks, osv-scanner)

### 4. Determine Merge Order
- [ ] Build dependency graph of PRs
- [ ] Identify safe merge sequences
- [ ] Document any ordering constraints
- [ ] Plan merge-once-green strategy

## Blocking Dependencies

Phase 2 can start after Phase 1 completes:
- [ ] Three consecutive green quality.yml runs on main
- [ ] Branch protection configured (if required for merge)
- [ ] Self-hosted runner online and functional (if needed)

## Notes

- Dependabot PRs may have been created weeks ago; main may have diverged
- Some PRs may conflict with each other
- Security/vulnerability fixes may have priority
- Avoid force-pushing to Dependabot PRs (Dependabot manages them)

---

Next: Fetch detailed information on each PR to populate the table above.
