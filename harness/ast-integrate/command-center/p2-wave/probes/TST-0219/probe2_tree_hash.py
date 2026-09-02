#!/usr/bin/env python3
"""Probe 2: installed tree hash proving the public artifact was not used.

Catalog signal (b). Does not treat resolver message text as the pass
criterion — that is probe 1. This probe re-installs into fresh dirs and
hashes the dest trees plus payload-byte presence.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import resolver as R  # noqa: E402
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/TST-0219.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:TST-0219-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0219" not in text:
        print("FAILED:TST-0219-probe2 sentinel absent")
        return 1
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        print("FAILED:TST-0219-probe2 self-declared", doc.get("state"))
        return 1

    live = S.evaluate()
    priv = live["private_ok"]
    pub = live["public_offer"]
    unpin = live["unpinned_fail"]
    mutant = live["confused_mutant"]

    priv_tree = priv["live_tree_hash"]
    pub_tree = pub["live_tree_hash"]
    unpin_tree = unpin["live_tree_hash"]
    mutant_tree = mutant["live_tree_hash"]

    summary = {
        "probe": "probe2-tree-hash",
        "unit_id": "TST-0219",
        "private_sha256": live["private_sha256"],
        "public_sha256": live["public_sha256"],
        "empty_tree_hash": live["empty_tree_hash"],
        "private_tree_hash": priv_tree,
        "public_offer_tree_hash": pub_tree,
        "unpinned_tree_hash": unpin_tree,
        "mutant_tree_hash": mutant_tree,
        "private_bytes_in_private_tree": priv["private_bytes_present"],
        "public_bytes_in_private_tree": priv["public_bytes_present"],
        "public_bytes_in_public_offer_tree": pub["public_bytes_present"],
        "public_bytes_in_unpinned_tree": unpin["public_bytes_present"],
        "public_bytes_in_mutant_tree": mutant["public_bytes_present"],
        "mutant_origin_used": mutant["origin_used"],
        "pass": False,
    }
    fails = []
    if live["private_sha256"] == live["public_sha256"]:
        fails.append("payloads are not distinct")
    if not priv["private_bytes_present"]:
        fails.append("private tree missing private payload hash")
    if priv["public_bytes_present"]:
        fails.append("private tree contains public payload hash")
    if priv_tree == live["empty_tree_hash"]:
        fails.append("private tree is empty")
    if live["private_sha256"] not in priv["live_census"].values():
        fails.append("census does not contain private artifact sha256")
    if live["public_sha256"] in priv["live_census"].values():
        fails.append("census contains public artifact sha256 after private install")

    if pub["public_bytes_present"] or pub["wrote_any"]:
        fails.append("public-offer dest contains public bytes")
    if pub_tree != live["empty_tree_hash"]:
        fails.append("public-offer dest tree hash is not the empty tree")
    if live["public_sha256"] in pub["live_census"].values():
        fails.append("public-offer census contains public sha256")

    if unpin["wrote_any"] or unpin["public_bytes_present"]:
        fails.append("unpinned dest was written")
    if unpin_tree != live["empty_tree_hash"]:
        fails.append("unpinned dest tree is not empty")

    if not mutant["public_bytes_present"]:
        fails.append("confused mutant did not install public bytes (detector vacuous)")
    if mutant["origin_used"] != R.PUBLIC_ORIGIN:
        fails.append("confused mutant did not select public origin")
    if mutant_tree == priv_tree:
        fails.append("mutant tree hash equals private tree hash")
    if live["public_sha256"] not in mutant["live_census"].values():
        fails.append("mutant census missing public sha256")

    summary["pass"] = not fails
    print(json.dumps(summary, sort_keys=True))
    if fails:
        print("FAILED:TST-0219-probe2 " + "; ".join(fails))
        return 1
    print(
        f"tree private={priv_tree[:16]} public_offer={pub_tree[:16]} "
        f"mutant={mutant_tree[:16]} public_bytes_absent_from_sut=True"
    )
    print("SUCCESS:TST-0219-probe2 installed tree hash excludes public artifact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
