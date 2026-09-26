---
title: Reframe dependabot zero-out (2026-06-16)
type: note
permalink: main/projects/reframe-dependabot-zero-out-2026-06-16
tags:
- reframe
- dependabot
- security
- npm
- torch
---

# Reframe dependabot zero-out (2026-06-16)

Drove Prekzursil/Reframe dependabot from 39 alerts / 5 PRs.

## Outcome
- **Open PRs: 0** (was 5). **Open alerts: 16** (was 39) — all 16 are torch, genuinely unfixable.
- main `quality` green after merge.

## Key facts learned
- Reframe CI `quality` gate runs osv-scanner over 3 lockfiles (app/package-lock.json, app/render-cli/package-lock.json, sidecar/requirements.lock.txt). **Dependabot alerts != CI gate**: main was green with 39 open alerts because `osv-scanner.toml` triaged them as ignore-with-review. Driving alerts to 0 = actually doing the deferred upgrades and removing the ignores.
- Branch protection: required check = `quality`, strict=true (must be up to date), enforce_admins=false.
- vitest.config.ts uses RATCHET coverage floors (not 100%; CLAUDE.md's "100%" applies to the sidecar engine via pytest --cov-fail-under=100, NOT the renderer UI).

## What worked (PR #209, merged)
Coordinated npm upgrade cleared all 23 npm alerts:
- electron 31->39 (clears 17 electron CVEs), vite 5->6 + electron-vite 2->3 (peer; electron-vite 2.3 peer-locks vite to ^4||^5 -> ERESOLVE without it), @vitejs/plugin-react 4.3->4.7.
- vitest 1.6->3.2.6 + @vitest/coverage-v8 3.2.6 (clears vitest UI CVE; also drops the nested vite5/esbuild0.21 vitest 1.6 dragged in).
- `overrides`: esbuild ^0.28.1 (app), ws ^8.21.0 (render-cli, Remotion transitive).
- Removed ALL 24 now-unused ignores from osv-scanner.toml; osv = 0 issues with no ignores.
- vitest 3 gotchas: `vi.fn<[],R>()` -> `vi.fn<()=>R>()`; v8 coverage measures lines MORE accurately so same 565 tests drop ~78%->~74% lines/statements (re-baselined floors to 73 with margin; v8 has ~1pt run jitter). Branches/functions unchanged.

## torch = unfixable (FLAGGED, PRs #204/#205/#208 closed)
Dependabot bumped torch 2.6.0+cu124 -> 2.12.0 in requirements-chatterbox.txt. Unworkable because:
1. **No torch>2.6.0+cu124 wheel exists** — download.pytorch.org/whl/cu124 tops out at 2.6.0+cu124.
2. **chatterbox-tts hard-pins torch==2.6.0** (python<3.14) — the package this isolated GPU env serves.
3. Bump drops +cu124 (CPU-only) and leaves torchaudio mismatched; doesn't sync CHATTERBOX_REQUIREMENTS tuple in chatterbox.py -> fails tests asserting +cu124.
4. Several torch advisories have **no patched version** (GHSA-rrmf-rvhw-rf47, GHSA-qfhq-4f3w-5fph) even at 2.12.0.
5. 8 of the 16 torch alerts are against sidecar/requirements.lock.txt which **has never contained torch** (git -S confirms) — stale dependabot misattribution, not bump-fixable.
torch alerts can only clear via a deliberate human overhaul of the voice-clone stack (new CUDA tag + chatterbox-tts replacement). Did NOT dismiss alerts to fake zero — reported as unfixable.

## Rails honored
No --no-verify, no force-push, never bypassed the `quality` gate (let it gate #209), explicit `git add <paths>` + `git diff --cached --name-only` confirmation, no test weakened (565 still pass; only the coverage measurement floor tracked the tool change).
