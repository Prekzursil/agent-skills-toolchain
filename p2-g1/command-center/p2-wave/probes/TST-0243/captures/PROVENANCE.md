# run-ledger.jsonl provenance (TST-0243)

- Original build-host source: `/opt/p2/supervisor.log` LAUNCH/DONE-OK pairs
  (93 records). That log is absent on this checkout, so the snapshot was
  RE-CAPTURED from the live source available here.
- This checkout's source: `command-center/receipts/*.json` timestamps
  (`timestamps.started_at`/`ended_at`, or an explicitly recorded
  `timestamps.duration_seconds`), joined per unit to its class by id
  prefix. Each JSONL row records its own `source` field:
  `receipt-timestamps`.
- Semantics differ from the original source: receipt timestamps span the
  unit's recorded build window (which can include idle queue time), not a
  supervisor LAUNCH-to-DONE work interval. The join therefore reports
  catalog DEFECT rows on this checkout where the build-host run reported
  none; `ledger.py:capture_from_supervisor_log` is kept for the original
  source and the probe output names the sources actually used.
- Rebuilt deterministically by `probe1_mechanical_join.py:ensure_snapshot`
  (delete this file and re-run the probe to reproduce it byte-identically).
