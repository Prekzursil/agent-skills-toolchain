---
title: 'Fleet lean gate rounds 4-5: basedpyright-standard + setup-dotnet + coverage-defer
  repos (2026-06-18)'
type: note
permalink: main/projects/reframe/fleet-lean-gate-rounds-4-5-basedpyright-standard-setup-dotnet-coverage-defer-repos-2026-06-18
tags:
- qzt
- fleet
- lean-gate
- basedpyright
- round5
- coverage
- decision
---

# Fleet lean gate — layered findings, rounds 4-5 (2026-06-18)

Continues [[fleet-lean-gate-biome-over-oxfmt-round-3-template-fixes-2026-06-18]]. After round-3 (biome) merged + v1 moved (91cc11ab) + the compliance wave pushed per-repo fixes, the REAL @v1 run surfaced the NEXT gate layer. Each round fixes earlier gates → exposes the next; convergent.

## @v1 (round-3) fleet results: 3 green / 13
GREEN: env-inspector (defusedxml requirements.txt added), personal-finance (no ts/js, was green), star-wars (osv zero-dep fixed).
Failures classified (verified via logs, NOT assumed):
- **basedpyright wave (6: momentstudio/swfoc/tanks/event-link/pbinfo/webcoder)** = TEMPLATE. basedpyright's default ("recommended") is stricter than pyright — floods untyped utility scripts (scripts/seo, scripts/quality, tools/workshop) with reportAny/reportUnknown*/reportUnusedCallResult (momentstudio 2774err/50301warn). Reframe runs basedpyright typeCheckingMode=standard via [tool.basedpyright]; fleet repos lack that. FIX (round-5): template runs basedpyright in STANDARD mode by default, honoring caller [tool.basedpyright] if present. NOT weakening (standard = Reframe's proven bar; reportAny-everywhere is gold-plating).
- **codex-session-manager** = TEMPLATE. gate-1 pre-commit runs the caller's dotnet-format hook but the runner has no .NET SDK (global.json pins 8.0.x) -> "Restore operation failed". The compliance-wave wrapper didn't prevent it. FIX (round-5): template detects C#/.NET (global.json/*.csproj/*.sln) -> actions/setup-dotnet before pre-commit (charter gate-1 C# = Roslyn+dotnet-format, so install the SDK, don't skip).
- **airline (jsts coverage)** + **codeblocks (python coverage, "NO TESTS RAN" exit5)** = REAL repo gaps (tests missing/under-wired). Same class as webcoder (7.65%). DEFER as documented drafts (the user already chose defer-multi-day-TDD for webcoder). To go 100%-green these 3 need genuine test-writing — offer TDD investment per repo.
- **devextreme** = stale oxfmt run (its re-pin commit ran before v1 moved) + the vendored-bundle issue -> round-4 (oxlint --no-error-on-unmatched-pattern + per-repo ignore static/app/**) IN FLIGHT (wf_b849baf7).

## SEQUENCING (template rounds edit the same reusable-quality.yml -> must serialize)
round-4 (oxlint no-unmatched + devextreme ignore) lands -> admin-merge + move v1 -> round-5 (basedpyright standard + setup-dotnet) off updated main -> admin-merge + move v1 -> rerun all 13 -> collect -> merge greens + atomic ruleset context flip (SaaS->quality). Expect ~10-11 green; airline/codeblocks/webcoder coverage-deferred.

## Reframe (parallel, disjoint, RUNNING): preview/subtitle bug-fix (wf_7fb5106e) + 4-bundle feature roadmap design->gates (wf_a57f82d0). Director v1 DONE (gate-approved DESIGN+PLAN, 10 WUs, feat/director-v1).

## Gotcha: a fleet watcher must verify run.headSha == branch HEAD before trusting "completed" (a just-pushed repo's new run isn't registered yet; you'll read the STALE prior run). devextreme's "oxfmt" step name caught this.