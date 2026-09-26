---
title: momentstudio coverage worker w3 findings (2026-06-21)
type: note
permalink: main/projects/momentstudio/momentstudio-coverage-worker-w3-findings-2026-06-21
tags:
- momentstudio
- coverage
- testing
- pytest
---

# momentstudio coverage worker w3 (feat/lean-quality-gate)

Wrote disjoint w3 test files for 4 source files. Repo: Prekzursil/momentstudio.

## Key environment gotchas (reusable)
- Gate = `coverage run --source=backend/app -m pytest backend/tests` (codacy-coverage.yml), pyproject `[tool.coverage.run]` branch+concurrency=thread,greenlet. NOT pytest-cov.
- **Python MUST be 3.12** (CI target; Dockerfile python:3.12-slim). On 3.14, bcrypt 5.0.0 PyO3 abi3 raises "PyO3 modules compiled for CPython 3.8 or older may only be initialized once per interpreter process" under coverage tracing. Use `py -3.12 -m venv`, install requirements.txt + requirements-ci.txt + greenlet + pytest-cov + black.
- **Coverage `--source` MUST be the DIRECTORY form `backend/app`** (filter report with `--include`). Module-form `--source=app.api.v1.auth` pre-imports the module and re-triggers the bcrypt PyO3 double-init crash.
- Gate runs ubuntu, NO postgres service; `test_integration_postgres.py` self-skips (`RUN_POSTGRES_INTEGRATION!=1`). So the DB layer under the gate is SQLite/aiosqlite via conftest in-memory engines.
- **UUID wall**: ORM uses `sqlalchemy.dialects.postgresql.UUID(as_uuid=True)` (no string-coercing TypeDecorator). `session.get(Model, "<str-uuid>")` raises `AttributeError: 'str' object has no attribute 'hex'` under aiosqlite. Only works with real `uuid.UUID` objects.

## Results (siblings + w3 file, dir-source)
- payments.py: 100% line+branch. Fully mockable (stub `payments.stripe.*`, patch `payments.is_mock_payments`/`is_stripe_configured`/`init_stripe`). IntegrityError recovery block needs commit-raise + rollback no-op + selective-execute stub (real DB conflict surfaces as MissingGreenlet, not catchable).
- cli.py: ~0% -> 78% (gate-BLOCKED ceiling). import_data catalog/address/shipping/order-item blocks pass string UUIDs to session.get + null product_id on NOT-NULL FK = postgres-only. Lines 65 (defensive unreachable) + 791 (__main__) = only legit pragmas. CANNOT reach 100% under gate env without orchestrator decision.
- auth.py: 68% -> 74%. Covered export-job endpoints, account-deletion, language/notifications/training-mode, logout, password-change, verify-request. Residual = large DB endpoints (sessions mgmt, step-up, 2FA, profile) reachable via TestClient but unwritten (budget).
- catalog.py: 73% -> 78%. Covered all pure helpers (slugify, _to_decimal, _validate_*, _compute_sale_price, _sync_sale_fields, apply_*_translation, is_sale_active, image-stats) + category CRUD (create/update/reorder + parent-cycle validation). Residual = bulk_update_products, product clone, stock adjustments, feed CSV, search blocks (reachable, unwritten, budget).

## Patterns
- auth TestClient fixture: in-memory engine + `app.dependency_overrides[get_session]`; MUST seed ContentBlocks page.terms-and-conditions + page.privacy-policy (registration requires them).
- cli: monkeypatch `app.cli.SessionLocal` with in-memory factory; main() dispatch via monkeypatched coroutines + `asyncio.run` -> coro.close().

Files: backend/tests/test_w3_{cli,payments,auth,catalog}.py. HEAD d6dc636.
