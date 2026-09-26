---
title: webcoder lean-quality-gate osv-scanner status 2026-06-20
type: note
permalink: main/projects/webcoder/webcoder-lean-quality-gate-osv-scanner-status-2026-06-20
tags:
- webcoder
- osv-scanner
- quality-gate
- dependency-vulns
---

# webcoder feat/lean-quality-gate — osv-scanner gate status (2026-06-20)

## Finding (verified, fresh clone)
Branch `feat/lean-quality-gate` HEAD `3c2f30f`. The task's assumed root cause (committed `backend/venv/` polluting osv/opengrep) was ALREADY FIXED before this pass:
- Commit `3c2f30f` "chore(repo): untrack committed backend virtualenv (backend/venv)" — `git ls-files | grep venv` = 0. `.gitignore` has `venv/`.
- Commit `d666291` already removed the ProblemDetailPage `dangerouslySetInnerHTML` XSS sink (the "1 REAL first-party finding"), replaced with escaped React text nodes + test. opengrep first-party clean.

## Why osv is STILL red (different cause than task premise)
`osv-scanner scan source --config=osv-scanner.toml --recursive .` → exit 1.
Sources scanned: ONLY `backend/requirements.txt` (34 pkgs) + `frontend/webcoder_ui/package-lock.json` (1674 pkgs). ZERO venv/site-packages paths. So it is NOT noise.
**Total: 68 packages affected by 188 known vulns (12 Critical, 75 High, 77 Medium, 22 Low, 2 Unknown).**
- Backend (~85 rows): django 5.2.1→5.2.15, pyjwt 2.9.0 (one PYSEC-2025-183 has NO fix `--`), requests (unpinned, resolves stale 2.9.2), djangorestframework-simplejwt 5.5.0→5.5.1, django-allauth, sqlparse 0.5.3→0.5.4, pytest 8.3.2→9.0.3.
- Frontend (~187 rows): overwhelmingly TRANSITIVE deps of abandoned `react-scripts@5.0.1` (CRA) — webpack/webpack-dev-server/babel/svgo/serialize-javascript/ws/undici/storybook/etc. Cannot reach zero without npm `overrides` of dozens of transitive pins OR ejecting CRA → build-risky, requires npm relock + full frontend rebuild + 100%-coverage revalidation.

## Decision
Did NOT silently undertake the 188-vuln multi-package upgrade + CRA relock — far larger and build-riskier than the scoped "remove venv" task, and RAILS forbid baseline/blanket-ignore weakening. Both pre-identified fixes already landed. Surfaced the scope gap for a human call on the dependency-modernization effort (esp. CRA toolchain replacement).
