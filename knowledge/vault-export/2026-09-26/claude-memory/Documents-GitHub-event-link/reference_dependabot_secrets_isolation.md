---
name: dependabot secrets isolation breaks zero gates
description: GitHub Actions doesn't pass repo Actions secrets to dependabot/* branches
  by default — Sonar/Codacy/QLTY/Sentry zero gates cascade-fail on dependabot PRs
  until Dependabot secrets are populated separately.
type: reference
originSessionId: 7e07bd36-c338-4890-8179-e112e67d5844
permalink: main/claude-memory/documents-git-hub-event-link/reference-dependabot-secrets-isolation
---

When SonarCloud Scan / Sonar Zero / Codacy Zero / QLTY Zero / Sentry Zero / Quality Secrets Preflight all fail on a dependabot PR with empty token errors (`Project not found... 'SONAR_TOKEN'`), the cause is **dependabot secrets isolation**, not a code defect.

GitHub Actions has two separate secret namespaces:
- Settings → Security → Secrets and variables → **Actions** (used for normal pushes/PRs)
- Settings → Security → Secrets and variables → **Dependabot** (used only for dependabot/* branches)

**Why:** Anyone with write access to the repo can craft a workflow modification, so passing repo secrets to dependabot-triggered runs would let a malicious dependabot manifest or transitively-owned package exfiltrate credentials. Dependabot got its own namespace as a security measure.

**How to apply:**
- When triaging "alert:fleet-bump-fail" on a dependabot PR, look at the SonarCloud Scan log first. If it says `SONAR_TOKEN: <empty>` or `Project not found`, this is the pattern — don't chase code-level fixes.
- Check if genuine code-level checks pass: verify, Coverage 100 Gate, CodeQL, Semgrep, DeepScan, DeepSource Visible Zero, Dependency Alerts, Quality Rollup. If all green, the PR is safe to admin-merge.
- Operator fix is per-repo: copy every secret used by the QZP shared-scanner-matrix from the Actions namespace to the Dependabot namespace.
- Tracked in QZP issue #184 (filed 2026-04-28).

**Distinguishing pattern (compared to other operator-blocked failures):**
| Failure shape | Likely cause |
|---|---|
| SONAR_TOKEN empty + Project not found | Dependabot secrets isolation (this pattern) |
| 404 on PR scope race | QZP #169 - Sonar Zero gate races SonarCloud Scan workflow |
| Codecov 0% on flag | Codecov backend ingestion stuck (devextreme #24, airline #56) |
| DeepSource cached "fail" state | DeepSource analyzer reset needed (QZP #165) |