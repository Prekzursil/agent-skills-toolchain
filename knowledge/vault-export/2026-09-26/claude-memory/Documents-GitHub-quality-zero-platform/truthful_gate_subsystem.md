---
name: Truthful-Gate Subsystem (active campaign closure)
description: The "once and for all" plan to end the recurring QZP gates-and-issues
  churn — dashboard-truth scanner + zero-conf onboarding. Resume context for quality-zero-platform.
type: project
permalink: main/claude-memory/documents-git-hub-quality-zero-platform/truthful-gate-subsystem
---

## What it is

The user's "solve everything as discussed, sturdy, well documented" ask =
the **truthful-gate subsystem** (handoff `.remember/today-2026-06-01.md`:
"dashboard-truth scanner → QZP profiles, zero-conf onboarding").

Design committed: `docs/plans/2026-06-01-truthful-gate-subsystem-design.md`
Branch: `feat/truthful-gate-subsystem` off `origin/main` @ c0a5437.
Recovery: `.beads/plans/active-plan.md`. See also [[qrv2_resume]] (now stale).

## The root problem (why it kept recurring)

Gates passed off CI exit codes while provider DASHBOARDS still listed
findings; rotated SaaS tokens surfaced as silent greens. ~30 strict-zero
PRs (#198–#225) chipped at symptoms; #232 (OPEN, BLOCKED) is the
enforcement half — it's red *correctly* because retiring the platform
`audit` exception exposes 838 Codacy + 1116 DeepSource + 110 Sonar legacy
findings.

## Design pillars

1. One **Truth Source contract** (`truth/contract.py`) — verdict enum
   `clean|dirty|unreadable`; `unreadable` (rotated token / API down) →
   BLOCK, making silent-pass *unrepresentable*. Refactor existing
   `check_*_zero.py` to delegate (characterization-test first).
2. **Token-rotation resilience** — auth preflight → `alert:scanner-unavailable`.
3. **Truthful baseline/burn-down** replaces `audit` mode (DECISION A1) —
   block on any increase + on missed deadline; unblocks #232 honestly.
4. **Reconciliation** CI-vs-dashboard → `alert:gate-truth-drift`.
5. **Zero-conf onboarding** `qzp onboard <slug>` — auto stack-detect +
   vendor-key derivation + ~8-line profile via stack inheritance
   (DECISION B1) + bootstrap + auto-promote.

## Mandated pipeline (CLAUDE.md)

design-review-gate (5) → writing-plans (PR-sliced TG-1..TG-6) →
plan-review-gate (3) → execution-method choice → execute (TDD, 100% cov) →
/self-reflect → PR.

## Gotchas to honor

- New `scripts/quality/*.py` MUST be added to `sonar.coverage.exclusions`
  in `sonar-project.properties` or `test_exclusions_match_coverage_source_complement` fails.
- `semgrep ci` rejects `--error/--strict`; use `--sarif-output` + post-gate.
- `URLError` extends `OSError`; don't write `except (OSError, URLError)`.
- Gate scripts invoked from `cwd=repo_dir` need the `sys.path` bootstrap.
- 8 git stashes are "prevent loss" — do not drop.