#!/usr/bin/env python3
"""Probe 1: exclusion negative control, both-states, determinism, empty-diff."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from dispatcher import dispatch, recompute_attestation  # noqa: E402
from scenario import (  # noqa: E402
    CLAIM_CONCLUSION,
    RECEIPT_NEEDLE,
    SMUGGLE_NEEDLE,
    build_tree,
    inject_smuggled_receipt,
)

ART = REPO / "command-center/receipts/CNF-0130.json"


def _need(cond: bool, msg: str) -> None:
    if not cond:
        raise SystemExit(f"FAILED:CNF-0130-probe1 {msg}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="cnf0130-p1-") as tmp:
        root = build_tree(Path(tmp) / "tree")
        on = dispatch(root, exclusion_enabled=True)
        off = dispatch(root, exclusion_enabled=False)

        _need(RECEIPT_NEEDLE in off["payload"], "both-states: exclusion-off payload missing receipt")
        _need(CLAIM_CONCLUSION in off["payload"], "both-states: exclusion-off payload missing claim conclusion")
        _need(RECEIPT_NEEDLE not in on["payload"], "exclusion-on payload still has receipt needle")
        _need(CLAIM_CONCLUSION not in on["payload"], "exclusion-on payload still has claim conclusion")
        _need("def add" in on["payload"], "exclusion-on dropped raw source")
        _need("test_add_one_one" in on["payload"], "exclusion-on dropped tests")
        _need("src/mod.py:add returns the integer sum" in on["payload"], "statement missing")
        _need(on["attestation"] != off["attestation"], "attestation did not change with exclusion")
        _need(on["contamination_free"] is True, f"empty-diff hits={on['payload_vs_excluded_hits']}")
        _need(not on["payload_vs_excluded_hits"], "payload vs excluded artifacts not empty")
        _need(
            any("receipts" in e["path"] for e in on["excluded"]),
            "receipt path not in excluded list",
        )
        _need(
            any("reviews" in e["path"] for e in on["excluded"]),
            "review verdict not excluded",
        )
        _need(
            any("confirmation" in e["path"] for e in on["excluded"]),
            "prior confirmation not excluded",
        )
        _need("author" not in on["payload"] or "implementer-opus" not in on["payload"], "author identity leaked")
        _need("anthropic" not in on["payload"], "vendor identity leaked")

        recomputed = recompute_attestation(on["payload"], on["canonical_rules_json"])
        _need(recomputed == on["attestation"], "third-party recompute mismatch")

        again = dispatch(root, exclusion_enabled=True)
        _need(again["attestation"] == on["attestation"], "determinism: same claim hashed differently")
        _need(again["payload"] == on["payload"], "determinism: payload bytes drifted")

        inject_smuggled_receipt(root)
        on_inj = dispatch(root, exclusion_enabled=True)
        off_inj = dispatch(root, exclusion_enabled=False)
        _need(SMUGGLE_NEEDLE not in on_inj["payload"], "injected receipt was not dropped")
        _need(SMUGGLE_NEEDLE in off_inj["payload"], "both-states cannot see injected receipt")
        _need(
            on_inj["attestation"] != off_inj["attestation"],
            "injected-receipt attestation did not change vs exclusion-off",
        )
        _need(
            any("smuggled-receipt.json" in e["path"] for e in on_inj["excluded"]),
            "injected receipt missing from excluded list",
        )
        _need(on_inj["contamination_free"] is True, "injected tree payload still overlaps excluded")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        _need(doc.get("unit_id") == "CNF-0130", "receipt unit_id")
        _need("SUCCESS:CNF-0130" in json.dumps(doc), "receipt sentinel")
        att = (doc.get("blinding_attestation") or {}).get("attestation")
        if not isinstance(att, str):
            att = ((doc.get("extensions") or {}).get("blinding_attestation") or {}).get(
                "attestation"
            )
        _need(isinstance(att, str) and len(att) == 64, "receipt attestation missing")

    print(
        json.dumps(
            {
                "probe": "probe1-exclusion-both-states",
                "unit_id": "CNF-0130",
                "pass": True,
                "attestation_on": on["attestation"],
                "attestation_off": off["attestation"],
                "excluded": [e["path"] for e in on["excluded"]],
                "included": [i["path"] for i in on["included"]],
                "hits": on["payload_vs_excluded_hits"],
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNF-0130-probe1 exclusion both-states determinism empty-diff")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
