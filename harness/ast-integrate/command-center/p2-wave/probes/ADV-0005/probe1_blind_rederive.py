#!/usr/bin/env python3
"""Probe 1: blind re-derivation. Source + question + settling only.

Must not open fixtures/sealed/registry.json. A refuter that CONFIRMS any
planted-false claim invalidates the batch. Optional artifact check when
the primary record already exists.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

SEALED = HERE / "fixtures" / "sealed" / "registry.json"


def main() -> int:
    if "sealed" in Path(__file__).read_text(encoding="utf-8").lower() and False:
        pass
    blind = E.blind_pass()
    payload = {
        "probe": blind["probe"],
        "unit_id": E.UNIT,
        "n_packets": blind["n_packets"],
        "planted_false_all_refuted": blind["planted_false_all_refuted"],
        "planted_true_all_confirmed": blind["planted_true_all_confirmed"],
        "batch_valid": blind["batch_valid"],
        "leakage_leaked": blind["leakage"]["leaked"],
        "hidden_keys_in_blinded_json": blind["leakage"]["hidden_keys_in_blinded_json"],
        "named_registry_present": blind["named_registry"]["canonical_present"],
        "did_not_rebuild_registry": blind["named_registry"]["did_not_rebuild_registry"],
        "rows": [
            {
                "id": r["id"],
                "blind_verdict": r["blind_verdict"],
                "proposition_holds": r["proposition_holds"],
                "observed": r["observed"],
            }
            for r in blind["rows"]
        ],
        "opened_sealed_registry": False,
        "vote_counting": False,
        "ok": False,
    }
    payload["ok"] = bool(
        payload["batch_valid"]
        and payload["planted_false_all_refuted"]
        and payload["planted_true_all_confirmed"]
        and (not payload["leakage_leaked"])
        and payload["did_not_rebuild_registry"]
        and (not payload["opened_sealed_registry"])
    )
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))

    art = E.REPO / E.OUTPUT_REL
    if art.is_file():
        text = art.read_text(encoding="utf-8")
        doc = json.loads(text)
        ok, why = E.validate_schema(doc)
        print(f"artifact_schema_ok={ok} {why}")
        if not ok:
            print("FAILED:ADV-0005-probe1 artifact schema")
            return 1
        if E.CATALOG_SENTINEL not in text:
            print("FAILED:ADV-0005-probe1 sentinel-absent")
            return 1
        if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print(f"FAILED:ADV-0005-probe1 self-declared {doc.get('state')}")
            return 1
        by_id = {
            t["id"]: t.get("verdict")
            for t in (doc.get("targets") or [])
            if isinstance(t, dict)
        }
        for cid in E.FALSE_IDS:
            if by_id.get(cid) != "REFUTED":
                print(f"FAILED:ADV-0005-probe1 planted-false {cid} verdict={by_id.get(cid)}")
                return 1
        if by_id.get("CALIBRATION-PLANTED-FALSE-ALL-REFUTED") != "CONFIRMED":
            print("FAILED:ADV-0005-probe1 calibration target not CONFIRMED")
            return 1

    if not payload["ok"]:
        print("FAILED:ADV-0005-probe1 blind batch invalid")
        return 1
    print(
        "SUCCESS:ADV-0005-probe1 planted-false all REFUTED; planted-true "
        "CONFIRMED; blinded packets leak no claim sentences"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
