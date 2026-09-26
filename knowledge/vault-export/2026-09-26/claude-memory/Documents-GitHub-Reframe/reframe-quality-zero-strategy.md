---
name: reframe-quality-zero-strategy
description: Where the Reframe quality-zero strategy/plan lives and its headline verdict
  (100% coverage + absolute-zero issues effort)
metadata:
  node_type: memory
  type: project
  originSessionId: d66eeed2-b2c3-47a7-bf57-a847586abb68
permalink: main/claude-memory/documents-git-hub-reframe/reframe-quality-zero-strategy
---

User goal for Reframe: **100% line+branch coverage on every test-measuring gate** AND **absolute zero issues (no ignore/suppress/bypass) on every provider dashboard** (Sonar, Codacy, Codecov, CodeQL, Semgrep, DeepSource, DeepScan, QLTY, CodeRabbit, Applitools, Chromatic, Dependabot, Sentry), with Claude hooks/MCP to fetch+fix+prevent.

A 26-agent ultracode workflow (2026-06-06) produced `docs/quality-zero/ZERO-STRATEGY-ULTRACODE-PLAN.md`. Headline verdict: **dashboard-zero is FALSE today** — today's "100%" measures ~1.2% of web lines (rest excluded), Python/Rust coverage is computed then discarded, and "zero" relies on 242 CodeQL dismissals + a `known-issues` NOSONAR registry. Recommended path = **Option 3**: prevention hooks now (hard-deny new suppressions) + new-code-zero blocking gate + bounded backlog burndown + extend the existing Codex remediation loop with a Claude fixer; overall-zero is the *destination*, reached by burndown, not a day-one blocking invariant. Rust branch coverage is the one tooling-forced exception (region + cargo-mutants on stable).

Delivery mechanics gotcha: see [[quality-zero-platform-delivery-trap]].