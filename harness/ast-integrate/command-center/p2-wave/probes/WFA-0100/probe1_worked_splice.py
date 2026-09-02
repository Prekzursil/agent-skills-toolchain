#!/usr/bin/env python3
"""Probe 1: worked INSERT splice; output IR validates; stage order matches.

Evidence A. Also: fused result decomposes to host and donor ids; host stages
the splice did not touch are byte-identical.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from decompose import decompose, host_stages_match  # noqa: E402
from ir import untouched_host_stages, validate_ir  # noqa: E402
from scenario import (  # noqa: E402
    DONOR_INDEX,
    INSERT_INDEX,
    declared_insertion,
    host_workflow,
    matching_donor,
)
from stage_splice import stage_splice  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0100-fusion-stage-splice.json"


def _fail(msg: str) -> int:
    print(f"FAILED:WFA-0100-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return _fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if not isinstance(doc, dict):
        return _fail("artifact not an object")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return _fail(f"artifact self-declared {st}")
    if "SUCCESS:WFA-0100" not in text:
        return _fail("sentinel absent")
    if doc.get("kind") != "FusionResult":
        return _fail(f"kind {doc.get('kind')!r} is not FusionResult")

    host = host_workflow()
    donor = matching_donor()
    declared = declared_insertion()
    live = stage_splice(host, donor, INSERT_INDEX, DONOR_INDEX)
    if live.get("status") != "emitted" or live.get("fusion") is None:
        return _fail(f"matching insert refused: {live.get('reason')}")
    if live.get("trace") != ["type-check", "emit"]:
        return _fail(f"matching trace {live.get('trace')!r} is not check-then-emit")

    fusion = live["fusion"]
    ir = validate_ir(fusion)
    if not ir["ok"]:
        return _fail(f"fused IR invalid: {ir['errors']}")

    order = [s.get("id") for s in fusion.get("stages") or []]
    expected = declared["expected_order"]
    if order != expected:
        return _fail(f"stage order {order} != declared {expected}")
    if order[INSERT_INDEX] != expected[INSERT_INDEX]:
        return _fail("inserted stage not at declared insert_index")
    if len(order) != len(host["stages"]) + 1:
        return _fail(f"stage count {len(order)} is not host+1")

    rows = untouched_host_stages(host, fusion, INSERT_INDEX)
    if not rows or any(not r["identical"] for r in rows):
        return _fail(f"untouched host stages not byte-identical {rows}")
    if len(rows) != len(host["stages"]):
        return _fail(f"untouched count {len(rows)}")

    dec = decompose(fusion)
    if not dec.get("ok"):
        return _fail("decompose failed")
    if set(dec.get("source_ids") or []) != {host["id"], donor["id"]}:
        return _fail(f"decompose source_ids {dec.get('source_ids')} != host+donor")
    match = host_stages_match(host, dec)
    if not match.get("ok"):
        return _fail(f"reconstructed host stages drifted {match}")

    art_fused = doc.get("fused") or doc.get("fused_ir") or {}
    art_order = [s.get("id") for s in (art_fused.get("stages") or [])]
    if art_order != order:
        return _fail(f"artifact fused order {art_order} != live {order}")
    art_ir = validate_ir(art_fused)
    if not art_ir["ok"]:
        return _fail(f"artifact fused IR invalid: {art_ir['errors']}")

    summary = {
        "probe": "probe1-worked-splice",
        "unit_id": "WFA-0100",
        "pass": True,
        "status": live.get("status"),
        "stage_order": order,
        "insert_index": INSERT_INDEX,
        "ir_ok": True,
        "decompose_source_ids": dec.get("source_ids"),
        "untouched_identical": True,
        "host_reconstructed": True,
        "fusion_id": fusion.get("id"),
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:WFA-0100-probe1 worked splice IR-valid stage-order host-untouched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
