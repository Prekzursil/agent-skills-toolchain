#!/usr/bin/env python3
"""Probe 2: empty-source is VIOLATION; M-NN comes back REFUTED-AS-BRIEFED; re-derive verdicts."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from cnf0006_fingerprint import close_verdict, pair_status  # noqa: E402
from constants import (  # noqa: E402
    MNN_FACT_ID,
    OUTPUT_REL,
    SCHEMA_REL,
    UNIT_ID,
    catalog_sentinel,
)
from facts import _content_verdict  # noqa: E402
from gate import run_gate_controls  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0022-probe2 {msg}")
    return 1


def main() -> int:
    art_path = REPO / OUTPUT_REL
    if not art_path.is_file() or art_path.stat().st_size <= 0:
        return fail("artifact missing")
    text = art_path.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable:{type(exc).__name__}")
    if doc.get("unit_id") != UNIT_ID:
        return fail(f"unit_id {doc.get('unit_id')}")
    if catalog_sentinel() not in text:
        return fail("sentinel-absent")
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(doc)

    gates = run_gate_controls()
    if not gates["empty_source_is_violation"]:
        return fail("empty source was not classified VIOLATION")
    if not gates["same_fingerprint_rejected"]:
        return fail("same-fingerprint rerun was not rejected")
    if not gates["distinct_fingerprint_accepted"]:
        return fail("distinct fingerprint was not accepted")
    print(
        "empty_source=VIOLATION same_fp_rejected="
        f"{gates['same_fingerprint_rejected']} distinct_ok="
        f"{gates['distinct_fingerprint_accepted']}"
    )

    derived: list[tuple[str, str]] = []
    mnn = None
    for row in doc.get("records") or []:
        fid = str(row.get("fact_id") or "")
        try:
            measured = json.loads(row.get("verifier_output") or "")
        except json.JSONDecodeError:
            return fail(f"{fid} verifier_output is not JSON")
        content = _content_verdict(fid, measured)
        status = pair_status(row.get("source_probe"), row.get("verifier_probe"))
        verdict = close_verdict(status, content)
        derived.append((fid, verdict))
        if verdict != row.get("verdict"):
            return fail(
                f"{fid} re-derived {verdict} != recorded {row.get('verdict')} "
                "(reviewer read outputs first)"
            )
        if fid == MNN_FACT_ID:
            mnn = row
            live = int(measured.get("live_collision_count", -1))
            print(f"{MNN_FACT_ID} live_collision_count={live} verdict={verdict}")
            if verdict != "REFUTED-AS-BRIEFED" or live == 31:
                return fail("M-NN collision was not REFUTED-AS-BRIEFED")
    if mnn is None:
        return fail("M-NN record absent")

    controls = doc.get("controls") or {}
    if controls.get("empty_source_is_violation") is not True:
        return fail("artifact controls.empty_source_is_violation is not true")
    if controls.get("mnn_collision_refuted_as_briefed") is not True:
        return fail("artifact controls.mnn_collision_refuted_as_briefed is not true")
    tests = {t.get("id"): t.get("result") for t in (doc.get("tests") or []) if isinstance(t, dict)}
    for tid in (
        "test_source_and_verifier_probe_fingerprints_differ",
        "test_a_record_with_an_empty_source_probe_is_a_VIOLATION_not_a_pass",
        "known-refuted-control-m-nn-collision-REFUTED-AS-BRIEFED",
    ):
        if tests.get(tid) != "PASS":
            return fail(f"test {tid} is not PASS")
    print(f"re-derived={len(derived)} all match recorded verdicts")
    print("SUCCESS:SYN-0022-probe2 empty-source VIOLATION and M-NN REFUTED-AS-BRIEFED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
