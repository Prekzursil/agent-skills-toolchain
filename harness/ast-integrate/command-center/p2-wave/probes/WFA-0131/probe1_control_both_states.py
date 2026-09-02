#!/usr/bin/env python3
"""Probe 1: control FIRE on gamed variants, SILENT on honest baseline.

Live re-run of the campaign (engine.evaluate_control). Mechanically different
from probe 2, which does not call evaluate_control.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from campaign import run_campaign  # noqa: E402
from variants import GAMED_IDS, PRIMARY_GAMED_IDS  # noqa: E402

ART = REPO / "command-center/foundry/WFA-0131-benchmark-gaming-adversarial-control.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0131-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:WFA-0131" not in text:
        return fail("sentinel absent")

    camp = run_campaign(freeze_first=False)
    scores = camp["scores"]
    honest = scores["honest_baseline"]["control"]["verdict"]
    if honest != "SILENT":
        return fail(f"honest baseline control={honest} fires={scores['honest_baseline']['control']['fires']}")

    missing_primary = [
        name
        for name in PRIMARY_GAMED_IDS
        if scores[name]["control"]["verdict"] != "FIRE"
    ]
    if missing_primary:
        return fail(f"control silent on primary gamed {missing_primary}")

    missing_all = [
        name for name in GAMED_IDS if scores[name]["control"]["verdict"] != "FIRE"
    ]
    if missing_all:
        return fail(f"control silent on gamed {missing_all}")

    if scores["genuine_improvement"]["control"]["verdict"] != "SILENT":
        return fail(
            "control FIRED on genuine improvement "
            f"{scores['genuine_improvement']['control']['fires']}"
        )

    payload = {
        "probe": "probe1_control_both_states",
        "honest_verdict": honest,
        "primary_gamed_fire": list(PRIMARY_GAMED_IDS),
        "all_gamed_fire": list(GAMED_IDS),
        "genuine_verdict": scores["genuine_improvement"]["control"]["verdict"],
        "fires": {name: scores[name]["control"]["fires"] for name in GAMED_IDS},
        "registry_sha256": camp["registry_sha256_before_first_run"],
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "honest=SILENT gamed_fire="
        f"{len(GAMED_IDS)}/{len(GAMED_IDS)} genuine=SILENT"
    )
    print("SUCCESS:WFA-0131-probe1 control both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
