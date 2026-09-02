#!/usr/bin/env python3
"""Probe 1: payload-identity, leakage, both-states, dispatch discipline."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import corpus as C  # noqa: E402
import harness as H  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0156.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0156-probe1 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0156":
        print("FAILED:CNF-0156-probe1 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:CNF-0156" not in json.dumps(doc):
        print("FAILED:CNF-0156-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0156-probe1 self-declared", doc.get("state"))
        return 1

    info = C.write_corpus()
    raw = info["payload_bytes"]
    hashes = H.write_vendor_payloads(raw)
    if not (hashes["anthropic"] == hashes["openai"] == hashes["identical"] == info["payload_sha256"]):
        print("FAILED:CNF-0156-probe1 live payload hashes diverge", hashes)
        return 1
    recorded = doc.get("payload_identity") or {}
    if recorded.get("sha256") != info["payload_sha256"]:
        print(
            "FAILED:CNF-0156-probe1 receipt payload hash drift",
            recorded.get("sha256"),
            info["payload_sha256"],
        )
        return 1
    if recorded.get("match") is not True:
        print("FAILED:CNF-0156-probe1 payload_identity.match is not true")
        return 1
    leak = C.leakage_hits(raw)
    if leak:
        print("FAILED:CNF-0156-probe1 leakage", leak)
        return 1
    oracle_text = json.dumps(info["oracle"])
    if any(row["ground_truth"] in raw.decode("utf-8") for row in info["oracle"]):
        # labels are planted-true / planted-false; they must not appear in payload
        print("FAILED:CNF-0156-probe1 ground_truth strings present in payload")
        return 1
    _ = oracle_text

    oracle = {row["id"]: row["ground_truth"] for row in info["oracle"]}
    for vendor in H.VENDORS:
        classified = H.run_vendor(
            vendor,
            C.PAYLOAD_DIR / f"{vendor}.json",
            H.RUNS / f"{vendor}-probe1.json",
        )
        if classified["status"] != "OK":
            print("FAILED:CNF-0156-probe1 dispatch", vendor, classified)
            return 1
        if "--background" in classified["command"]:
            print("FAILED:CNF-0156-probe1 background in command")
            return 1
        matrix = H.confusion(classified["doc"]["verdicts"], oracle)
        if not matrix["both_states"]:
            print("FAILED:CNF-0156-probe1 both-states", vendor, matrix["counts"])
            return 1
        receipt_m = next(m for m in doc["confusion_matrices"] if m["vendor"] == vendor)
        if receipt_m["counts"] != matrix["counts"]:
            print("FAILED:CNF-0156-probe1 matrix drift", vendor, receipt_m["counts"], matrix["counts"])
            return 1
        print(
            f"vendor={vendor} tp={matrix['counts']['tp']} fp={matrix['counts']['fp']} "
            f"tn={matrix['counts']['tn']} fn={matrix['counts']['fn']} "
            f"false_pass={matrix['false_pass_rate']} false_alarm={matrix['false_alarm_rate']}"
        )

    faults = H.run_fault_injections()
    if faults["quota"]["status"] != "NOT-CHECKED" or faults["quota"]["converted_to_refuted"]:
        print("FAILED:CNF-0156-probe1 429 became a verdict", faults["quota"])
        return 1
    if faults["severed"]["status"] != "SEVERED" or faults["severed"]["produced_verdict"]:
        print("FAILED:CNF-0156-probe1 severed classified as verdict", faults["severed"])
        return 1

    summary = {
        "pass": True,
        "probe": "probe1-payload-identity",
        "unit_id": "CNF-0156",
        "payload_sha256": info["payload_sha256"],
        "leakage_hits": leak,
        "quota_status": faults["quota"]["status"],
        "severed_status": faults["severed"]["status"],
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:CNF-0156-probe1 payload-identity leakage both-states dispatch-discipline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
