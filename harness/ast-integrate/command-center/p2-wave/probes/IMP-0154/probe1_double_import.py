#!/usr/bin/env python3
"""Named probe 1: double import yields 1 row and 2 observations.

Two mechanically different adapters (local-repo shaped, live-tree shaped)
import the same URI and the same bytes. The registry must collapse them
to one candidate and keep both provenance observations. Counts are
computed from the ledger, not asserted.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from foundry.candidate_registry import (  # noqa: E402
    CandidateRegistry,
    ImportRecord,
    verify_chain,
)

UNIT = "IMP-0154"
FIX = HERE / "fixtures" / "double-import" / "wf.json"
URI = "foundry://colliding-catalogs/wf.double-import.fixture"
ART = REPO / "command-center" / "receipts" / "IMP-0154.json"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    if not FIX.is_file():
        return fail(f"fixture missing {FIX.relative_to(REPO)}")
    payload = FIX.read_bytes()
    with tempfile.TemporaryDirectory(prefix="imp0154-p1-") as tmp:
        ledger = Path(tmp) / "candidates.jsonl"
        reg = CandidateRegistry(ledger)
        first = reg.import_record(
            ImportRecord(
                source_uri=URI,
                content=payload,
                retrieval_method="read-path",
                adapter_id="IMP-0150",
                retrieved_at="2026-08-24T18:00:00+00:00",
                extra={"catalog": "local-repo"},
            )
        )
        second = reg.import_record(
            ImportRecord(
                source_uri=URI,
                content=payload,
                retrieval_method="read-path",
                adapter_id="IMP-0151",
                retrieved_at="2026-08-24T18:00:01+00:00",
                extra={"catalog": "live-harness"},
            )
        )
        rows = reg.row_count()
        obs_key = reg.observation_count(URI, first.content_hash)
        obs_total = reg.observation_count()
        chain = verify_chain(ledger)
        snapshot = reg.export_snapshot()
        events = reg.events()

    if first.action != "insert":
        return fail(f"first action={first.action} want=insert")
    if second.action != "observe":
        return fail(f"second action={second.action} want=observe")
    if first.candidate_id != second.candidate_id:
        return fail("candidate_id diverged across identical imports")
    if rows != 1:
        return fail(f"row_count={rows} want=1")
    if obs_key != 2:
        return fail(f"observation_count={obs_key} want=2")
    if obs_total != 2:
        return fail(f"observation_count_total={obs_total} want=2")
    if first.row_count != 1 or second.row_count != 1:
        return fail(
            f"running row_count first={first.row_count} second={second.row_count}"
        )
    if not chain.ok:
        return fail(f"chain broken: {chain.error}")
    if chain.events != 3:
        # 1 candidate + 2 observations
        return fail(f"event_count={chain.events} want=3")
    kinds = [e["kind"] for e in events]
    if kinds != ["candidate", "observation", "observation"]:
        return fail(f"kinds={kinds}")
    adapters = [e.get("adapter_id") for e in events if e["kind"] == "observation"]
    if adapters != ["IMP-0150", "IMP-0151"]:
        return fail(f"adapters={adapters}")
    if snapshot["row_count"] != 1 or snapshot["observation_count"] != 2:
        return fail(f"snapshot mismatch {snapshot['row_count']}/{snapshot['observation_count']}")

    # Distinct URI, identical bytes: a different identity, not a collapse.
    with tempfile.TemporaryDirectory(prefix="imp0154-p1b-") as tmp:
        ledger = Path(tmp) / "candidates.jsonl"
        reg = CandidateRegistry(ledger)
        a = reg.import_bytes(
            URI, payload, retrieval_method="read-path", adapter_id="A"
        )
        b = reg.import_bytes(
            URI + "#other",
            payload,
            retrieval_method="read-path",
            adapter_id="B",
        )
        if a.content_hash != b.content_hash:
            return fail("same bytes produced different hashes")
        if reg.row_count() != 2:
            return fail(f"distinct-uri row_count={reg.row_count()} want=2")

    if not ART.is_file():
        return fail(f"receipt missing {ART.relative_to(REPO)}")
    receipt = json.loads(ART.read_text(encoding="utf-8"))
    measured = (receipt.get("measured") or {}).get("double_import") or {}
    if measured.get("row_count") != 1 or measured.get("observation_count") != 2:
        return fail(f"receipt double_import {measured} does not match live 1/2")
    if "SUCCESS:IMP-0154" not in ART.read_text(encoding="utf-8"):
        return fail("receipt sentinel absent")

    out = {
        "pass": True,
        "probe": "probe1-double-import",
        "unit_id": UNIT,
        "row_count": rows,
        "observation_count": obs_key,
        "event_count": chain.events,
        "first_action": first.action,
        "second_action": second.action,
        "candidate_id": first.candidate_id,
        "adapters": adapters,
        "chain_ok": chain.ok,
        "distinct_uri_same_bytes_rows": 2,
        "computed_not_asserted": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"row_count={rows} observation_count={obs_key} "
        f"actions={first.action},{second.action} chain_ok={chain.ok}"
    )
    print(f"SUCCESS:{UNIT}-probe1 double-import 1 row, 2 observations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
