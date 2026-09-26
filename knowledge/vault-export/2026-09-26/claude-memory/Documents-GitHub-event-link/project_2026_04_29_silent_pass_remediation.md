---
name: 2026-04-29 silent-pass gate remediation
description: Multi-PR push to convert silent-pass gates (Semgrep, Codacy, DeepSource,
  QLTY, DeepScan) into hard-blocks across the fleet
type: project
originSessionId: 7e07bd36-c338-4890-8179-e112e67d5844
permalink: main/claude-memory/documents-git-hub-event-link/project-2026-04-29-silent-pass-remediation
---

User identified 5 silent-pass scanner gates that pass green while findings sit on cloud dashboards. Strict-zero contract: ANY findings, complexity >goal, duplication >goal, OR coverage missing/<100% must red-block.

**Active PRs** (Prekzursil/quality-zero-platform):
- **#221** Semgrep SARIF zero-gate. `semgrep ci` exits 0 on non-blocking findings; replaced with `semgrep ci --sarif-output` then `check_semgrep_zero.py` counts ALL findings. Falls back to `semgrep scan --config auto` when SEMGREP_APP_TOKEN unset.
- **#222** Codacy threshold gate. New `codacy_quality_thresholds.py` adds complexFilesPercentage / duplicationPercentage / coverage missing+<100% checks via repository-analysis endpoint. 100% coverage floor (overrides Codacy's default 60%).

**Why:** User: "make sure that the gates are properly enforced and properly report when... issues are not 0, complexity or duplicaiton is beyond limit and coverage is not uploaded and/or not 100% line+branch".

**How to apply:** When working on QZP gate tightening, check both PRs first; the patterns established (SARIF zero-gate + auth fallback for Semgrep; multi-dim threshold module for Codacy) are templates for the remaining gates: DeepSource (HTML scraper missing 875+140 issues), QLTY (cloud=71 vs local=0 mismatch on QZP), DeepScan (need verification).

**Mistakes to avoid (recorded so future-me skips them):**
1. Closed PR #220 — tried `semgrep ci --error --strict` but those flags only work on `semgrep scan` (legacy), not `semgrep ci`. `ci` rejects them with `unknown option`. Use `semgrep ci --sarif-output` + post-scan SARIF gate instead.
2. Workflow contract test was actively *locking in* the silent-pass form — `assertIn('run(["semgrep", "ci"], ...)') + assertNotIn('--error')`. Inverted to assert the new SARIF + zero-gate pattern.
3. New scripts/quality/*.py files MUST be added to `sonar.coverage.exclusions` in `sonar-project.properties` or the `test_exclusions_match_coverage_source_complement` test fails the pre-push verify.
4. `URLError` extends `OSError` — `except (OSError, URLError)` is redundant; DeepSource flags it.
5. `check_semgrep_zero.py` and other gate scripts invoked from `cwd=repo_dir` (target repo, not QZP) need `sys.path` bootstrap mirroring `check_codacy_zero.py`.