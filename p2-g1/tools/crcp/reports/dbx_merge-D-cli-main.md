# CRCP merge-D CLI integration

## Result

Produced a full replacement `crcp/__main__.py` with additive CLI wiring only. No source modules outside the owned file were changed.

## Wiring and call sites

- Added `_livez()` as a local-only liveness probe. It emits `{"live": true, "status": "LIVE"}` and performs no network request.
- Added `_health_with_probes()`, which calls the existing `full_health()` API and the existing `wfmon_export.build_wfmon_report()` readiness policy, then attaches top-level `livez` and `readyz` sections.
- Changed `cmd_health()` to use `_health_with_probes()`. JSON output and `health_live.json` now include both sections; table output prints a compact JSON probe section after the existing table.
- Added `cmd_livez()` and the `crcp livez` parser entry. It prints JSON and exits 0.
- Added `cmd_readyz()` and the `crcp readyz` parser entry. It prints the existing operational readiness result and exits 0 only when `ready` is true.
- Verified `crcp.spool`, `crcp.reconcile`, and `crcp.wfmon_export` import cleanly. CLI help documents the established `python -m crcp.reconcile {scan,requeue,dead-letter}` entry point and `crcp.spool.EventSpool` API without inventing a second spool/reconcile interface.

## Validation

- Candidate compiles with `python -m py_compile`.
- `python -m crcp livez` emitted valid JSON without network access.
- `python -m crcp --help` exposed `livez`, `readyz`, and the spool/reconcile operational documentation.
- Bundle-shaped smoke tests confirmed `health --json` contains valid `livez` and `readyz` sections.
- Repository contract suite: 21 tests passed.
- A non-ready environment correctly produced exit 1 for `readyz` and `health`; this is expected health signaling, not a command failure.

## Residual risk

- `readyz` deliberately inherits the existing `full_health()` rail probes and readiness gates. Missing poll/lease metadata remains `unknown`, so a CLI process can be live while not ready.
- `health` retains its pre-existing assumption that the CRCP root has a `reports/` directory before writing report files. The supplied bundle has that layout.
- Readiness behavior remains coupled to the existing wfmon policy and persisted state locations; deployment-specific state paths may yield `unknown` until the live bridge has written metadata.

UNIT-COMPLETE: merge-D-cli-main
