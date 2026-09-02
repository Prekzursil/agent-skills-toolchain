#!/usr/bin/env python3
"""Probe 1: known-broken deletion/empty + circularity control.

Mechanically different from probe 2 (healthy + consumer-field). This probe
plants defects on a tempfile copy and requires the gate to go red, while a
circular verifier that trusts claimed_present stays green.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import circular_trap as T  # noqa: E402
import fixtures as F  # noqa: E402
import gate as G  # noqa: E402


def _fail(msg: str) -> int:
    print(f"FAILED:CNF-0192-probe1 {msg}")
    return 1


def main() -> int:
    src = (HERE / "gate.py").read_text(encoding="utf-8")
    if "unit_manifest" in src or "circular_trap" in src:
        return _fail("gate.py must not import the writer or the circular trap")
    if G.uses_trap_keys_for_verdict(src):
        return _fail("gate.py AST-reads claimed_present/present/exists as a verdict")

    with tempfile.TemporaryDirectory(prefix="cnf0192-del-") as td:
        root = Path(td)
        mpath = F.write_tree(root, delete="alpha")
        result = G.verify(mpath)
        circular_green = T.trust_manifest_claims(mpath)
        alpha = next(e for e in result["entries"] if e["id"] == "alpha")
        print(
            json.dumps(
                {
                    "case": "delete-alpha",
                    "bucket": result["bucket_terminal_state"],
                    "alpha": alpha["terminal_state"],
                    "missing": result["counts"]["missing"],
                    "circular_trap_still_green": circular_green,
                    "circularity_ok": result["circularity"]["ok"],
                },
                sort_keys=True,
            )
        )
        if alpha["terminal_state"] != "MISSING":
            return _fail(f"deleted artifact terminal_state={alpha['terminal_state']}")
        if result["counts"]["missing"] != 1:
            return _fail(f"missing count {result['counts']['missing']} != 1")
        if result["bucket_terminal_state"] == "SUCCESS":
            return _fail("bucket stayed SUCCESS after deletion")
        if not circular_green:
            return _fail("circular trap was not green; detector control is vacuous")
        if not result["circularity"]["ok"]:
            return _fail(f"circularity violations {result['circularity']['violations']}")
        for entry in result["entries"]:
            for ev in entry["evidence"]:
                if ev.get("source") in G.FORBIDDEN_EVIDENCE_SOURCES:
                    return _fail(f"forbidden evidence {ev}")
                if str(ev.get("path") or "").endswith("ARTIFACT-MANIFEST.json"):
                    if entry["path"] != ev.get("path"):
                        return _fail("entry cited the manifest as own evidence")

    with tempfile.TemporaryDirectory(prefix="cnf0192-empty-") as td:
        root = Path(td)
        mpath = F.write_tree(root, empty="beta")
        result = G.verify(mpath)
        beta = next(e for e in result["entries"] if e["id"] == "beta")
        print(
            json.dumps(
                {
                    "case": "empty-beta",
                    "bucket": result["bucket_terminal_state"],
                    "beta": beta["terminal_state"],
                    "empty": result["counts"]["empty"],
                },
                sort_keys=True,
            )
        )
        if beta["terminal_state"] != "EMPTY":
            return _fail(f"empty artifact terminal_state={beta['terminal_state']}")
        if result["counts"]["empty"] < 1:
            return _fail("empty count did not grow")
        if result["bucket_terminal_state"] == "SUCCESS":
            return _fail("bucket stayed SUCCESS on empty file")

    with tempfile.TemporaryDirectory(prefix="cnf0192-tiny-") as td:
        root = Path(td)
        mpath = F.write_tree(root, tiny="gamma")
        result = G.verify(mpath)
        gamma = next(e for e in result["entries"] if e["id"] == "gamma")
        print(
            json.dumps(
                {
                    "case": "tiny-gamma",
                    "gamma": gamma["terminal_state"],
                    "below_min_size": result["counts"]["below_min_size"],
                    "min_bytes": result["min_bytes"],
                },
                sort_keys=True,
            )
        )
        if gamma["terminal_state"] != "BELOW-MIN-SIZE":
            return _fail(f"1-byte artifact terminal_state={gamma['terminal_state']}")
        if result["min_bytes"] <= 1:
            return _fail("MIN_BYTES default is not exercised (would pass 1-byte)")

    print("SUCCESS:CNF-0192-probe1 known-broken deletion/empty/tiny and circularity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
