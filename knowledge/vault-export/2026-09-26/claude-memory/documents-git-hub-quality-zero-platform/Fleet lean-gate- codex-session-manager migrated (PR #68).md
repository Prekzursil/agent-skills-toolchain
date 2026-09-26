---
title: 'Fleet lean-gate: codex-session-manager migrated (PR #68)'
type: note
permalink: main/claude-memory/documents-git-hub-quality-zero-platform/fleet-lean-gate-codex-session-manager-migrated-pr-68
tags:
- fleet
- lean-gate
- quality-zero-platform
- codex-session-manager
- csharp
---

# Fleet lean-gate: codex-session-manager (PR #68)

Migrated `Prekzursil/codex-session-manager` to the lean 6-gate via an ADDITIVE PR (2026-06-17, charter decided 2026-06-16).

## Outcome
- PR: https://github.com/Prekzursil/codex-session-manager/pull/68 (NOT draft — all applicable gates verified green locally)
- Language: pure C# (.NET 8), 63 .cs files, 3 src + 3 test projects.
- Archive-first: branch `archive/pre-lean-gate` + annotated tag `archive/pre-lean-gate` at default HEAD `ce3ce84` (both pushed).
- Branch: `feat/lean-quality-gate`, commit `4e32b0e`.
- SECURITY.md: ALREADY EXISTED (standard form, PVR link + @Prekzursil) — no change.

## Added (additive only; no QZT workflow removed, no rulesets/required-contexts touched)
- `.github/workflows/quality.yml` — ~5-line caller pinned to `reusable-quality.yml@feat/lean-quality-template`.
- `.pre-commit-config.yaml` — C# `dotnet format` (Roslyn) + gitleaks v8.30.1.
- `.gitleaks.toml` — path allowlist (bin/obj/publish/etc). 0 leaks.
- `.quality/opengrep/{general,csharp}-security.yaml` + README — pinned SAST, 5 rules, 0 findings.
- `osv-scanner.toml` + 6 `packages.lock.json` (generated `dotnet restore --use-lock-file`). 0 issues.
- Dependabot already configured (nuget + github-actions) — left as-is.

## Gate-1 autofix committed
- `.gitattributes` flipped `* eol=crlf` -> `eol=lf` (repo blobs were ALREADY LF; .editorconfig says end_of_line=lf; the crlf attr was the outlier forcing CI `dotnet format` ENDOFLINE failures). Renormalized 9 CRLF-stored files.
- Real format fixes (only 2 files): `[assembly:ThemeInfo` -> `[assembly: ThemeInfo` (App/AssemblyInfo.cs); raw-string-literal dedent in SessionCatalogRepositoryTests.cs.

## Key findings / gotchas
- **C# repos: the reusable lean template runs NO C# test/coverage lane** (gate 3 covers only python/jsts). C# tests stay in the existing `ci.yml`. So for C# callers the lean gate enforces gates 1/4/5/6 only — gate 2 (types) is compiler-enforced, gate 3 stays in dotnet CI.
- **charter_check.sh must NOT ship in caller repos**: it hard-requires `.github/workflows/reusable-quality.yml` in the same root (only exists in QZP), so shipping `.quality/charter.yml` in a caller would make `charter-check` exit 1 = permanent red. Detection `if: charter=='true'` correctly skips it when absent. Drift guard lives in QZP only. (README's "callers ship charter" line is wrong for the path logic.)
- **osv-scanner needs lockfiles**: bare `.csproj` PackageReference => "No package sources found" (exit 128). Generate committed `packages.lock.json` via `dotnet restore --use-lock-file`; existing `ci.yml` `dotnet restore` is non-locked so won't break; Dependabot updates them.
- **GOTCHA — git stash --include-untracked + drop DELETES untracked new files.** Lost all recreated configs mid-task that way; had to recreate. Never use stash to "reset tracked only" when untracked work exists.
- Local `dotnet format CodexSessionManager.sln` (solution-wide) OOMs on this Windows box (MEF/MSBuild); per-project `dotnet format <proj>` works. Verify LF cleanliness by exporting the staged index (`git checkout-index --prefix=`) to a scratch dir (index blobs = LF = what CI checks out) then per-project verify.
- `scripts/verify` (QZT pre-push: dotnet restore/build/test) GREEN, 112 tests pass.

## CI read (once, no grind per anti-livelock)
- `quality / quality` lean gate: PENDING at PR open (just launched). Verified every lane green locally.
- QZT SaaS checks (Codacy/Sonar/Coverage-100/DeepScan/etc.) still run (deferred machinery) — if any blocks, it's an OPERATOR/BLOCKED item, not to be ground on.
