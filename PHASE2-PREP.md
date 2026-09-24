# Phase 2 Prep — Dependabot PR Triage

**Status:** Initial scan and planning  
**Target:** Merge all identified Dependabot PRs once main is green from Phase 1

## Dependabot PRs to Triage

The following PRs require review, rebase, local test, and merge sequencing:

| PR | Type | Branch | Status |
|----|------|--------|--------|
| #338-#343 | Batch | Multiple | TODO: Scan for details |
| #344 | Single | TBD | TODO: Scan for details |
| #351 | Single | TBD | TODO: Scan for details |
| #315/#324 | Linked | TBD | TODO: Scan for details |
| #311 | Single | TBD | TODO: Scan for details |

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
