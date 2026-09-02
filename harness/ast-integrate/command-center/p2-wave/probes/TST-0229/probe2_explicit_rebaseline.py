#!/usr/bin/env python3
"""Probe 2: explicit re-baseline succeeds and is recorded (both-states).

State A: a full benchmark run does not change the store digest.
State B: who/when/why re-baseline retargets the pointer, appends the audit
log, and keeps the old blob. Incomplete re-baseline is refused.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.bench.baseline_store import (  # noqa: E402
    BaselineStore,
    IncompleteRebaseline,
    Rebaseline,
    SilentOverwriteRefused,
    sha256_bytes,
)
from tools.bench.runner import run_benchmark  # noqa: E402

UID = "TST-0229"
CASE = "bench.case.alpha"
V1 = b"TST-0229-baseline-v1-nonzero"
V2 = b"TST-0229-rebaseline-v2-intentional"
WHO = "TST-0229-operator"
WHEN = "2026-08-24T18:00:00Z"
WHY = "intentional metric floor change after documented harness edit"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0229-probe2 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0229-p2-") as tmp:
        store = BaselineStore(Path(tmp) / "prod")
        d1 = store.write(CASE, V1)
        h_seed = store.store_digest()

        run_same = run_benchmark(store, CASE, lambda: V1)
        run_diff = run_benchmark(store, CASE, lambda: V2)
        h_after_runs = store.store_digest()
        runs_immutable = (
            run_same["store_unchanged"]
            and run_diff["store_unchanged"]
            and h_seed == h_after_runs
            and store.get(CASE) == V1
        )

        silent_refused = False
        try:
            store.write(CASE, V2)
        except SilentOverwriteRefused:
            silent_refused = True

        d2 = store.write(
            CASE,
            V2,
            rebaseline=Rebaseline(who=WHO, when=WHEN, why=WHY),
        )
        records = store.audit_records()
        matching = [
            r
            for r in records
            if r.get("kind") == "rebaseline"
            and r.get("case_id") == CASE
            and r.get("who") == WHO
            and r.get("when") == WHEN
            and r.get("why") == WHY
            and r.get("old_digest") == d1
            and r.get("new_digest") == d2
        ]
        h_after_rb = store.store_digest()
        old_blob_kept = (store.blobs / d1).is_file() and (
            store.blobs / d1
        ).read_bytes() == V1
        pointer_is_v2 = store.get(CASE) == V2 and d2 == sha256_bytes(V2)

        incomplete_refused = False
        try:
            store.write(
                CASE,
                b"TST-0229-v3",
                rebaseline=Rebaseline(who="x", when=WHEN, why="   "),
            )
        except IncompleteRebaseline:
            incomplete_refused = True

        payload = {
            "probe": "probe2-explicit-rebaseline",
            "unit_id": UID,
            "pass": False,
            "reviewer_id": "TST-0229-probe2-explicit-rebaseline",
            "independent": True,
            "full_run": {
                "store_digest_before": h_seed,
                "store_digest_after": h_after_runs,
                "equal": h_seed == h_after_runs,
                "same_payload_match": run_same["comparison"]["match"],
                "different_payload_mismatch": not run_diff["comparison"]["match"],
                "wrote_store": run_same["wrote_store"] or run_diff["wrote_store"],
            },
            "silent_overwrite_refused": silent_refused,
            "rebaseline": {
                "old_digest": d1,
                "new_digest": d2,
                "store_digest_before": h_after_runs,
                "store_digest_after": h_after_rb,
                "store_digest_changed": h_after_runs != h_after_rb,
                "pointer_is_new_payload": pointer_is_v2,
                "old_blob_retained": old_blob_kept,
                "audit_records": records,
                "matching_audit_count": len(matching),
                "who": WHO,
                "when": WHEN,
                "why": WHY,
            },
            "incomplete_rebaseline_refused": incomplete_refused,
            "runs_immutable": runs_immutable,
        }
        payload["pass"] = bool(
            runs_immutable
            and silent_refused
            and pointer_is_v2
            and old_blob_kept
            and len(matching) == 1
            and h_after_runs != h_after_rb
            and incomplete_refused
            and run_same["comparison"]["match"]
            and not run_diff["comparison"]["match"]
        )
        print(json.dumps(payload, sort_keys=True))

        if not runs_immutable:
            return fail("full run mutated the baseline store")
        if not run_same["comparison"]["match"]:
            return fail("identical payload did not match baseline")
        if run_diff["comparison"]["match"]:
            return fail("different payload matched baseline (dead compare)")
        if not silent_refused:
            return fail("silent overwrite was not refused before re-baseline")
        if not pointer_is_v2:
            return fail("explicit re-baseline did not retarget the pointer")
        if not old_blob_kept:
            return fail("old content-addressed blob was deleted")
        if len(matching) != 1:
            return fail(f"audit log missing who/when/why record count={len(matching)}")
        if h_after_runs == h_after_rb:
            return fail("store digest unchanged after recorded re-baseline")
        if not incomplete_refused:
            return fail("blank why was accepted as a re-baseline")
        print(
            "SUCCESS:TST-0229-probe2 full run immutable; "
            "explicit re-baseline recorded who/when/why"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
