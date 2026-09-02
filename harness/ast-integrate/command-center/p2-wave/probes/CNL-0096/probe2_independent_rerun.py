#!/usr/bin/env python3
"""Probe 2: independent both-states rerun, negative control, schema, overclaim.

Reviewer does not trust the author's adjectives: FPR must be a number, the
negative-control rewrite must fire, and Draft-07 validation must pass.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import both_states as BS  # noqa: E402
import schema_local as SL  # noqa: E402
from detector import detect  # noqa: E402
from fixtures import PAIR_EXHAUSTED, load  # noqa: E402

ART = REPO / "command-center/design/council/CNL-0096-endless-debate-cap-and-graceful-degradation.md"
SCHEMA_REL = "command-center/schema/council-detector-spec.schema.json"
SCHEMA = REPO / SCHEMA_REL


def check_overclaim(doc: dict) -> tuple[bool, str]:
    payload = BS.artifact_payload(doc)
    fpr = payload.get("false_positive_rate")
    if not isinstance(fpr, dict):
        return False, "fpr-missing"
    rate = fpr.get("rate")
    if isinstance(rate, bool) or not isinstance(rate, (int, float)):
        return False, "fpr-not-number"
    if isinstance(rate, str):
        return False, "fpr-adjective"
    gd = payload.get("graceful_degradation") or {}
    if gd.get("emitted_kind") != "exhausted_without_decision":
        return False, "emitted-kind-missing"
    if gd.get("not_the_same_as") != "no-decision":
        return False, "not-distinguished-from-no-decision"
    if "SUCCESS:CNL-0096" not in json.dumps(doc):
        return False, "sentinel-absent"
    return True, f"rate={rate}"


def main() -> int:
    live = BS.run_matrix()
    print(f"independent_ok={live['ok']}")
    print(f"independent_planted_fired={live['planted_bad_fired']}")
    print(f"independent_clean_silent={live['known_good_silent']}")
    print(f"independent_pair_distinct={live['distinguisher_pair']['distinct']}")
    if not live["ok"]:
        print("FAILED:CNL-0096-probe2 independent matrix failed")
        return 1

    src = load(PAIR_EXHAUSTED)
    mutant = copy.deepcopy(src)
    mutant["outcome"]["kind"] = "no-decision"
    mutant["outcome"]["termination_cause"] = "deliberative"
    nc = detect(mutant)
    print(f"negative_control_fired={nc['fired']} codes={nc['codes']}")
    print(live["negative_control"]["verbatim"])
    if not nc["fired"]:
        print("FAILED:CNL-0096-probe2 negative control did not fire")
        return 1

    if not ART.is_file() or not SCHEMA.is_file():
        print("FAILED:CNL-0096-probe2 artifact or schema missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    schema_errors = SL.iter_errors(doc)
    if schema_errors:
        print("FAILED:CNL-0096-probe2 schema-invalid")
        for err in schema_errors[:12]:
            print(" ", err)
        return 1
    try:
        SL.assert_rejects_garbage()
    except ValueError as exc:
        print(f"FAILED:CNL-0096-probe2 {exc}")
        return 1
    print("schema_ok=True")

    ok, why = check_overclaim(doc)
    print(f"overclaim_ok={ok} {why}")
    if not ok:
        print("FAILED:CNL-0096-probe2 overclaim")
        return 1

    stripped = copy.deepcopy(doc)
    target = None
    if isinstance(stripped.get("report"), dict) and isinstance(
        (stripped["report"].get("false_positive_rate") or {}), dict
    ):
        target = stripped["report"]["false_positive_rate"]
    elif isinstance(stripped.get("extensions"), dict) and isinstance(
        (stripped["extensions"].get("false_positive_rate") or {}), dict
    ):
        target = stripped["extensions"]["false_positive_rate"]
    elif isinstance(stripped.get("false_positive_rate"), dict):
        target = stripped["false_positive_rate"]
    else:
        print("FAILED:CNL-0096-probe2 no FPR field to mutate")
        return 1
    target["rate"] = "low"
    mok, mwhy = check_overclaim(stripped)
    print(f"mutant_ok={mok} {mwhy}")
    if mok:
        print("FAILED:CNL-0096-probe2 adjective FPR was accepted")
        return 1

    payload = BS.artifact_payload(doc)
    art_pair = (payload.get("distinguisher_pair") or {}).get("distinct")
    if art_pair is not True:
        print("FAILED:CNL-0096-probe2 artifact distinguisher_pair.distinct")
        return 1
    if float((payload.get("false_positive_rate") or {}).get("rate")) != float(
        live["false_positive_rate"]["rate"]
    ):
        print("FAILED:CNL-0096-probe2 FPR drift vs independent rerun")
        return 1

    print("SUCCESS:CNL-0096-probe2 independent-rerun negative-control schema")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
