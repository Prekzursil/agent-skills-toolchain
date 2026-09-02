#!/usr/bin/env python3
"""Probe 1: build the directed support graph and enumerate every cycle.

Catalog verbatim: build the directed support graph and run cycle detection,
reporting every cycle with its member claims.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from graph import REPO, probe1_payload  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0081-circular-citation-cycle-detection.json"
CATALOG_SENTINEL = (
    "SUCCESS:ADV-0081 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0081 <reason>."
)


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0081-probe1 {msg}")
    return 1


def main() -> int:
    result = probe1_payload()
    print(json.dumps(result, sort_keys=True, default=str))
    print(
        "n_cycles={n} live={l} live_doc_claim={d} planted_doc_claim={p} "
        "planted_cycle={pc} planted_chain_acyclic={ca} representable={r}".format(
            n=result["n_simple_cycles"],
            l=result["n_live_simple_cycles"],
            d=result["n_live_document_claim_cycles"],
            p=result["n_planted_document_claim_cycles"],
            pc=result["controls"]["planted_unsupported_cycle_found"],
            ca=result["controls"]["planted_chain_acyclic"],
            r=result["graph_representable"],
        )
    )
    if not result["graph_representable"]:
        return fail("graph missing support, document-to-origin-claim, or external-root edges")
    if not result["controls"]["planted_unsupported_cycle_found"]:
        return fail("planted unsupported cycle not enumerated")
    if not result["controls"]["planted_chain_acyclic"]:
        return fail("planted acyclic chain was classified as a cycle")
    if result["n_planted_document_claim_cycles"] < 1:
        return fail("planted document-to-origin-claim cycle missing")
    if not result["pass"]:
        return fail("probe1 controls failed")

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        try:
            doc = json.loads(text)
        except json.JSONDecodeError as exc:
            return fail(f"artifact unparseable {exc}")
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            return fail(f"self-declared {doc.get('state')}")
        if CATALOG_SENTINEL not in text:
            return fail("catalog sentinel-absent")
        if doc.get("unit_id") != "ADV-0081":
            return fail(f"unit_id {doc.get('unit_id')}")
        live_doc = result["n_live_document_claim_cycles"]
        targets = {
            t.get("target_id"): t
            for t in (doc.get("targets") or [])
            if isinstance(t, dict)
        }
        cycle_t = targets.get("CYCLE-EXISTENCE") or {}
        if cycle_t.get("live_document_claim_cycles") != live_doc:
            return fail(
                f"artifact CYCLE-EXISTENCE live_document_claim_cycles "
                f"{cycle_t.get('live_document_claim_cycles')} != {live_doc}"
            )

    print(
        "SUCCESS:ADV-0081-probe1 directed support graph built; cycles enumerated "
        "with member claims; planted cycle vs chain classified"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
