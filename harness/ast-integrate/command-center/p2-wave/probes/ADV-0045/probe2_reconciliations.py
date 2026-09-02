#!/usr/bin/env python3
"""Named probe 2: execute reconciliations against chain/replay/verify.

Does not call the live close.append_event writer. Independent of probe 1.
If the adjudication artifact exists, checks impossibility + control results.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from reconcile import measure  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0045-append-only-vs-erasure-adjudication.json"
SENTINEL = "SUCCESS:ADV-0045"


def _catalog_sentinel() -> str:
    data = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == "ADV-0045":
            return str(unit.get("completion_sentinel") or SENTINEL)
    return SENTINEL


def _section(doc: dict, key: str) -> list:
    """Read a list from the receipt, the privacy-dataflow report, or extensions."""
    if isinstance(doc.get(key), list) and doc.get(key):
        return doc[key]
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    if isinstance(report.get(key), list) and report.get(key):
        return report[key]
    ext = doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {}
    if isinstance(ext.get(key), list) and ext.get(key):
        return ext[key]
    return []


def main() -> int:
    live = measure()
    print(json.dumps(live, sort_keys=True, ensure_ascii=True))
    if not live.get("pass"):
        print("FAILED:ADV-0045-probe2 reconciliation measurements did not pass")
        return 1
    tomb = live["tombstone"]
    shred = live["crypto_shred"]
    ext = live["externalisation"]
    mini = live["minimisation"]
    imp = live["impossibility"]
    if tomb["erasure_achieved"] or not tomb["pii_still_in_log_bytes"]:
        print("FAILED:ADV-0045-probe2 tombstone incorrectly credited as erasure")
        return 1
    if tomb["breaks_raw_replay_determinism"]:
        print("FAILED:ADV-0045-probe2 tombstone broke raw replay")
        return 1
    if not shred["decrypt_works_before_shred"] or shred["decrypt_works_after_shred"]:
        print("FAILED:ADV-0045-probe2 crypto-shred decrypt control failed")
        return 1
    if not shred["breaks_audit_of_plaintext"]:
        print("FAILED:ADV-0045-probe2 crypto-shred did not break plaintext audit")
        return 1
    if not ext["erasure_of_side_store"] or ext["pii_in_log_plaintext"]:
        print("FAILED:ADV-0045-probe2 externalisation measurement failed")
        return 1
    if mini["future_write_contains_pii"] or mini["erases_history"]:
        print("FAILED:ADV-0045-probe2 minimisation measurement failed")
        return 1
    if not imp["no_strategy_satisfies_A_and_B_and_C"]:
        print("FAILED:ADV-0045-probe2 impossibility not demonstrated")
        return 1
    if not (imp.get("residual_risk") and imp.get("owner_visible_impact")):
        print("FAILED:ADV-0045-probe2 impossibility missing residual/owner impact")
        return 1

    if ART.is_file() and ART.stat().st_size > 200:
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if SENTINEL not in text or _catalog_sentinel() not in text:
            print("FAILED:ADV-0045-probe2 sentinel missing from artifact")
            return 1
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            print("FAILED:ADV-0045-probe2 self-declared", doc.get("state"))
            return 1
        targets = {t.get("id"): t for t in _section(doc, "enumerated_targets") if isinstance(t, dict)}
        if (targets.get("T-IMPOSSIBILITY") or {}).get("verdict") != "CONFIRMED":
            print("FAILED:ADV-0045-probe2 T-IMPOSSIBILITY not CONFIRMED")
            return 1
        if (targets.get("T-TOMBSTONE-ERASURE") or {}).get("verdict") != "REFUTED":
            print("FAILED:ADV-0045-probe2 T-TOMBSTONE-ERASURE must be REFUTED as erasure")
            return 1
        negs = {c.get("id"): c for c in _section(doc, "negative_controls") if isinstance(c, dict)}
        if not negs:
            print("FAILED:ADV-0045-probe2 negative_controls missing")
            return 1
        if "impossibility" not in json.dumps(_section(doc, "named_probes")):
            print("FAILED:ADV-0045-probe2 named probe raw_output missing impossibility")
            return 1

    print(
        "tombstone_erasure=False shred_breaks_plaintext_audit=True "
        f"externalise_side_store={ext['erasure_of_side_store']} "
        f"impossible={imp['no_strategy_satisfies_A_and_B_and_C']}"
    )
    print("SUCCESS:ADV-0045-probe2 reconciliations executed; A∧B∧C impossible")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
