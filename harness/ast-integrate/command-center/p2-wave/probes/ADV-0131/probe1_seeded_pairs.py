#!/usr/bin/env python3
"""Probe 1: planted numeric + existence contradictions in a scratch tree.

Both must be found with the planted file:line anchors. Also re-checks the
emitted artifact for schema, sentinel, and the known live instance.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402
from scenario import SEED_MISSING, SEED_SUBJECT, write_seeded  # noqa: E402

ART = D.REPO / D.OUTPUT_REL


def main() -> int:
    with TemporaryDirectory(prefix="adv-0131-probe1-") as td:
        root = Path(td)
        planted = write_seeded(root)
        pairs = D.mine(root, root)
        num = [
            p
            for p in pairs
            if p["subject_id"] == SEED_SUBJECT
            and p["exclusivity_reason"] == "numeric-mismatch"
        ]
        exi = [
            p
            for p in pairs
            if p["exclusivity_reason"] == "existence-versus-absence"
            and p.get("target_path") == SEED_MISSING
        ]
        want_num = {
            f"{D.rel_of(planted['numeric_a'], root)}:1",
            f"{D.rel_of(planted['numeric_b'], root)}:1",
        }
        want_exi = {
            f"{D.rel_of(planted['exists_listed'], root)}:1",
            f"{D.rel_of(planted['exists_absent'], root)}:1",
        }
        num_ok = bool(num) and want_num <= set(num[0]["verbatim_anchors"]) and sorted(num[0].get("values") or []) == [7, 12]
        exi_ok = bool(exi) and want_exi <= set(exi[0]["verbatim_anchors"]) and exi[0].get("stat_exists") is False
        payload = {
            "probe": "probe1-seeded-pairs",
            "unit_id": "ADV-0131",
            "numeric_found": num_ok,
            "existence_found": exi_ok,
            "numeric_anchors": num[0]["verbatim_anchors"] if num else [],
            "existence_anchors": exi[0]["verbatim_anchors"] if exi else [],
            "stat_exists": exi[0].get("stat_exists") if exi else None,
            "pair_count": len(pairs),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        if not num_ok:
            print("FAILED:ADV-0131-probe1 numeric contradiction not found with correct anchors")
            return 1
        if not exi_ok:
            print("FAILED:ADV-0131-probe1 existence contradiction not found with correct anchors")
            return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:ADV-0131-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    ok, why = D.validate_against_schema(doc)
    print(f"schema_ok={ok} {why}")
    if not ok:
        print("FAILED:ADV-0131-probe1 schema")
        return 1
    text = ART.read_text(encoding="utf-8")
    if D.SENTINEL not in text:
        print("FAILED:ADV-0131-probe1 sentinel-absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ADV-0131-probe1 self-declared {doc.get('state')}")
        return 1
    if "17-DECISION-LOG.md:175" not in text:
        print("FAILED:ADV-0131-probe1 known-live-anchor-absent")
        return 1
    body = D.payload_of(doc)
    if not body.get("known_live_instance", {}).get("found"):
        print("FAILED:ADV-0131-probe1 known-live-not-found")
        return 1

    print("SUCCESS:ADV-0131-probe1 seeded numeric+existence found; artifact holds known live instance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
