#!/usr/bin/env python3
"""Probe 1: sampling frame, A B A B interleaving, artifact raw values attached."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

ART = REPO / H.OUT_REL
SCHEMA = REPO / H.SCHEMA_REL


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0052-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != H.UNIT:
        return fail(f"unit_id={doc.get('unit_id')}")
    text = json.dumps(doc)
    if H.COMPLETION_SENTINEL not in text:
        return fail("completion_sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errs = sorted(
        jsonschema.Draft7Validator(schema).iter_errors(doc), key=lambda e: list(e.path)
    )
    if errs:
        return fail(f"schema {errs[0].message}")

    rows = H.make_rows()
    frame = doc.get("sampling_frame") or {}
    if frame.get("seed") != H.SEED:
        return fail("seed mismatch")
    if H.payload_digest(rows) != frame.get("payload_sha256"):
        return fail("payload redraw not identical")
    if H.payload_digest(H.make_rows()) != frame.get("payload_sha256"):
        return fail("second redraw not identical")

    benches = doc.get("benchmarks") or []
    if len(benches) < 2:
        return fail("need two benchmarks")
    for b in benches:
        inter = b.get("interleaving") or {}
        order = inter.get("order") or []
        if not H.is_abab(order):
            return fail(f"{b.get('id')} order not A B A B: {order}")
        if H.is_blocked(order):
            return fail(f"{b.get('id')} blocked order")
        arms = {a["id"]: a for a in b.get("arms") or []}
        if "A" not in arms or "B" not in arms:
            return fail(f"{b.get('id')} missing arms")
        if len(arms["A"]["raw_ns"]) < 11 or len(arms["B"]["raw_ns"]) < 11:
            return fail(f"{b.get('id')} under-sampled")
        seq = inter.get("sequence") or []
        if len(seq) != 22:
            return fail(f"{b.get('id')} sequence length {len(seq)}")
        for i, rec in enumerate(seq):
            want = "A" if i % 2 == 0 else "B"
            if rec.get("arm") != want:
                return fail(f"{b.get('id')} sequence[{i}]={rec}")

    blocked = (doc.get("interleaving") or {}).get("blocked_control") or {}
    if not blocked.get("blocked") or blocked.get("interleaved"):
        return fail("blocked control not recorded as rejected")

    live = H.run_interleaved(H.snap_a, H.snap_b_identity, rows)
    if not live["interleaved"] or live["blocked"]:
        return fail(f"live interleaving failed order={live['order']}")
    if live["n_reps"] != 11:
        return fail("live n_reps")

    ia = doc.get("interval_arithmetic") or {}
    ident = ia.get("identity") or {}
    if ident.get("raw_A_ns") != benches[0]["arms"][0]["raw_ns"]:
        return fail("interval_arithmetic identity raw_A mismatch")
    if ident.get("raw_B_ns") != benches[0]["arms"][1]["raw_ns"]:
        return fail("interval_arithmetic identity raw_B mismatch")

    out = {
        "benchmarks_checked": [b["id"] for b in benches],
        "live_interleaved": True,
        "live_order": live["order"],
        "pass": True,
        "payload_redraw_identical": True,
        "probe": "probe1-interleaved",
        "seed": H.SEED,
        "unit_id": H.UNIT,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:CNF-0052-probe1 interleaved A B A B and sampling frame")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
