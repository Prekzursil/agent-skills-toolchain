---
name: quality-zero-platform-delivery-trap
description: How quality-zero gate changes actually reach Reframe (controller pin
  vs platform_ref) and the fleet blast radius — read before editing any quality gate
metadata:
  node_type: memory
  type: project
  originSessionId: d66eeed2-b2c3-47a7-bf57-a847586abb68
permalink: main/claude-memory/documents-git-hub-reframe/quality-zero-platform-delivery-trap
---

Reframe's CI quality gates are thin wrappers that call reusable workflows in the **separate** repo `Prekzursil/quality-zero-platform` (a "strict-zero control plane" governing ~16 repos). Two decoupled version knobs, and getting them wrong makes fixes silently no-op or blast all 16 repos:

- **Controller pin** = the `@<SHA>` on each wrapper's `uses:` line — freezes WHICH reusable-workflow **YAML file** GitHub loads. Reframe is pinned ~214 commits behind platform `main`. So **editing `reusable-*.yml` has ZERO effect on Reframe until the pin is bumped** (via platform `bump-workflow-shas-wave.yml`, needs `DRIFT_SYNC_PAT`).
- **`platform_ref: main`** = which platform **Python** (`scripts/quality/**`) the loaded workflow checks out at runtime. So **any script-level change hits ALL ~16 governed repos the instant it merges to `main`**, independent of pins. Always dogfood platform self-CI + spot-check 1-2 consumers before merging; registry/known-issues edits need operator sign-off.

The full strategy + evaluation (live dashboard census proving dashboard-zero is currently FALSE, the empty-`canonical.json` feed defect, coverage-discarded bug, 242 dismissed CodeQL alerts, two-track plan) lives in `docs/quality-zero/ZERO-STRATEGY-ULTRACODE-PLAN.md` (+ `APPENDIX-evidence.md`). See [[reframe-quality-zero-strategy]].