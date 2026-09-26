---
name: QZP v2 Phase 2 — Codecov flag-split
description: Phase 2 of QZP v2 shipped per-flag Codecov upload + ingest validator;
  event-link must bump reusable-workflow SHAs after platform merges to verify the
  58% → 100% fix
type: project
originSessionId: 7e07bd36-c338-4890-8179-e112e67d5844
permalink: main/claude-memory/documents-git-hub-event-link/project-qzp-phase2
---

Phase 2 of `quality-zero-platform` v2 rewrites `reusable-codecov-analytics.yml` to upload coverage once per `coverage.inputs[]` row (keyed by `flag`), replacing the single `codecov-action` call that silently merged inputs. The validator `scripts/quality/validate_codecov_flags.py` polls Codecov's v2 commit API to fail CI if any declared flag is missing from the report.

**Why:** Event-link shipped at 58% aggregate coverage because Codecov collapsed its three declared inputs (backend, ui, backend-integration) into a single unflagged blob. Each input was individually at 100%.

**How to apply:** After Phase 2's PR #89 merges to platform `main`:
1. Update event-link's `.github/workflows/codecov-analytics.yml` SHA pin (currently `d7a94db4ab57df42940832cf67b730c673af7da6`) to point at the new platform-main SHA.
2. Re-trigger event-link CI (push a trivial commit or re-run the workflow).
3. Verify Codecov shows three per-flag rows (backend, ui, backend-integration) each at 100%, with an accurate aggregate, not the previous 58% silent-drop.
4. The ingest validator's `if: always()` step will fail CI if any declared flag doesn't land in Codecov — the new guard against the silent-drop class.

**Validator auth note:** The `CODECOV_TOKEN` in CI is an upload (write-scope) token. The Codecov v2 commit API requires a separate read-scope Bearer token. The validator treats 401/403 as warn-and-skip, not hard-fail, so adoption isn't blocked on repos without the read token.