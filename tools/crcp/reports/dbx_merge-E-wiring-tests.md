# CRCP merge-E wiring tests

## Result

PASS — 6 unittest cases completed offline on the Linux Databricks job node.

Command:

```text
python /dbfs/tmp/crcp-e2e-merge/results/run_merge_tests.py
```

Observed summary:

```text
Ran 6 tests in 0.015s
OK
```

## What was wired

- The runner adds both `/local_disk0/codexwork/bundle` and its `crcp/` directory
  to `sys.path`. This supports package imports and the legacy flat-import layout.
- Import smoke coverage joins the existing `EventSpool`, `event_key`,
  `acquire_singleton_lock`, `classify_sse`, and `full_health` APIs in one suite.
- Durable spool coverage calls `EventSpool.put_observed` twice with the same
  logical event, checks both returned keys against `event_key`, and verifies the
  SQLite spool contains exactly one row.
- SSE coverage sends complete, truncated, and explicit-error fixtures through
  `classify_sse(200, fixture)` and requires `COMPLETE`, `UNCERTAIN_ACCEPTED`, and
  `ERROR`, respectively.
- Singleton coverage acquires and releases a lease using a temporary local path.
  No process termination or shared lock path is involved.
- `full_health` is imported but not called, avoiding CLI, credential, localhost,
  or live-network probes.

## Call sites

- `test_merge_wiring.MergeWiringTests.test_put_observed_is_idempotent_for_same_event_key`
  -> `crcp.spool.EventSpool.put_observed`, `EventSpool.get`, and
  `crcp.spool.event_key`.
- `test_merge_wiring.MergeWiringTests.test_sse_*`
  -> `crcp.sse_contract.classify_sse`.
- `test_merge_wiring.MergeWiringTests.test_singleton_lock_can_be_acquired_and_released_locally`
  -> `crcp.singleton.acquire_singleton_lock` and the returned lease's `release`.
- `test_merge_imports.MergeImportTests.test_required_merge_surfaces_import`
  -> package-level imports from `crcp.spool`, `crcp.singleton`,
  `crcp.sse_contract`, and `crcp.health`.

## Residual risk

- These tests verify the merged API boundaries, but exclusive file ownership
  prevented changing production call sites such as `live_bridge.cycle_once` or
  `write_path`; their runtime orchestration remains outside this unit.
- CRCP currently contains two SSE APIs (`sse_contract.classify_sse` and
  `sse_validate.classify_sse_stream`) with different success/error vocabulary.
  This suite targets the existing contract API and does not select a global
  production entrypoint.
- CRCP also contains a separate `event_spool` implementation. This suite targets
  the P0 `crcp.spool` API required by `put_observed`; callers using
  `crcp.event_spool` remain a distinct compatibility path.
- Health behavior is intentionally not executed because it can inspect local
  credentials, CLIs, and services. Only its import boundary is covered.

No source modules were modified. All generated files are confined to
`/dbfs/tmp/crcp-e2e-merge/results/`.

UNIT-COMPLETE: merge-E-wiring-tests
