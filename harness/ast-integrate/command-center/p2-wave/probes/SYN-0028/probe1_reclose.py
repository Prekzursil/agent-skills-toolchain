#!/usr/bin/env python3
"""Probe 1: re-run the closer against disk; artifact must match live recompute.

Does not read probe 2's verdict.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import close as C  # noqa: E402

ART = REPO / C.OUTPUT_REL


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:SYN-0028-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    ok, why = C.validate_against_schema(doc)
    print(f"schema_ok={ok} {why}")
    if not ok:
        print("FAILED:SYN-0028-probe1 schema")
        return 1
    if C.SENTINEL not in text:
        print("FAILED:SYN-0028-probe1 sentinel-absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:SYN-0028-probe1 self-declared {doc.get('state')}")
        return 1

    live = C.close(REPO)
    livep = C.payload(live)
    art = C.payload(doc)
    counts = art.get("counts") or {}
    print(
        f"n={art.get('selected_set_size')} source={art.get('selected_set_source')} "
        f"impl={counts.get('implemented')} sup={counts.get('superseded')} "
        f"rej={counts.get('rejected_with_owner_reasoning')} "
        f"amb={counts.get('ambiguous_not_checked')} sum={counts.get('sum')}"
    )
    if not art.get("counts_sum_equals_selected"):
        print("FAILED:SYN-0028-probe1 counts_sum_equals_selected false")
        return 1
    if counts.get("sum") != counts.get("selected_set_size"):
        print("FAILED:SYN-0028-probe1 four-way sum != selected-set size")
        return 1
    if counts.get("silently_dropped", 0) != 0:
        print("FAILED:SYN-0028-probe1 silently_dropped non-zero")
        return 1
    if not art.get("no_bare_ambiguous_token_assigned_a_state"):
        print("FAILED:SYN-0028-probe1 bare token assigned a state")
        return 1
    if not art.get("states_mutually_exclusive_and_exhaustive"):
        print("FAILED:SYN-0028-probe1 states not exclusive/exhaustive")
        return 1

    art_fp = C.disposition_fingerprint(doc)
    live_fp = C.disposition_fingerprint(live)
    if art_fp != live_fp:
        print(f"FAILED:SYN-0028-probe1 disposition drift art={art_fp} live={live_fp}")
        return 1
    if livep.get("counts") != art.get("counts"):
        print(f"FAILED:SYN-0028-probe1 counts drift art={art.get('counts')} live={livep.get('counts')}")
        return 1
    if livep.get("selected_set_source") != art.get("selected_set_source"):
        print("FAILED:SYN-0028-probe1 selected_set_source drift")
        return 1
    if C.SENTINEL not in json.dumps(live):
        print("FAILED:SYN-0028-probe1 live recompute missing sentinel")
        return 1

    named = art.get("named_inputs") or []
    present = [n for n in named if n.get("present")]
    print(f"named_inputs present={len(present)}/{len(named)}")
    for req in (
        "07-OPTION-UNIVERSE.json",
        "command-center/OPTION-ID-RESOLUTION.json",
        "command-center/synthesis/SYN-0005.decision-trace.json",
    ):
        row = next((n for n in named if n.get("requested") == req), None)
        print(f"  {req} present={None if row is None else row.get('present')}")

    print("SUCCESS:SYN-0028-probe1 reclose schema counts exclusive no-bare")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
