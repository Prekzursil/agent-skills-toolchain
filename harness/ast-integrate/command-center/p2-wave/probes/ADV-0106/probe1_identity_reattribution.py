#!/usr/bin/env python3
"""Probe 1: identity re-attribution from anonymised transcript vs chance."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:{E.UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    meas = E.measure()
    good = meas["stylometry_good"]
    bad = meas["stylometry_bad"]
    ident = meas["public_identity_scan"]

    if abs(good["chance"] - E.CHANCE) > 1e-12:
        return fail("chance baseline not 1/n_authors")
    if good["n"] != E.N_TEST * len(E.AUTHORS):
        return fail(f"good n={good['n']}")
    if not good["indistinguishable_from_chance"]:
        return fail(
            f"good-state accuracy {good['accuracy']} distinguishable from chance "
            f"{good['chance']} p_ge={good['p_ge_chance']}"
        )
    if bad["indistinguishable_from_chance"] or bad["accuracy"] <= E.CHANCE:
        return fail(
            f"leaky-state oracle stuck at chance accuracy={bad['accuracy']}"
        )
    if ident["identity_leaked"]:
        return fail(f"public transcript still names seats {ident['identity_hits']}")
    if meas["identity_verdict"] != "REFUTED":
        return fail(f"identity_verdict={meas['identity_verdict']}")

    art = E.REPO / E.OUT_REL
    if art.is_file():
        doc = json.loads(art.read_text(encoding="utf-8"))
        if E.SENTINEL not in art.read_text(encoding="utf-8"):
            return fail("catalog sentinel absent")
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            return fail(f"self-declared {doc.get('state')}")
        rec = (doc.get("measurements") or {}).get("stylometry_good") or {}
        if rec and abs(float(rec.get("accuracy", -1)) - good["accuracy"]) > 1e-12:
            return fail("artifact stylometry_good.accuracy drifted from live")

    payload = {
        "probe": "probe1-identity-reattribution",
        "unit_id": E.UNIT,
        "pass": True,
        "catalog_probe": E.CATALOG_PROBE1,
        "chance": good["chance"],
        "good_accuracy": good["accuracy"],
        "good_p_ge_chance": good["p_ge_chance"],
        "good_indistinguishable": True,
        "bad_accuracy": bad["accuracy"],
        "bad_indistinguishable": bad["indistinguishable_from_chance"],
        "public_identity_leaked": ident["identity_leaked"],
        "verdict": meas["identity_verdict"],
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"chance={good['chance']} good_acc={good['accuracy']} "
        f"bad_acc={bad['accuracy']} public_id_leak={ident['identity_leaked']}"
    )
    print(
        "SUCCESS:ADV-0106-probe1 identity re-attribution vs chance; "
        "good state indistinguishable; leaky idiolect distinguishable"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
