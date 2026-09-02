#!/usr/bin/env python3
"""Probe 1: fixture score + independent recomputation from stored components.

Evidence requirement (IMP-0094): TWO independent signals
  (1) the score for a fixture package
  (2) an independent recomputation from the stored component measurements
      alone, requiring exact equality
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.quality_score import (  # noqa: E402
    compute_score,
    default_fixture_path,
    load_measurements,
    score_from_components,
    validate_record,
)

RECEIPT = REPO / "command-center" / "receipts" / "IMP-0094.json"


def _hand_recompute(components_bp: dict, weights_bp: dict, scale: int) -> int:
    acc = 0
    for key, weight in weights_bp.items():
        acc += int(weight) * int(components_bp[key])
    return acc // int(scale)


def main() -> int:
    measurements = load_measurements(default_fixture_path())
    scored = compute_score(measurements)
    record = scored.to_record()
    schema_errors = validate_record(record, repo=REPO)

    live_rederive = score_from_components(record["components_bp"], record["weights_bp"])
    live_hand = _hand_recompute(record["components_bp"], record["weights_bp"], record["scale"])
    live_equal = live_rederive == record["score_bp"] == live_hand

    receipt_ok = None
    receipt_equal = None
    if RECEIPT.is_file() and RECEIPT.stat().st_size > 0:
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        published = receipt.get("quality_score") or {}
        receipt_ok = (
            str(receipt.get("state") or "").upper() not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
            and "SUCCESS:IMP-0094" in RECEIPT.read_text(encoding="utf-8")
            and isinstance(published, dict)
            and published.get("score_bp") is not None
        )
        if isinstance(published, dict) and published.get("components_bp"):
            red = _hand_recompute(
                published["components_bp"],
                published["weights_bp"],
                int(published.get("scale") or 10000),
            )
            receipt_equal = red == int(published["score_bp"])
            receipt_ok = bool(receipt_ok) and receipt_equal and not validate_record(published, repo=REPO)

    payload = {
        "probe": "probe1-rederive",
        "unit_id": "IMP-0094",
        "fixture": default_fixture_path().relative_to(REPO).as_posix(),
        "package_id": scored.package_id,
        "version": scored.version,
        "score_bp": scored.score_bp,
        "rederived_from_components_bp": live_rederive,
        "hand_recompute_from_components_bp": live_hand,
        "exact_equality": live_equal,
        "schema_errors": schema_errors,
        "components_bp": record["components_bp"],
        "weights_bp": record["weights_bp"],
        "worksheet": record["worksheet"],
        "receipt_present": RECEIPT.is_file(),
        "receipt_published_rederives": receipt_equal,
        "receipt_ok": receipt_ok,
        "pass": live_equal and not schema_errors and (receipt_ok is not False),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not live_equal:
        print("FAILED:IMP-0094-probe1 score not rederivable from components")
        return 1
    if schema_errors:
        print("FAILED:IMP-0094-probe1 schema", schema_errors[:3])
        return 1
    if receipt_ok is False:
        print("FAILED:IMP-0094-probe1 receipt published score does not rederive")
        return 1
    print(
        f"fixture_score_bp={scored.score_bp} rederived={live_rederive} "
        f"hand={live_hand} equal={live_equal}"
    )
    print("SUCCESS:IMP-0094-probe1 fixture score rederivable from published components")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
