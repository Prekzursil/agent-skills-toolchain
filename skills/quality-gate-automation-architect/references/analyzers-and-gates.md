---
title: analyzers-and-gates
type: note
permalink: dqverify-repo-20261013/skills/quality-gate-automation-architect/references/analyzers-and-gates
---

# Analyzers and Gates

Use this reference when the architecture involves SonarQube Cloud, Codacy, Codecov, coverage ratchets, or strict branch-protection quality gates.

## Tool-neutral principles

- Map failing checks to their actual producers before proposing fixes.
- Separate lanes: coverage, lint and style, static analysis, security, integration, visual, deployment.
- Do not assume a provider dashboard is the full truth. Compare provider results with workflow files, gate scripts, and branch protection.
- Keep pull-request repair separate from historical debt reduction.

## SonarQube Cloud

Official behavior that matters:

- Pull request analysis uses the quality gate to catch new issues before merge.
- Pull request analysis reports only issues introduced by the pull request, compared with the target branch analysis.
- Pull request quality gates apply only the conditions on new code.
- PR decoration can surface the quality gate status in the DevOps platform and block merge if the gate fails.
- Target branch analysis must be current, or stale target scans can misclassify what is truly new.

Design guidance:

- Treat Sonar PR failures as PR-lane inputs, not backlog-lane inputs.
- If the target branch analysis is stale, refresh that assumption before chasing false positives.
- Do not promise whole-repo historical cleanup from PR quality-gate semantics alone.

## Codacy

Official behavior that matters:

- Codacy quality gates determine when pull requests and commits are reported as not up to standards.
- Codacy can report PR status back to the Git provider and optionally block merges.
- Gate rules include new issues, new security issues, complexity, duplication, coverage variation, and diff coverage.
- `Diff coverage is under` applies only to pull requests.
- Codacy coverage views expose both diff coverage and coverage variation relative to the target branch.

Design guidance:

- Use diff coverage for PR-specific coverage requirements.
- Use coverage variation for "do not let project coverage drop" style policies.
- Allow a small negative coverage variation only if the user explicitly accepts that trade during refactors.
- Avoid using Codacy alone as the source of retry logic; combine it with workflow status and local validation.

## Practical heuristics from prior sessions

These are derived summaries, not vendor rules:

- Missing or obsolete required contexts can keep a strict-zero gate red even when the underlying tools are green.
- Large-diff coverage targets can be dominated by denominator math; quantify expected covered-line gain before spending cycles.
- Coverage-only work should not inherit unrelated failing lanes such as Ruff, Percy, or deployment checks.
- High-signal diagnosis combines:
  - required checks from GitHub
  - failing workflow logs
  - policy files such as `.codacy.yaml`, `codecov.yml`, or custom gate scripts
  - provider-specific PR metrics and comments

## Ratchet patterns

- Prefer diff coverage and non-decreasing project coverage as the default PR contract.
- Ratchet uplift should come from narrow test additions first.
- Stop coverage work when the next increment clearly requires wider production refactoring or new shared test harnesses.

## Debt burn-down patterns

- Batch by `tool -> rule family -> language -> directory`.
- Keep PRs narrow and reviewable.
- Maintain allowlists for zero-touch rules and denylists for reviewer-only areas such as auth, concurrency, migrations, and public API changes.