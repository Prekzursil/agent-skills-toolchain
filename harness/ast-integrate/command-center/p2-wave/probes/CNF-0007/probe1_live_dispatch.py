#!/usr/bin/env python3
"""Probe 1: live cross-vendor dispatch, severed-stream, prompt-by-file.

Re-runs the dispatcher. Does not rewrite the matrix artifact.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import dispatch as D  # noqa: E402
import matrix as M  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0007-crossvendor-matrix.json"
PROMPT = HERE / "fixtures" / "prompt-crossvendor.txt"
LIVE = HERE / "dispatches" / "CNF-0007-openai-parsed.json"
SEVERED = HERE / "dispatches" / "PLANT-P0-SEVERED-STREAM-receipt.json"


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNF-0007-probe1 matrix missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0007" or doc.get("state") in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:CNF-0007-probe1 state={doc.get('state')}")
        return 1

    live = D.run_confirmer(
        "openai", PROMPT, LIVE, mode="complete", claim_id="CNF-0007"
    )
    print(
        f"live classification={live['classification']} parsed={live['parsed']} "
        f"exit={live['exit_code']} bytes={live['output_bytes']} "
        f"counts={live['counts_as_result']}"
    )
    if not (
        live["counts_as_result"]
        and live["classification"] == "completed"
        and live["parsed"]
        and live["exit_code"] == 0
        and live["output_bytes"] > 0
    ):
        print(f"FAILED:CNF-0007-probe1 live dispatch {live}")
        return 1
    parsed = json.loads(LIVE.read_text(encoding="utf-8"))
    if parsed.get("confirmer_vendor") != "openai":
        print(f"FAILED:CNF-0007-probe1 confirmer vendor {parsed.get('confirmer_vendor')}")
        return 1
    if parsed.get("observed_vendor") != "anthropic":
        print(f"FAILED:CNF-0007-probe1 observed vendor {parsed.get('observed_vendor')}")
        return 1
    if parsed.get("source_probe") == parsed.get("verifier_probe"):
        print("FAILED:CNF-0007-probe1 source_probe equals verifier_probe")
        return 1
    if not parsed.get("source_probe") or not parsed.get("verifier_probe"):
        print("FAILED:CNF-0007-probe1 empty probe fingerprint")
        return 1

    severed = D.run_confirmer(
        "anthropic", PROMPT, SEVERED, mode="severed", claim_id="PLANT-P0-SEVERED-STREAM"
    )
    print(
        f"severed classification={severed['classification']} "
        f"counts={severed['counts_as_result']} parsed={severed['parsed']}"
    )
    if severed["classification"] != "severed-stream" or severed["counts_as_result"]:
        print(f"FAILED:CNF-0007-probe1 severed counted as result: {severed}")
        return 1
    if live["exit_code"] == 0 and severed["exit_code"] == 0:
        if live["counts_as_result"] == severed["counts_as_result"]:
            print("FAILED:CNF-0007-probe1 exit-0-only detector is inert")
            return 1

    inline = D.reject_inline("y" * 40000)
    print(
        f"inline classification={inline['classification']} "
        f"transport={inline.get('prompt_transport')}"
    )
    if inline["classification"] != "win-arg-limit" or inline["counts_as_result"]:
        print(f"FAILED:CNF-0007-probe1 inline not rejected: {inline}")
        return 1

    counted = [
        d
        for d in (M.payload(doc).get("dispatches") or [])
        if isinstance(d, dict) and d.get("counts_as_result") is True
    ]
    if not counted:
        print("FAILED:CNF-0007-probe1 artifact has no counted dispatch")
        return 1
    for row in counted:
        if row.get("prompt_transport") != "file":
            print(f"FAILED:CNF-0007-probe1 counted dispatch not file-prompt: {row}")
            return 1
        if not row.get("parsed") or int(row.get("output_bytes") or 0) <= 0:
            print(f"FAILED:CNF-0007-probe1 counted dispatch missing parsed file: {row}")
            return 1

    print("SUCCESS:CNF-0007-probe1 live dispatch severed-stream prompt-by-file")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
