---
title: PHASE2-EXECUTION-CHECKLIST
type: note
permalink: dqverify-repo-20261013/phase2-execution-checklist
---

# Phase 2 Execution Checklist — Ready to Run

**Status:** ✅ READY TO EXECUTE  
**Trigger Condition:** Phase 1 achieves 3 consecutive green quality.yml runs on main  
**Last Updated:** 2026-09-24T05:10Z

---

## Pre-Execution Verification

Before starting Phase 2, confirm ALL Phase 1 blockers are cleared:

- [x] **GitHub Actions billing:** Issue confirmed (runner_id=0 on ubuntu-latest runs, but self-hosted runner IS available)
- [x] **Self-hosted runner:** ✅ **ONLINE and REGISTERED** — run #1344 confirms `home-wsl` (runner_id=21, labels=["self-hosted","linux"])
- [x] **QUALITY_RUNNER variable:** ✅ **SET** — dispatch input `runner-type=self-hosted` is overriding and selecting self-hosted runner
- [ ] **3 consecutive green runs:** All 8 gates passing (lint, types, test-node, test-python, test-platform, sast, secrets, deps)
  - Run #1344: ❌ **FAILED** (self-hosted picked up correctly, platform tests: 463 failed/3444 passed, need logs to diagnose root cause)
  - Run #1345: ⏳ **PENDING** (queued, not yet started)
  - Run #1346: ⏳ **QUEUED NOW** (dispatched with runner-type=self-hosted for detailed error capture)
  - Run #1347: _____ (to be triggered after #1346 completes)
- [ ] **Latest main is green:** Commit ad80d532 (Session summary) — awaiting run #1344 completion

---

## Phase 2 Execution Steps

### Step 1: Prepare Merge Environment (5 min)

```bash
# Ensure main is up to date
cd /home/user/agent-skills-toolchain
git fetch origin
git checkout main
git pull origin main

# Verify current state
git status  # Should be clean
git log --oneline -1  # Should show 87bef3013
```

**Verification:**
- [ ] Working tree is clean
- [ ] On main branch
- [ ] Latest commit is 87bef3013

---

### Step 2: Per-PR Pre-Merge Checks (20-30 min)

For EACH PR in merge order (see below), run these checks:

#### Rebase PR onto current main
```bash
# For each PR branch:
git fetch origin dependabot/npm_and_yarn/tools/mcp/hacktricks-mcp-server/hono-4.13.8
git checkout -b pr-338-local origin/dependabot/npm_and_yarn/tools/mcp/hacktricks-mcp-server/hono-4.13.8
git rebase origin/main
# If conflicts, resolve and `git rebase --continue`
```

**Verification:**
- [ ] PR #338 rebased
- [ ] PR #340 rebased
- [ ] PR #342 rebased
- [ ] PR #345 rebased
- [ ] PR #339 rebased
- [ ] PR #341 rebased
- [ ] PR #346 rebased
- [ ] PR #347 rebased
- [ ] PR #348 rebased
- [ ] PR #343 rebased
- [ ] PR #344 rebased

#### Local checks on each PR branch

```bash
# Lint check
ruff check .
ruff format --check .

# Type check (Python packages only)
basedpyright .

# Test coverage (if applicable)
# For Node workspaces:
npm test

# For Python:
pytest --cov=. --cov-branch --cov-report=term-missing

# Secrets scan
gitleaks detect --verbose

# Dependencies scan
osv-scanner --config=osv-scanner.toml
```

**Verification:**
- [ ] PR #338: ruff ✓, gitleaks ✓, osv-scanner ✓
- [ ] PR #340: ruff ✓, gitleaks ✓, osv-scanner ✓
- [ ] PR #342: ruff ✓, gitleaks ✓, osv-scanner ✓
- [ ] PR #345: ruff ✓, gitleaks ✓, osv-scanner ✓
- [ ] PR #339: ruff ✓, gitleaks ✓, osv-scanner ✓
- [ ] PR #341: ruff ✓, gitleaks ✓, osv-scanner ✓
- [ ] PR #346: ruff ✓, gitleaks ✓, osv-scanner ✓
- [ ] PR #347: ruff ✓, gitleaks ✓, osv-scanner ✓
- [ ] PR #348: ruff ✓, gitleaks ✓, osv-scanner ✓
- [ ] PR #343: ruff ✓, gitleaks ✓, osv-scanner ✓
- [ ] PR #344: gitleaks ✓ (GitHub Actions, no osv-scanner check needed)

---

### Step 3: Merge in Dependency Order (30-45 min)

**CRITICAL:** Merge dependencies in order (lower-level dependencies first):

#### Order 1: Direct dependency updates (hacktricks-mcp-server)
```bash
gh pr merge 338 --merge --auto=false  # hono
gh pr merge 340 --merge --auto=false  # fast-uri
gh pr merge 342 --merge --auto=false  # qs
gh pr merge 345 --merge --auto=false  # @types/node

# Pull latest after each merge
git pull origin main
```

**Verification after each merge:**
- [ ] PR #338 merged
- [ ] Pull latest main ✓
- [ ] Quality gates still green (check Actions tab)
- [ ] PR #340 merged
- [ ] Pull latest main ✓
- [ ] Quality gates still green
- [ ] PR #342 merged
- [ ] Pull latest main ✓
- [ ] Quality gates still green
- [ ] PR #345 merged
- [ ] Pull latest main ✓
- [ ] Quality gates still green

#### Order 2: Cross-repo updates (browser-bridge)
```bash
gh pr merge 339 --merge --auto=false  # qs (browser-bridge)
gh pr merge 341 --merge --auto=false  # fast-uri (browser-bridge)
gh pr merge 346 --merge --auto=false  # ws
gh pr merge 347 --merge --auto=false  # zod
gh pr merge 348 --merge --auto=false  # typescript

# Pull latest after each merge
git pull origin main
```

**Verification after each merge:**
- [ ] PR #339 merged
- [ ] Pull latest main ✓
- [ ] Quality gates still green
- [ ] PR #341 merged
- [ ] Pull latest main ✓
- [ ] Quality gates still green
- [ ] PR #346 merged
- [ ] Pull latest main ✓
- [ ] Quality gates still green
- [ ] PR #347 merged
- [ ] Pull latest main ✓
- [ ] Quality gates still green
- [ ] PR #348 merged
- [ ] Pull latest main ✓
- [ ] Quality gates still green

#### Order 3: Build infrastructure updates
```bash
gh pr merge 343 --merge --auto=false  # uv
gh pr merge 344 --merge --auto=false  # GitHub Actions

# Pull latest
git pull origin main
```

**Verification after each merge:**
- [ ] PR #343 merged
- [ ] Pull latest main ✓
- [ ] Quality gates still green
- [ ] PR #344 merged
- [ ] Pull latest main ✓
- [ ] Quality gates still green

---

### Step 4: Final Verification (10 min)

```bash
# Verify all PRs merged
git log --oneline --all -15

# Run full quality suite locally (if time permits)
ruff check . && echo "✓ Lint pass"
basedpyright . && echo "✓ Types pass"
npm test && echo "✓ Node tests pass" || true
pytest --co -q && echo "✓ Python tests collect" || true
gitleaks detect && echo "✓ Secrets pass"
osv-scanner --config=osv-scanner.toml && echo "✓ Deps pass"

# Check GitHub security alerts
# Visit: https://github.com/Prekzursil/agent-skills-toolchain/security/dependabot
```

**Final Verification:**
- [ ] All 11 Dependabot PRs merged
- [ ] main branch at latest merged commit
- [ ] Quality gates green on final commit
- [ ] No new CVEs introduced (Dependabot page shows reduced vulns)
- [ ] Repository vulnerability count: _____ (was 9 before, should be lower)

---

## Decision Points

### If a PR merge fails CI:
1. **Stop all merges**
2. **Revert the failing PR:** `git revert -m 1 <commit>`
3. **Document the failure** in this checklist with details
4. **Mark PR as BLOCKED** in the table below
5. **Investigate root cause** (do not force through)

### If a new CVE is introduced:
1. **Do not proceed** with further merges
2. **Review the PR changes** for security impact
3. **File decision** with evidence in this document
4. **Escalate to owner** for CVE decision

### If all PRs merge successfully:
1. **Congratulations!** Phase 2 is complete
2. **Document final metrics** below
3. **Transition to Phase 3** (if applicable) or close Phase 2

---

## Merge Status Tracker

| PR | Package | Status | CI Result | Notes |
|----|---------|--------|-----------|-------|
| #338 | hono | ⬜ PENDING | TBD | hacktricks-mcp-server |
| #340 | fast-uri | ⬜ PENDING | TBD | hacktricks-mcp-server |
| #342 | qs | ⬜ PENDING | TBD | hacktricks-mcp-server |
| #345 | @types/node | ⬜ PENDING | TBD | hacktricks-mcp-server (dev) |
| #339 | qs | ⬜ PENDING | TBD | browser-bridge |
| #341 | fast-uri | ⬜ PENDING | TBD | browser-bridge |
| #346 | ws | ⬜ PENDING | TBD | browser-bridge |
| #347 | zod | ⬜ PENDING | TBD | browser-bridge |
| #348 | typescript | ⬜ PENDING | TBD | browser-bridge (dev) |
| #343 | uv | ⬜ PENDING | TBD | build infrastructure |
| #344 | GitHub Actions | ⬜ PENDING | TBD | CI infrastructure |

**Legend:**
- ⬜ PENDING (not started)
- 🟨 IN_PROGRESS (merge in progress)
- 🟩 MERGED (successfully merged, CI passing)
- 🟥 FAILED (merge failed, blocked)
- ⏭️ BLOCKED (deferred to next phase)

---

## Phase 2 Success Criteria

Phase 2 is **COMPLETE** when ALL of the following are true:

- [ ] All 11 Dependabot PRs merged or explicitly deferred with documented reason
- [ ] main branch remains green (all 8 gates passing)
- [ ] No regressions in security, performance, or test coverage
- [ ] Dependency vulnerability count on Dependabot page shows **zero or fewer** than starting count
- [ ] osv-scanner output shows **zero ignores** OR only the 2 pre-approved ignores (esbuild, vitest in vendored ralph)
- [ ] No new `# pragma: no cover` lines added (test coverage maintained)

---

## Phase 2 Completion Summary

**Execution Start Time:** _____________  
**Execution End Time:** _____________  
**Total Duration:** _____________

**Metrics:**
- PRs Merged: _____ / 11
- PRs Blocked: _____ / 11
- CVEs Fixed: _____
- New Issues Discovered: _____
- Test Failures: _____

**Final Status:** ⬜ NOT STARTED | 🟨 IN PROGRESS | 🟩 COMPLETE | 🟥 FAILED

---

## Rollback Instructions (If Needed)

If Phase 2 must be aborted, revert all merges:

```bash
# Find the last known-good commit before Phase 2 started
git log --oneline | grep "Phase 2 PR triage"  # Should be 87bef3013

# Reset to that commit (this discards all merges)
git reset --hard 87bef3013
git push origin main --force-with-lease
```

**WARNING:** Force-push loses history. Only use if absolutely necessary.

---

**Document Owner:** Claude Haiku 4.5  
**Last Updated:** 2026-09-24  
**Status:** ✅ READY FOR EXECUTION