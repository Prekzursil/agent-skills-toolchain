---
title: 'Reframe WU-A: OS-matrix packaged E2E + nasty-input fixtures'
type: note
permalink: main/projects/reframe/reframe-wu-a-os-matrix-packaged-e2-e-nasty-input-fixtures
tags:
- reframe
- e2e
- ci
- electron
- testing
---

# Reframe WU-A (branch feat/test-hardening, off origin/main 8c7f320)

Done 2026-06-22. Clone at C:\Users\Prekzursil\AppData\Local\Temp\reframe-wuA (Git Bash temp == Windows fs). WSL sees it at /mnt/c/.../reframe-wuA; venv = /tmp/msv (py3.12.3) with e2e deps (faster-whisper/cv2/av/scenedetect). Commit 82ba57d, pushed (origin tip 9a5aa0f after rebase).

## Key architecture facts (load-bearing)
- electron-builder.yml is **Windows-only**: only a `win:` target; extraResources need build/python-embed (3.12) + build/python-embed-314 (3.14, chatterbox) + build/ffmpeg, ALL staged by build/python-embed-setup.ps1 (PowerShell, -WithFfmpeg, network DLs). No mac/linux package possible. So: windows leg = real .exe packaged E2E; mac/linux = dev-build preview E2E.
- Two coverage gates, BOTH 100%, must not regress: sidecar `pytest --cov=media_studio --cov-branch --cov-fail-under=100` (default addopts `-m 'not e2e'` deselects e2e tests) and renderer `vitest run --coverage` (renderer/src/** include; app/e2e/ NOT in include).
- e2e tests live OUTSIDE both coverage scopes → nasty-input e2e fixtures add zero coverage and can't break the gate. Confirmed: sidecar deselected 21→45 (my 24 new), still 100%/4015 passed; renderer 100%/1653 passed.
- pre-commit biome/oxlint patterns are `^app/(main|renderer/src|render-cli/src)/...` → they EXCLUDE app/e2e/. Gate-lint-format passing is NOT evidence the e2e specs are clean; run `biome check` on them manually.
- charter_check.py parses ONLY quality.yml, not e2e.yml → safe to rewrite e2e.yml.

## What I built
- .github/workflows/e2e.yml: e2e-gui promoted to matrix [windows-latest, macos-latest, macos-13, ubuntu-latest], fail-fast:false. Per-OS ffmpeg (apt/brew/choco); xvfb Linux-only (2 conditional steps); RF_PY=setup-python python-path on all legs; RF_E2E_DEV=1 on non-win; Windows stages embed+builds package then drives .exe; CSC_IDENTITY_AUTO_DISCOVERY=false (mac signing hang).
- app: added electron-playwright-helpers devDep. fixtures.findBuiltApp() prefers dist/ package (findLatestBuild+parseElectronApp→executable) else dev MAIN_ENTRY; RF_E2E_REQUIRE_PACKAGED=1 hard-errors when no package. preview.spec asserts app.isPackaged matches launched build. New packaged.spec.ts: test.describe + `test.skip(process.platform!=='win32')`, asserts isPackaged===true + resources/asar path.
- Nasty inputs probed FIRST (ground truth): zero-length/garbage → playable:false+reason (graceful); audio-only/weird-aspect → ok; mjpeg → playable:false "not Chromium-playable"; missing → RpcError "unknown video" (NOT "not found"); subtitle parsers tolerant (empty/whitespace/no-timing→0 cues; bad-ts→ValueError "unparseable timestamp"; unicode/RTL preserved; ASS escape_ass_text neutralizes `{`/`}` braces but leaves inner literal text inert).
- sidecar/tests/e2e/test_nasty_inputs.py (e2e-marked, 24 tests) + app/e2e/nasty_captions.dom.test.tsx (5 tests, real CaptionOverlay).

## Gotchas hit
- CaptionOverlay.activeLine groups words within LINE_GAP_SEC=0.8 → dense cues (0.005s spacing) make the active "line" the WHOLE 10k list. Fix test: phrases of 10 words with >0.8s gaps between → bounded active line.
- WSL invocation from Bash tool: use `wsl.exe -e bash -lc "cd /mnt/c/... && /tmp/msv/bin/python ..."` (double-quote, cd-first). Bare `-e /tmp/...` or referencing /tmp at arg position triggers WSLENV path mangling to a Windows temp path.

## Local validation done
- sidecar nasty e2e: 24 passed (WSL). Default gate: 100%, 4015 passed, 45 deselected.
- renderer: 100%, 1653 passed. DOM e2e: 7 passed.
- typecheck:e2e clean; biome check clean; actionlint clean EXCEPT macos-13 false-positive (stale label DB; macos-13 is a real Intel runner the task requires).
- Built dev bundle + ran preview.spec against it (RF_E2E_DEV=1): 8 passed incl isPackaged===false. packaged.spec on Windows w/o dist → fails fast with clear message (correct; CI builds first).
- Matrix dispatched: run 27924345135 (queued/running all 5 legs). PACKAGED build leg is CI-only (can't stage embed locally).


## CI run 1 results (27924345135) + fix
- e2e-gui ubuntu+macos-latest: GREEN (dev build, isPackaged===false path). macos-13: stuck queued (runner shortage) — cancelled.
- e2e-sidecar: RED on 3 PRE-EXISTING tests (verified fail on pristine origin/main too): test_e2e_ai2_hub_director::test_hub_rotation_on_real_429, ::test_director_apply_default_engine_table_is_empty, test_e2e_ai2_intel_repurpose::test_intel_semantic_settings_driven_egress_redacted_key_bug (XPASS-strict, documents redacted-key product bug). OUT OF SCOPE — do NOT fix/deselect. My 24 nasty tests passed in CI.
- Windows leg: staging (python-embed-setup.ps1 incl 3.14 embed) GREEN headless first try; electron-builder package GREEN; DOM tests GREEN; but PACKAGED .exe Playwright E2E RED. Root cause = harness resolution bug, NOT packaging: findBuiltApp's silent `catch{}` hid whether findLatestBuild or parseElectronApp threw. electron-builder directories.output is resolved relative to projectDir (app/) per platformPackager.ts `path.resolve(this.projectDir, output)` → ../dist = repo-root dist = D:\a\Reframe\Reframe\dist (matches error path, so dir IS correct). parseElectronApp(win-unpacked) win32 branch (find_parse_builds.js:228-253) takes first .exe + reads resources/app.asar packageJson.main — works IF win-unpacked exists.
- Fix (commit 42b6d6e): findBuiltApp now tries explicit unpacked dirs [win-unpacked, linux-unpacked, mac, mac-arm64] via parseElectronApp first, then findLatestBuild fallback; on RF_E2E_REQUIRE_PACKAGED failure throws dist/ listing + per-candidate error + candidate dir contents → one CI run will reveal if win-unpacked exists or how parse failed. Re-dispatched run 27924902833.
- KEY: gh run logs (--log-failed / --log) NOT downloadable until WHOLE run completes; a queued macos-13 blocks it. The error-context.md artifact (uploaded mid-run via always()) IS retrievable → route diagnostics through the JS throw, not a YAML step.
- PACKAGED_E2E honest status until this leg green: "package builds in CI (staging+electron-builder green); .exe launch pending harness-resolution fix."


## CI runs 2-4: packaged .exe VERIFIED, preview seeding issue isolated
- Run 27924902833 (commit 42b6d6e): diagnostics revealed win-unpacked EXISTS + parseElectronApp resolves exe='win-unpacked/Reframe - Media Studio.exe'; my bug was gating on existsSync(info.main) — info.main is INSIDE app.asar (resources/app.asar/out/main/main.js), existsSync always false. Fix 97db692: gate only on info.executable (real file); info.main is the correct electron.launch arg for asar (canonical electron-playwright-helpers pattern args:[appInfo.main],executablePath:appInfo.executable).
- Run 27925243567 (commit 97db692): **packaged.spec.ts PASSED** = SHIPPED .exe boots, app.isPackaged===true, runs from resources/asar, packaged renderer loads no-console-errors. PACKAGED_E2E answer = YES (drives the .exe). BUT 4 preview.spec tests RED: seeded 'sample' absent from packaged library (Library title renders but 0 items).
- Anchor correction (advisor): NOT a python mismatch — sidecar.ts:95 + dataRoot envOverride both make MEDIA_STUDIO_PYTHON/CONFIG_DIR env WIN in packaged too (same as dev which passed 8/8). Real suspects: env not propagating to packaged .exe launch, OR config-dir divergence under isPackaged. main.ts:140-180 confirms envOverride wins; preferExeDataDir=app.isPackaged only kicks in when env UNSET.
- Fix attempt 3fbb989: added packaged.spec diagnostic — reads packaged main env (CONFIG_DIR/PYTHON/SIDECAR_DIR) + drives window.api.rpc ping+library.list (seed-independent "packaged backend responds" proof). Run 27925862006 pending — will reveal env-vs-sidecar-vs-dataroot root cause in one run.
- DECISION pending evidence: if harness env-propagation → fix, preview.spec passes packaged. If genuine app behavior (ignores CONFIG_DIR when packaged / sidecar can't spawn) → app bug OUT OF WU-A SCOPE: report finding, run preview.spec dev-build on all legs, keep packaged.spec (with ping/list) as the .exe proof.
- gotcha: `gh run watch`/`--log` blocked by queued macos-13 (runner shortage); poll per-job via `gh api .../actions/jobs/<id>` + download error-context.md artifact (always() upload) mid-run.


## ROOT CAUSE CONFIRMED (run 27926388588, stderr captured) + final resolution
- Captured packaged main log proved it: env propagates FINE (configDir=seeded dataRoot, python=hostedtoolcache 3.12.10, sidecarDir=D:\a\Reframe\Reframe\sidecar all correct). Sidecar "not running" because packaged main runs FIRST-RUN BOOTSTRAP: `[bootstrap] step 2/2: python -m pip install --target <configDir>/envs/sidecar -r resources/sidecar/runtime_setup/requirements-sidecar.txt` — pip-installing the HEAVY runtime (faster-whisper/torch/etc) on first launch. Multi-minute + network → sidecar can't answer RPCs in CI test window. This is the DOCUMENTED app design (electron-builder ships SOURCE+embeds; wheels install first-run), NOT a regression, NOT in WU-A scope to change.
- Final resolution (commit 754a90b): packaged.spec keeps isPackaged===true/asar/no-console-error (.exe SHELL works) + new assertion = packaged main inherits seeded env AND fires [bootstrap] from shipped resources/sidecar (reads app.process() stdout/stderr buffered in beforeAll — Playwright error-context omits sidecar stderr, so app.process() capture was the key diagnostic). DATA-PIPELINE (seeded library/playback/export) runs against dev build: Windows leg now sets RF_E2E_DEV=1 so preview.spec uses dev build (passes) while packaged.spec still drives real .exe (self-forces RF_E2E_REQUIRE_PACKAGED, ignores RF_E2E_DEV). README documents the shell-vs-pipeline split.
- KEY LESSON: to debug a packaged Electron sidecar in Playwright, capture `app.process().stdout/stderr` in beforeAll and append to the failing assertion — error-context.md does NOT include the spawned child's stderr. The asar info.main path (resources/app.asar/out/main/main.js) is NOT a real fs path → never existsSync-gate it; it's the valid electron.launch arg.
- PACKAGED_E2E final answer: YES drives the .exe (packaged.spec green: isPackaged===true via electronApp.evaluate, runs from asar, boots clean, fires bootstrap). Cold packaged full-pipeline = CI-infeasible (first-run heavy pip), proven+documented; pipeline verified on dev build all legs.
- Final verify run 27927014485 pending.