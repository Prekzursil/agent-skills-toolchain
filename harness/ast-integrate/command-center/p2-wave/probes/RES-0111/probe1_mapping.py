#!/usr/bin/env python3
"""Probe 1: every named primitive is mapped to a spec-list class or dropped.

Both-states: the live table passes; a force-fit of exactly-once onto
duplicate-dispatch fails; two-phase commit (control) is dropped; a known
mapped primitive is not dropped. Dropped-unmapped count is stated and > 0.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import contract as C  # noqa: E402

ART = REPO / C.OUT_REL


def main() -> int:
    both = C.both_states()
    for key in (
        "good_table_ok",
        "control_2pc_dropped",
        "known_idempotency_mapped",
        "e3_without_baseline_rejected",
        "elegance_exactly_once_rejected",
    ):
        print(f"{key}={both[key]}")
        if not both[key]:
            print(f"FAILED:RES-0111-probe1 {key}")
            return 1
    print(f"dropped_unmapped_count={both['dropped_unmapped_count']}")
    print(f"good_why={both['good_why']}")
    print(f"elegance_why={both['elegance_why']}")

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:RES-0111-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != C.UNIT:
        print("FAILED:RES-0111-probe1 unit_id", doc.get("unit_id"))
        return 1
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:RES-0111-probe1 self-declared {st}")
        return 1
    if C.SENTINEL not in text:
        print("FAILED:RES-0111-probe1 sentinel absent")
        return 1
    rows = doc.get("primitive_to_failure_class_mapping") or []
    ok, why = C.check_mapping_table(rows)
    print(f"artifact_table_ok={ok} {why}")
    if not ok:
        print("FAILED:RES-0111-probe1 artifact mapping")
        return 1
    stated = doc.get("primitives_dropped_unmapped_count")
    live_n = C.dropped_unmapped_count(rows)
    if stated != live_n or live_n != both["dropped_unmapped_count"]:
        print(f"FAILED:RES-0111-probe1 dropped-count drift stated={stated} live={live_n}")
        return 1
    if "primitive-to-failure-class mapping" not in text:
        print("FAILED:RES-0111-probe1 mapping phrase absent")
        return 1
    print(
        "SUCCESS:RES-0111-probe1 mapping totality, dropped-count control, "
        f"both-states n_drop={live_n}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
