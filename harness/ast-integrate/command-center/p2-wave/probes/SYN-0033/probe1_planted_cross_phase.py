#!/usr/bin/env python3
"""Probe 1: planted cross-phase contradiction fires; intra-phase pairs stay out."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import controls as C  # noqa: E402
import overclaim as O  # noqa: E402

ART = REPO / "command-center/synthesis/SYN-0033.cross-phase-contradictions.json"
SENTINEL = (
    "SUCCESS:SYN-0033 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the examined-pair count "
    "is published and every open contradiction names a settling probe. Any "
    "other terminal state is FAILED:SYN-0033 <classification> with the "
    "diagnostic tail attached."
)


def main() -> int:
    planted = C.planted_cross_phase_detected()
    intra = C.intra_phase_excluded()
    named = C.open_rows_name_settling_probe()
    checks = [
        ("planted_detected", planted.get("ok")),
        ("intra_phase_excluded", intra.get("ok")),
        ("open_named_probe", named.get("ok")),
        ("planted_examined_nonzero", planted.get("examined", 0) > 0),
    ]
    for name, ok in checks:
        print(f"{name}={ok}")
        if not ok:
            print(f"FAILED:SYN-0033-probe1 {name}")
            if name == "planted_detected":
                print(f"  open_ids={planted.get('open_ids')}")
            if name == "intra_phase_excluded":
                print(f"  skipped={intra.get('intra_exclusive_skipped')}")
                print(f"  reported={intra.get('reported')}")
            return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:SYN-0033-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:SYN-0033-probe1 sentinel-absent")
        return 1
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:SYN-0033-probe1 self-declared", doc.get("state"))
        return 1
    ok, why = O.check_overclaim(doc)
    print(f"artifact_overclaim_ok={ok} {why}")
    if not ok:
        print("FAILED:SYN-0033-probe1 overclaim on live artifact")
        return 1
    payload = O.domain(doc)
    if "examined_pair_count" not in payload:
        print("FAILED:SYN-0033-probe1 live examined_pair_count absent")
        return 1
    print(
        "planted_open={0} intra_excluded={1} examined={2}".format(
            planted["open_ids"],
            intra["intra_phase_pairs_excluded"],
            planted["examined"],
        )
    )
    print("SUCCESS:SYN-0033-probe1 planted-cross-phase intra-phase-excluded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
