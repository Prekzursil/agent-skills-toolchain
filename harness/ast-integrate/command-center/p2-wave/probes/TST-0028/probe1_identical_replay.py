#!/usr/bin/env python3
"""Probe 1: identical materialised builds replay with an empty semantic diff.

Source measurement. Re-runs record/replay in two isolated copies of subject/
and fails if the artifact set or decision trace moves. Distinct fingerprint
from probe 2 (does not plant a behaviour change).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

ART = REPO / "command-center/receipts/TST-0028.json"
SENTINEL = "SUCCESS:TST-0028"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0028-probe1 {msg}")
    return 1


def main() -> int:
    exp = H.run_experiment()
    ident = exp["identical_replay"]
    stats = exp["replayability"]
    offline = stats["replayable_without_live_network_or_credentials"]
    out = {
        "probe": "probe1-identical-replay",
        "unit_id": "TST-0028",
        "identical_empty": ident["empty"],
        "artifact_empty": ident["artifact_set"]["empty"],
        "trace_empty": ident["decision_trace"]["empty"],
        "side_by_side": exp["materialised_builds"]["side_by_side"],
        "step_count": exp["recorded"]["step_count"],
        "replayable_without_live_network_or_credentials_percent": offline["percent"],
        "replayable_count": offline["count"],
        "reasons_present": stats["reasons_present"],
        "pass": bool(
            ident["empty"]
            and ident["artifact_set"]["empty"]
            and ident["decision_trace"]["empty"]
            and exp["materialised_builds"]["side_by_side"]
            and offline["count"] >= 1
            and set(stats["reasons_present"]) >= {"network", "credential", "clock", "GUI"}
        ),
    }
    print(json.dumps(out, sort_keys=True))
    if not out["pass"]:
        return fail("identical replay was not empty or replayability incomplete")
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    rec_ident = ((doc.get("tests_live") or {}).get("identical_replay")) or {}
    if rec_ident.get("empty") is not True:
        return fail("receipt identical_replay.empty is not true")
    rec_pct = (
        (doc.get("replayability") or {})
        .get("replayable_without_live_network_or_credentials") or {}
    ).get("percent")
    if rec_pct != offline["percent"]:
        return fail(f"receipt percent drift live={offline['percent']} receipt={rec_pct}")
    rec_steps = (doc.get("recorded") or {}).get("step_count")
    if rec_steps != exp["recorded"]["step_count"]:
        return fail(f"receipt step_count drift live={exp['recorded']['step_count']} receipt={rec_steps}")
    print(
        f"identical_empty=True percent={offline['percent']} "
        f"steps={exp['recorded']['step_count']} side_by_side=True"
    )
    print("SUCCESS:TST-0028-probe1 identical build empty diff")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
