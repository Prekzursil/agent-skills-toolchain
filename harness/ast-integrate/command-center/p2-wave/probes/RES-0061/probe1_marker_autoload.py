#!/usr/bin/env python3
"""Probe 1: per-client auto-load of a benign marker, plus artifact sentinel."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import surface as S  # noqa: E402

ART = REPO / "command-center/research/RES-0061.json"
SENTINEL = (
    "SUCCESS:RES-0061 in the receipt AND a per-client auto-load observation "
    "using a benign marker plus a clean-tree control read"
)


def main() -> int:
    exp = S.run_experiment()
    print(
        "planted_ingest="
        f"{exp['all_clients_ingested_on_planted']} "
        "clean_silent="
        f"{exp['no_client_ingested_on_clean']} "
        "signals_agree="
        f"{exp['signals_agree']} "
        "decoy_planted="
        f"{exp['decoy_in_instruction_buffer_planted']}"
    )
    for row in exp["planted_clients"]:
        print(
            f"client[{row['client_id']}] ingested={row['ingested_marker']} "
            f"s1={row['s1']['present']} s2={row['s2']['present']} "
            f"live={row['live'].get('status')}"
        )
    if not exp["all_clients_ingested_on_planted"]:
        print("FAILED:RES-0061-probe1 a client missed the planted marker")
        return 1
    if not exp["no_client_ingested_on_clean"]:
        print("FAILED:RES-0061-probe1 clean tree produced a marker ingest")
        return 1
    if not exp["signals_agree"]:
        print("FAILED:RES-0061-probe1 S1/S2 disagreement")
        return 1
    if exp["decoy_in_instruction_buffer_planted"] or exp["decoy_in_instruction_buffer_clean"]:
        print("FAILED:RES-0061-probe1 decoy leaked into an instruction buffer")
        return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:RES-0061-probe1 research artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:RES-0061-probe1 self-declared {doc.get('state')}")
        return 1
    if SENTINEL not in text or "SUCCESS:RES-0061" not in text:
        print("FAILED:RES-0061-probe1 sentinel absent")
        return 1
    print("SUCCESS:RES-0061-probe1 per-client marker auto-load plus clean control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
