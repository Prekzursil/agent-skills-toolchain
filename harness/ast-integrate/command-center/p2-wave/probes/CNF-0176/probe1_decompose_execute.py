#!/usr/bin/env python3
"""Probe 1: decompose, execute recovered components, capability set, round-trip.

Mechanically independent of probe 2 (license strip). Re-runs the engine live and
compares fingerprints and per-component execute records to the confirmation artifact.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0176.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0176-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0176":
        return fail(f"unit_id {doc.get('unit_id')}")
    text = json.dumps(doc)
    if "SUCCESS:CNF-0176" not in text:
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")
    live = S.run_confirmation()
    if not live.get("pass"):
        return fail("live confirmation did not pass")
    if not live.get("roundtrip_ok"):
        return fail("round-trip fingerprint mismatch")
    if live.get("capability_losses"):
        return fail(f"capability loss {live.get('capability_losses')}")
    planted = live.get("planted_lossy") or {}
    if not planted.get("detector_fired"):
        return fail("lossy fusion did not name rank")
    vanity = live.get("vanity_gate") or {}
    if vanity.get("accepted") is not False:
        return fail("11170 vanity fusion was accepted")
    parse_only = live.get("parse_only_control") or {}
    if parse_only.get("executed") is not False:
        return fail("parse-only counted as executed")
    comps = live.get("per_component") or []
    if len(comps) != 2:
        return fail(f"expected 2 recovered components got {len(comps)}")
    for row in comps:
        if not row.get("executed") or not row.get("tokens_equal"):
            return fail(f"component {row.get('source_id')} did not execute to original output")
        if str(row.get("terminal_state") or "") != "ok":
            return fail(f"component {row.get('source_id')} not terminal ok")

    rec_fp = str((doc.get("rollback_repro") or {}).get("fusion_fingerprint") or "")
    if rec_fp != live["fusion_fingerprint"]:
        return fail("artifact fusion fingerprint != live")
    rec_round = (doc.get("rollback_repro") or {}).get("roundtrip_ok")
    if rec_round is not True:
        return fail("artifact roundtrip_ok is not true")
    rec_comps = {
        r.get("source_id"): r for r in (doc.get("per_component") or []) if isinstance(r, dict)
    }
    for row in comps:
        got = rec_comps.get(row["source_id"])
        if not got:
            return fail(f"artifact missing component {row['source_id']}")
        if got.get("executed") is not True:
            return fail(f"artifact executed flag false for {row['source_id']}")
        if list(got.get("tokens") or []) != list(row.get("tokens") or []):
            return fail(f"artifact tokens drift for {row['source_id']}")
        if got.get("license_present") is not True or got.get("credit_present") is not True:
            return fail(f"artifact license/credit missing for {row['source_id']}")

    src_probe = doc.get("source_probe") or {}
    ver_probe = doc.get("verifier_probe") or {}
    if not src_probe or not ver_probe:
        return fail("empty source_probe or verifier_probe with CONFIRMED")
    if json.dumps(src_probe, sort_keys=True) == json.dumps(ver_probe, sort_keys=True):
        return fail("source_probe identical to verifier_probe")

    out = {
        "probe": "probe1-decompose-execute",
        "unit_id": "CNF-0176",
        "roundtrip_ok": True,
        "components": len(comps),
        "all_executed": True,
        "capability_losses": [],
        "planted_loss_fired": True,
        "vanity_refused": True,
        "parse_only_executed": False,
        "fusion_fingerprint": live["fusion_fingerprint"],
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    for row in comps:
        print(
            f"component {row['source_id']} executed={row['executed']} "
            f"terminal={row['terminal_state']} tokens_equal={row['tokens_equal']} "
            f"license={row['license_present']} credit={row['credit_present']}"
        )
    print("SUCCESS:CNF-0176-probe1 decompose execute capability round-trip")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
