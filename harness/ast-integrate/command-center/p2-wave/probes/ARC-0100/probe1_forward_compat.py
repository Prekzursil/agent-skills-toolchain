#!/usr/bin/env python3
"""Probe 1: forward-compat unknown-field outcome matches declared policy."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import contracts as C  # noqa: E402
import suite as S  # noqa: E402

ART = REPO / "command-center/phase4/conformance/ARC-0100.json"


def main() -> int:
    report = S.run_all()
    failed = []
    for row in report["contracts"]:
        uid = row["contract_id"]
        fc = row["forward_compat"]
        clean = row["clean_stable"]
        taut = row["anti_tautology"]
        print(
            f"{uid} policy={row['policy']} source={row['schema_source']} "
            f"forward={fc['ok']} clean={clean['ok']} taut={taut['ok']} "
            f"future_reason={fc['declared']['reason']}"
        )
        if not fc["ok"]:
            failed.append(f"{uid}:forward-compat")
        if not clean["ok"]:
            failed.append(f"{uid}:clean-stable")
        if not taut["ok"]:
            failed.append(f"{uid}:anti-tautology")
        if fc["declared"]["extras"] != [C.FUTURE_FIELD]:
            failed.append(f"{uid}:future-field-not-the-extra")

    live = report["live_catalog_arc0083"]
    print(
        f"live_catalog sample={live['sample_id']} accepted={live['accepted']} "
        f"kind={live['reason_kind']} extras={live['unknown_keys']} "
        f"missing={live['missing_required']}"
    )
    if live["accepted"] is True:
        failed.append("live-catalog-REJECT-should-fire")
    if "question_or_target" not in live["unknown_keys"]:
        failed.append("live-catalog-missing-question_or_target-extra")
    if "target" not in live["missing_required"]:
        failed.append("live-catalog-target-not-missing")

    if not ART.is_file():
        print("FAILED:ARC-0100-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0100-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:ARC-0100" not in text:
        print("FAILED:ARC-0100-probe1 sentinel absent")
        return 1
    art_rows = {
        r.get("contract_id"): r
        for r in S.contracts_from_artifact(doc)
        if r.get("contract_id")
    }
    for uid in C.CONTRACT_IDS:
        if uid not in art_rows:
            failed.append(f"{uid}:artifact-row-absent")
            continue
        if art_rows[uid].get("policy") != C.POLICIES[uid]["policy"]:
            failed.append(f"{uid}:artifact-policy-drift")
        if not art_rows[uid].get("producer") or not art_rows[uid].get("consumer"):
            failed.append(f"{uid}:artifact-pair-unnamed")
        if art_rows[uid].get("justification") == "UNJUSTIFIED":
            failed.append(f"{uid}:unjustified")

    if failed:
        print("FAILED:ARC-0100-probe1 " + ",".join(failed))
        return 1
    print("SUCCESS:ARC-0100-probe1 forward-compat anti-tautology live-catalog")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
