---
name: event-link main green-gate blocker
description: Why event-link main was red on Quality Zero gates and how both stages
  cleared
type: project
originSessionId: 7e07bd36-c338-4890-8179-e112e67d5844
permalink: main/claude-memory/documents-git-hub-event-link/project-eventlink-main-blocker
---

Event-link main's `Quality Zero Gate` was red for months across the QZP rollout. The chain had two stages, both now resolved.

## Stage 1 — SonarCloud Auto-Analysis vs CI conflict (RESOLVED 2026-04-27 ~03:00Z)

**Symptom:** `Coverage 100 Gate` step `SonarCloud scan` failed with:
> `ERROR You are running CI analysis while Automatic Analysis is enabled. Please consider disabling one or the other.`
> `##[error]Action failed: The process '/opt/.../sonar-scanner' failed with exit code 3`

**Why:** SonarCloud project at `https://sonarcloud.io/project/configuration?id=Prekzursil_event-link` had Automatic Analysis enabled, racing against the platform's reusable workflow's `sonar-scanner` push.

**How fixed:** Operator UI toggle:
1. `https://sonarcloud.io/project/configuration?id=Prekzursil_event-link`
2. Administration → Analysis Method
3. Set to "GitHub Actions / Continuous Integration" (disable Automatic Analysis)

**API verified:** `GET /api/settings/values?keys=sonar.autoscan.enabled` returns `"value":"false"` (was `"true"`). No public API for this toggle — UI-only by design. `api/settings/set` returns `Setting cannot be set on a Project`; `api/v2/analysis/automatic_analysis` returns 405.

## Stage 2 — SonarCloud "0% Coverage on New Code" (RESOLVED 2026-04-27 ~03:37Z, PR #131 merged)

**Symptom (post-Stage-1 CI run, run 24974719702):**
- `shared-scanner-matrix / Coverage 100 Gate`: ✅ success (Stage 1 cleared)
- `aggregate-gate / Quality Zero Gate`: ❌ failure
- `SonarCloud Code Analysis` check: ❌ `Failed conditions: 0.0% Coverage on New Code`

**Why:** `sonar-project.properties` had sources/tests/exclusions but **no** `sonar.python.coverage.reportPaths` or `sonar.javascript.lcov.reportPaths`. The CI workflow already produced coverage at `backend/coverage.xml` and `ui/coverage/lcov.info`, but Sonar didn't know to read them, so its `new_coverage >= 80%` quality-gate condition saw 0%.

**How fixed:** PR #131 added the two `reportPaths` settings pointing at the existing artefacts:
```properties
sonar.python.coverage.reportPaths=backend/coverage.xml
sonar.javascript.lcov.reportPaths=ui/coverage/lcov.info
```

No workflow change needed. PR #131 merged at 03:37:50Z.

**API verified post-merge:** SonarCloud Code Analysis check on the merge commit reports SUCCESS for the first time since QZP rollout.

## Stage 3 — Sonar Zero new_coverage 65.9% (active 2026-04-27 ~03:46Z)

**Symptom (post-Stage-2 main run, 24975364848):** 10/11 scanner gates green:
- ✅ Coverage 100 Gate, QLTY Zero, Sentry Zero, DeepSource Visible Zero, Semgrep Zero, Codacy Zero, DeepScan Zero, Dependency Alerts, Quality Secrets Preflight, Quality Rollup
- ❌ **Sonar Zero**: `Sonar quality gate status is ERROR (expected OK)`

**Why:** SonarCloud's quality gate condition `new_coverage` requires ≥80%; actual is **65.9%**. Stage 2 fix moved this from 0% → 65.9% (huge win — coverage data IS being read), but coverage isn't fully matching to all source files.

**Root cause hypothesis:** vitest's lcov.info emits `SF:src/components/...` paths relative to vitest's cwd (`ui/`), but SonarCloud's path matcher expects them relative to repo root. The matcher is finding SOME files (hence 65.9%) but not all. Backend python coverage XML likely has the same mismatch (`coverage.xml` paths relative to `backend/`).

**Possible fixes (NOT yet attempted):**

1. **Adjust vitest's lcov path emission**: vitest v8 coverage may have a `srcPath` or similar option to prefix paths with `ui/`.
2. **Use `sonar.javascript.lcov.reportPaths` with multiple paths AND `sonar.sources=.`**: broaden source root so SF: paths can be matched anywhere.
3. **Lower SonarCloud's `new_coverage` threshold for event-link's quality gate** (operator-side; affects only this project, not the org-wide "Sonar way" default).
4. **Post-process lcov.info in CI** to prefix `ui/` to SF: lines before sonar-scanner runs.

Per the QZP-V2-DESIGN.md philosophy, fix #4 is the lowest-risk option — a workflow step that prefixes SF: lines. But it's repo-specific; the fleet (12 other governed repos with similar test setup) would benefit from a templated solution.

**State on event-link main (after PR #131 merge):** 10/11 gates green; new_coverage at 65.9% (vs 80% threshold) holds the aggregate Quality Zero Gate red. First time main has had >0% Sonar new_coverage since the rollout — the fix is working, just incomplete.