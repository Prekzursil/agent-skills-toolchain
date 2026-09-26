---
title: Wave2 Codex-Fleet GUI integration facts 2026-07-11
type: note
permalink: main/projects/wave2-codex-fleet-gui-integration-facts-2026-07-11
tags:
- wave2
- codex-fleet
- quality-zero-platform
- gui
- admin-dashboard
---

# Wave2 Codex-Fleet GUI integration facts 2026-07-11

Component (C) of Wave 2 = self-contained admin GUI to edit `codex-targets.yml` + trigger the codex fleet sweep. Target repo: `Prekzursil/quality-zero-platform` (PUBLIC control-plane, holds NO auth.json).

## Non-obvious integration constraints (discovered)
- QZT publishes its admin dashboard via `.github/workflows/publish-admin-dashboard.yml` → runs `scripts/quality/build_admin_dashboard.py --assets-dir docs/admin --output-dir site` → deploys `site/` to GitHub Pages.
- **`write_dashboard()` copies ONLY 3 named files** (`index.html`, `styles.css`, `app.js`) from `docs/admin` → `site/`. It does NOT recurse subdirectories. So a raw `docs/admin/codex-fleet/index.html` would NEVER reach Pages.
- QZT enforces **100% coverage** and has Python tests for the builder (`tests/test_admin_dashboard.py`, `test_build_admin_dashboard_extra.py`). Modifying `write_dashboard()` pulls in the coverage gate + test maintenance.
- **DECISION**: fit in by extending the WORKFLOW (`publish-admin-dashboard.yml`) with a YAML-only `cp` step that copies `docs/admin/codex-fleet/` into `site/codex-fleet/` — zero Python/coverage impact. Page lands at `https://<pages>/codex-fleet/`.
- Existing dashboard conventions: vanilla ES-module JS, XSS-safe DOM (`createElement`+`textContent`, never innerHTML for data), dark palette (bg #0b1020, panel #121a31, border #1f2a44, text #edf2f7, accent #8cc8ff, badges pass/fail/pending).

## Dispatch contracts (from live workflow files)
- Runner = `Prekzursil/agent-skills-toolchain` `.github/workflows/codex-runner.yml` (PRIVATE, holds CODEX_AUTH_JSON). workflow_dispatch inputs: `target_repo`(req), `task`(req), `base_branch`, `model`(default gpt-5.6-sol), `effort`(minimal|low|medium|high|xhigh|max|ultra), `max_changed_files`(int str).
- Runner PRs carry label `codex-runner` + assignee `Prekzursil`, branch `codex/<UTCts>`, title "Codex: automated change". → PR status query = `is:pr is:open label:codex-runner`.
- Sweep workflow `codex-fleet-wave.yml` (component B, lives in QZT) + `codex-targets.yml` (component D writes it) DO NOT EXIST YET — GUI must handle 404 gracefully.

## Auth reality (CORS)
- api.github.com sends CORS + supports Authorization header → PAT reads/commits/dispatch all work client-side.
- github.com/login/device/code + /login/oauth/access_token do NOT send CORS → static-page Device Flow is IMPOSSIBLE without a proxy. So PAT (session-only, sessionStorage) is the working MVP; Device Flow is wired but gated behind CONFIG.deviceFlowClientId + deviceFlowProxy (one-time owner setup).

Staging: `.../6b89b6ff-.../scratchpad/wave2/gui/quality-zero-platform/{docs/admin/codex-fleet/index.html, .github/workflows/publish-admin-dashboard.yml}` + MANIFEST.md.
