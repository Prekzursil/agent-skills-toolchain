---
title: 'Reframe issues #264 #265 resolved 2026-07-11'
type: note
permalink: main/reframe/reframe-issues-264-265-resolved-2026-07-11
tags:
- reframe
- codeql
- path-injection
- ci
- resolved
---

# Reframe issues #264 #265 resolved 2026-07-11

Closed out the user's remaining Reframe backlog: 2 open issues + 1 dependabot PR + 1 security alert. Repo now: **0 open issues, 0 open PRs, main green.**

## What was done
- **PR #277** (dependabot pip/sidecar bump, torch stack + cudnn): fixed the hardcoded pin test (`test_runtime_setup.py` cudnn `9.23.2.1`→`9.24.0.43`), verified safetensors 0.8.0 keeps stable `safetensors.torch.load_file` API, **merged**.
- **Alert #262** (torch CVE-2025-3000, `torch.jit.script`): **dismissed** `not_used` (feature unused, no patched version, AV:L local-only).
- **Issue #265** (quality — mojibake dash): **fixed + merged** (PR #278).
- **Issue #264** (security — CodeQL keystore guards): **resolved + closed** (inline proven infeasible; dismissal is correct).

## ⭐ KEY LEARNING — CodeQL rejects a taint-derived containment base
Tried (PR #279) to inline `safeFilePath`'s `resolve(dir, basename)` + `startsWith(dir + sep)` guard at the keystore write/shred sinks so CodeQL `js/path-injection` would confirm it locally instead of via the dismissed helper-boundary FP. **It empirically failed** — CodeQL still flagged `keystore.ts:252` "Uncontrolled data used in path expression."

Root cause: the containment base `dir = resolve(dirname(path))` is **derived from the tainted `path`**. CodeQL does NOT accept a taint-derived prefix as a path-injection barrier (a check against an attacker-influenceable prefix proves nothing). This is the **same limitation as Python `ensure_within` needing an untainted base**. The keystore is Electron-decoupled (full path injected for unit-testability) so there is **no untainted base** → the alerts are un-clearable by inlining → **the dismissal IS the correct, principled FP resolution** (the "user-provided value" is actually `app.getPath("userData")`, confined to its own dir by safeFilePath). Only advanced-CodeQL-setup modeling safeFilePath as a custom sanitizer could make CodeQL "confirm" it — not worth it for tool-recognition-only. Extends [[reference_reframe_quality_gate_codeql_2026-07-11]].

## #265 finding — em-dash mojibake was a CI-font artifact, not a source bug
The Library readiness labels `Reframe — vertical subject tracking` / `— saliency` showed the em-dash (U+2014) as mojibake in the Windows CI visual baseline. Verified: source em-dash is **correct** (byte-identical to the "Reframe — Media Studio" one that renders fine) and RPC transport is UTF-8-safe (`json.dumps ensure_ascii=True` → ships as `—`, Electron un-escapes). So it's a CI headless-font rendering artifact for these RPC-delivered rows. Fix = switch separator to ASCII hyphen (`-`, matches the `Reframe - Media Studio` productName) for deterministic rendering. Source in `sidecar/media_studio/handlers/_capabilities.py:64,71,73`. Windows visual baseline regenerates on CI.

## Process note
Isolated the risky #264 experiment (could introduce non-dismissable PR-blocking CodeQL alerts) into its own PR #279, separate from the safe #265 PR #278 — so the CodeQL-rejection didn't block the safe fix. When it failed, closed #279 + kept dismissals with no collateral.

Continues [[project_reframe_v1_4_1_shipped_2026-07-09]].
