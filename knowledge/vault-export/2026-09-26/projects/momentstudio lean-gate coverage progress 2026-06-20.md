---
title: momentstudio lean-gate coverage progress 2026-06-20
type: note
permalink: main/projects/momentstudio-lean-gate-coverage-progress-2026-06-20
tags:
- momentstudio
- coverage
- lean-quality-gate
---

# momentstudio lean-gate 100% coverage drive

Branch `feat/lean-quality-gate`, repo Prekzursil/momentstudio. Goal: 100% Python line+branch + fully green lean gate (quality-zero-platform reusable workflow @v1).

## Gate facts (verified)
- Lean coverage gate command: `python -m pytest --cov --cov-branch --cov-fail-under=100` (reads pyproject `[tool.coverage.run] source=["backend/app"]`).
- Only the `gate-tests-coverage python` lane fails; ruff/format/basedpyright PASS on my work; gitleaks clean; opengrep gated behind coverage (fails fast) but my changes use no flagged patterns.
- CI python 3.12. Tests use anyio/`asyncio.run(flow())` pattern (NOT pytest-asyncio).

## Test pattern (reusable)
- Added `make_memory_session_factory()` to `backend/tests/conftest.py` — in-memory SQLite, all tables, `asyncio.run` per test.
- Each module: own `test_lean_*.py`. Verify per-module with `pytest <file> --cov --cov-report= ; coverage report -m | grep <mod>`.
- ALWAYS run `ruff check` (not just format) + confirm output BEFORE commit (got bitten once by F401 unused import committed).
- Unreachable defensive branches: `# pragma: no cover - <reason>` (used in pii.py sub-6-digit phone, pricing.py negative total — both provably unreachable).

## Progress
- Baseline 52% (347 tests, 84/192 files at 100%). Now 53% (485 tests, 107/192 at 100%). +23 modules to 100%, +138 tests, 9 batches committed+pushed (HEAD cdfefe33).
- Done 100%: step_up, payment_provider, analytics_tokens, newsletter_tokens, legal_consents, tracking, promo_usage, core/metrics, schemas/promo, schemas/user, og_images, schemas/media, schemas/content, pick_lists, pricing, pii, captcha, sitemap, structured_data, audit_chain, address, notifications, self_service.

## Remaining (honest): 85 files, 17,691 missing units
- large(>=300 stmts)=24 files / 13,797 missing (THE BULK): orders.py(1614m), admin_dashboard.py(1336m), services/content.py(1171m), catalog.py(1130m), coupons_v2.py(957m), auth API(833m), order svc(820m), media_dam(757m), content API(561m), catalog API(537m), cli.py(532m/0%), email(465m), auth svc(424m)...
- mid(80-300)=30 files / 3,095m ; small(<80)=31 files / 799m.
- Next-best ROI: knock out the 31 small + 30 mid files (clean 100% each via the established pattern) before the giant API files which need full authenticated TestClient fixtures (admin/customer tokens via create_user+issue_tokens_for_user, see test_fx_api.py). Realistic estimate to 100%: many more multi-hour passes (~15-20k lines of tests).
