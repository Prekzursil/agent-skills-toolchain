#!/usr/bin/env python3
"""Named probe 2: content change on the same URI mints a NEW row.

Mechanically independent of probe 1 (which never mutates bytes). This
probe writes v1, then v2 at the same URI, then:

1. Computes row_count == 2 and both content hashes still present.
2. Re-reads the v1 candidate event_hash after the v2 insert (no silent
   overwrite).
3. Verifies the hash chain, then mutates a prior line in a copy and
   confirms the detector fires (both-states control).
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
    LedgerCorruptError,
    content_sha256,
    verify_chain,
)

UNIT = "IMP-0154"
V1 = HERE / "fixtures" / "content-change" / "wf-v1.json"
V2 = HERE / "fixtures" / "content-change" / "wf-v2.json"
URI = "foundry://content-change/wf.content-change.fixture"
ART = REPO / "command-center" / "receipts" / "IMP-0154.json"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def mutate_first_event(src: Path, dest: Path) -> None:
    lines = src.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise RuntimeError("empty ledger")
    event = json.loads(lines[0])
    event["content_hash"] = "0" * 64
    lines[0] = json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    if not V1.is_file() or not V2.is_file():
        return fail("content-change fixtures missing")
    b1 = V1.read_bytes()
    b2 = V2.read_bytes()
    h1 = content_sha256(b1)
    h2 = content_sha256(b2)
    if h1 == h2:
        return fail("v1 and v2 are byte-identical; fixture is vacuous")

    with tempfile.TemporaryDirectory(prefix="imp0154-p2-") as tmp:
        root = Path(tmp)
        ledger = root / "candidates.jsonl"
        reg = CandidateRegistry(ledger)
        r1 = reg.import_bytes(
            URI,
            b1,
            retrieval_method="read-path",
            adapter_id="IMP-0150",
            retrieved_at="2026-08-24T18:10:00+00:00",
        )
        events_after_v1 = reg.events()
        v1_event = next(e for e in events_after_v1 if e["kind"] == "candidate")
        v1_hash = v1_event["event_hash"]
        v1_content = v1_event["content_hash"]
        r2 = reg.import_bytes(
            URI,
            b2,
            retrieval_method="read-path",
            adapter_id="IMP-0150",
            retrieved_at="2026-08-24T18:10:01+00:00",
        )
        rows = reg.candidates()
        chain_good = verify_chain(ledger)
        events_after_v2 = reg.events()
        v1_again = next(
            e
            for e in events_after_v2
            if e["kind"] == "candidate" and e["content_hash"] == h1
        )
        prefix_ok = v1_again["event_hash"] == v1_hash and v1_again["content_hash"] == v1_content

        mutated = root / "mutated.jsonl"
        mutate_first_event(ledger, mutated)
        chain_bad = verify_chain(mutated)
        load_fired = False
        load_error = ""
        try:
            CandidateRegistry(mutated)
        except LedgerCorruptError as exc:
            load_fired = True
            load_error = str(exc)

        same_uri_hashes = sorted(r["content_hash"] for r in rows)
        snapshot = reg.export_snapshot()

    if r1.action != "insert" or r2.action != "insert":
        return fail(f"actions={r1.action},{r2.action} want=insert,insert")
    if r1.candidate_id == r2.candidate_id:
        return fail("content change reused candidate_id (silent overwrite shape)")
    if len(rows) != 2:
        return fail(f"row_count={len(rows)} want=2")
    if same_uri_hashes != sorted([h1, h2]):
        return fail(f"uri hashes={same_uri_hashes} want={[h1, h2]}")
    if not prefix_ok:
        return fail("v1 candidate event_hash moved after v2 import")
    if not chain_good.ok:
        return fail(f"good chain broken: {chain_good.error}")
    if chain_bad.ok:
        return fail("mutated ledger still verified — detector is dead")
    if not load_fired:
        return fail("CandidateRegistry accepted a mutated ledger")
    if r1.observation_count_for_key != 1 or r2.observation_count_for_key != 1:
        return fail(
            f"obs per row r1={r1.observation_count_for_key} r2={r2.observation_count_for_key}"
        )
    if snapshot["row_count"] != 2:
        return fail(f"snapshot row_count={snapshot['row_count']}")

    if not ART.is_file():
        return fail(f"receipt missing {ART.relative_to(REPO)}")
    receipt = json.loads(ART.read_text(encoding="utf-8"))
    measured = (receipt.get("measured") or {}).get("content_change") or {}
    if measured.get("row_count") != 2:
        return fail(f"receipt content_change {measured} does not match live 2 rows")
    if measured.get("v1_event_hash_unchanged") is not True:
        return fail("receipt did not record v1_event_hash_unchanged=true")
    if "SUCCESS:IMP-0154" not in ART.read_text(encoding="utf-8"):
        return fail("receipt sentinel absent")

    out = {
        "pass": True,
        "probe": "probe2-content-change",
        "unit_id": UNIT,
        "row_count": len(rows),
        "v1_content_hash": h1,
        "v2_content_hash": h2,
        "v1_event_hash_unchanged": prefix_ok,
        "chain_ok_on_good": chain_good.ok,
        "chain_ok_on_mutated": chain_bad.ok,
        "load_fired_on_mutated": load_fired,
        "load_error": load_error,
        "same_uri_hashes": same_uri_hashes,
        "computed_not_asserted": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"rows={len(rows)} v1_unchanged={prefix_ok} "
        f"good_chain={chain_good.ok} mutated_chain={chain_bad.ok} "
        f"load_fired={load_fired}"
    )
    print(f"SUCCESS:{UNIT}-probe2 content-change new row, hash chain detects rewrite")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
