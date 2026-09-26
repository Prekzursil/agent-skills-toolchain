---
name: Quality Rollup v2 work lives in quality-zero-platform
description: Pointer — the QRv2 refactor is in-flight on feat/quality-rollup-v2 at
  C:\Users\Prekzursil\Documents\GitHub\quality-zero-platform; resume there, not here
type: reference
permalink: main/claude-memory/downloads-swfoc-editor/qrv2-pointer
---

Quality Rollup v2 refactor for `quality-zero-platform` is in-flight on branch `feat/quality-rollup-v2`. Design doc committed at `93ae3f6` — `docs/plans/2026-04-09-quality-rollup-v2-design.md`.

Phase 3 (brainstorming) complete. Phase 4 (design-review-gate → writing-plans → plan-review-gate) pending — must be run in a session rooted at `C:\Users\Prekzursil\Documents\GitHub\quality-zero-platform\` so the repo's CLAUDE.md + metaswarm rules apply.

**Do not resume QRv2 work in this SWFOC session.** Open Claude Code inside `C:\Users\Prekzursil\Documents\GitHub\quality-zero-platform\` and the bionlp-style per-project memory at `~/.claude/projects/C--Users-Prekzursil-Documents-GitHub-quality-zero-platform/memory/qrv2_resume.md` will load automatically with full context.

**What user locked in during brainstorm (for quick recall if they ask from this session):**
- Dual output (canonical JSON + rendered markdown), multi-view (by file/provider/severity)
- Hybrid dedup taxonomy (~40 categories)
- D+E patch tier (deterministic + LLM fallback)
- Strict 100% coverage on platform repo, reuse existing gate scripts
- Fix SonarCloud coverage upload via sonar-project.properties
- Minimal .codacy.yaml + per-tool config files
- Chromatic+Applitools infra + enable on momentstudio
- 3 PRs: foundation, self-gov, new lanes