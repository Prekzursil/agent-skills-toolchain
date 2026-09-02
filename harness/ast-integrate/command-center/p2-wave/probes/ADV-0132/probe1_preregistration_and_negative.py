#!/usr/bin/env python3
"""Probe 1: re-run blind observers; require pre-registration order and negative controls.

Does not trust artifact timestamps without re-reading the prediction file and
re-executing observers. Does not re-score the headline (that is probe 2).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import blind as B  # noqa: E402
import questions as Q  # noqa: E402
import study as S  # noqa: E402

ART = REPO / S.OUT_REL
SCHEMA = REPO / S.SCHEMA_REL
PRED = HERE / "fixtures" / "predictions.json"


def parse_ts(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0132-probe1 {msg}")
    return 1


def main() -> int:
    src = (HERE / "blind.py").read_text(encoding="utf-8")
    if "sealed_answers" in src:
        return fail("blind.py mentions sealed_answers")
    if "consensus_prior" in src:
        return fail("blind.py mentions consensus_prior")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-absent")
    text = ART.read_text(encoding="utf-8")
    if Q.CATALOG_SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared:{doc.get('state')}")
    if doc.get("unit_id") != "ADV-0132":
        return fail("unit_id")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errs = sorted(
        jsonschema.Draft7Validator(schema).iter_errors(doc),
        key=lambda e: list(e.path),
    )
    if errs:
        return fail(f"schema {errs[0].message}")

    if not PRED.is_file():
        return fail("predictions-absent")
    pred = json.loads(PRED.read_text(encoding="utf-8"))
    pred_by_id = {r["id"]: r for r in pred["predictions"]}

    live_rows = []
    for q in Q.QUESTIONS:
        observed = B.observe(REPO, q["id"])
        rec = next(c for c in doc["conclusions"] if c["id"] == q["id"])
        if rec["executed_result"] != observed:
            return fail(f"observer-drift {q['id']} art={rec['executed_result']} live={observed}")
        p_ts = pred_by_id[q["id"]]["prediction_timestamp"]
        if rec["prediction_timestamp"] != p_ts:
            return fail(f"prediction-ts-drift {q['id']}")
        if parse_ts(p_ts) >= parse_ts(rec["executed_timestamp"]):
            return fail(f"prediction-not-before-run {q['id']}")
        live_rows.append((q["id"], rec["verdict"], observed))
        print(f"{q['id']} verdict={rec['verdict']} observed={observed}")

    hc = [c for c in doc["conclusions"] if c["stratum"] == "HIGH-CONFIDENCE-AGREED-UNTESTED"]
    nc = [c for c in doc["conclusions"] if c["stratum"] == "NEGATIVE-CONTROL-HAS-TEST"]
    if len(hc) < 3:
        return fail(f"high-confidence-n {len(hc)}")
    if len(nc) < 2:
        return fail(f"negative-control-n {len(nc)}")
    if not doc["negative_control"]["agrees_with_preexisting_tests"]:
        return fail("negative-control-flag")
    if any(c["verdict"] != "AGREEMENT-HELD" for c in nc):
        return fail("negative-control-not-held")

    existing = S.preexisting_tests()
    if len(existing) < 2 or any(not r["passed"] for r in existing):
        return fail(f"preexisting-tests {existing}")
    print(
        "preexisting "
        + ", ".join(f"{r['id']}=PASS" for r in existing)
    )
    print("SUCCESS:ADV-0132-probe1 pre-registration precedes run; negative controls agree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
