#!/usr/bin/env python3
"""Probe 2: independent reader vs adapter fills (hallucinated-default detector).

Does not import adapter field extractors. Lists parameters each paper
specifies with independent_reader.CUES, then checks that every adapter
FILLED field the reader knows about is in that list. A planted fill the
reader cannot find must be caught. Every filled quote must occur in source.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import adapter  # noqa: E402
import independent_reader as IR  # noqa: E402
from fields import FIXTURES, REQUIRED_PARAMS  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0053-probe2 {msg}")
    return 1


def main() -> int:
    planted_caught = False
    compared = []
    for meta in FIXTURES:
        text = adapter.load_fixture(meta["rel"])
        tr = adapter.translate(
            text,
            paper_id=meta["paper_id"],
            rel=meta["rel"],
            family=str(meta.get("family") or ""),
        )
        listed = IR.list_specified(text)
        filled = tr["filled_fields"]
        hallu = IR.hallucinated_fills(filled, listed["specified"])
        if hallu:
            return fail(
                f"{meta['paper_id']} adapter filled {hallu} but reader "
                f"specified {listed['specified']}"
            )
        for name, rec in tr["fields"].items():
            if rec["status"] != "FILLED":
                continue
            quote = rec.get("quote")
            if not isinstance(quote, str) or quote not in text:
                return fail(f"{meta['paper_id']} unquoted fill {name}")
            if not rec.get("source_anchor"):
                return fail(f"{meta['paper_id']} {name} node missing source_anchor")
        compared.append(
            {
                "paper_id": meta["paper_id"],
                "verdict": tr["verdict"],
                "adapter_filled_required": [
                    p for p in REQUIRED_PARAMS if tr["fields"][p]["status"] == "FILLED"
                ],
                "reader_specified_required": listed["specified_required"],
                "hallucinated": hallu,
            }
        )

        if meta["paper_id"] == "underspecified":
            if listed["specified_required"]:
                return fail(
                    f"underspecified reader listed {listed['specified_required']}"
                )
            if any(tr["fields"][p]["status"] == "FILLED" for p in REQUIRED_PARAMS):
                return fail("underspecified adapter filled a required param")
            # Planted mutation: adapter claims a default the paper does not specify.
            fake_filled = list(filled) + ["participant_count"]
            planted = IR.hallucinated_fills(fake_filled, listed["specified"])
            if "participant_count" not in planted:
                return fail("planted participant_count fill was not caught")
            planted_caught = True

        if meta["paper_id"] == "partial-missing-scoring":
            if "scoring" in listed["specified_required"]:
                return fail("reader treated 'quality is assessed' as scoring")
            if "scoring" in [
                p for p in REQUIRED_PARAMS if tr["fields"][p]["status"] == "FILLED"
            ]:
                return fail("adapter filled unpinned scoring")

        if meta["expect_verdict"] == "TRANSLATED":
            for p in REQUIRED_PARAMS:
                if p not in listed["specified_required"]:
                    return fail(
                        f"{meta['paper_id']} reader missed specified required {p}"
                    )
                if tr["fields"][p]["status"] != "FILLED":
                    return fail(f"{meta['paper_id']} adapter missed required {p}")

    if not planted_caught:
        return fail("planted hallucination control did not run")

    # Nodes without source_anchor fail (WFA-0044 IR rule applied to this adapter).
    committee = next(c for c in compared if c["paper_id"] == "role-committee-specified")
    text = adapter.load_fixture(
        next(m["rel"] for m in FIXTURES if m["paper_id"] == "role-committee-specified")
    )
    ir = adapter.translate(
        text,
        paper_id="role-committee-specified",
        rel=next(
            m["rel"] for m in FIXTURES if m["paper_id"] == "role-committee-specified"
        ),
        family="role-committees",
    )["ir"]
    if ir is None:
        return fail("committee IR missing")
    if not ir["nodes"]:
        return fail("committee IR has no nodes")
    bare = [n["id"] for n in ir["nodes"] if not n.get("source_anchor")]
    if bare:
        return fail(f"IR nodes without source_anchor: {bare}")

    payload = {
        "compared": compared,
        "planted_hallucination_caught": planted_caught,
        "ir_nodes": len(ir["nodes"]),
        "pass": True,
        "probe": "probe2-independent-reader",
        "unit_id": "WFA-0053",
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:WFA-0053-probe2 independent reader; planted hallucinated default caught"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
