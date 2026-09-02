#!/usr/bin/env python3
"""Probe 2: independent unique-token gain vs evaluator stop bit."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from simulate import info_gain_step, run_all  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0101-stopping-rule-both-directions.json"
UNIT = "ADV-0101"


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0101-probe2 {msg}")
    return 1


def recompute_gain_from_transcripts(run: dict) -> int:
    prior: set[str] = set()
    after_r1 = 0
    for rec in run["rounds"]:
        gain = info_gain_step(rec["utterances"], prior)
        prior |= gain["tokens"]
        if rec["round"] > 1:
            after_r1 += gain["new_unique_count"]
    return after_r1


def main() -> int:
    bundle = run_all()
    if not bundle["info_gain_divergences"]:
        return fail("no-divergence")

    recomputed = []
    for row in bundle["expression_runs"]:
        end = row["councils"]["endless_low_info"]
        healthy = row["councils"]["healthy_progress"]
        end_gain = recompute_gain_from_transcripts(end)
        healthy_gain = recompute_gain_from_transcripts(healthy)
        print(
            f"{row['expression']['id']} endless_gain={end_gain} "
            f"recorded={end['info_gain_after_round1_total']} "
            f"stop={end['stop_reason']} at={end['stopped_at']}"
        )
        if end_gain != end["info_gain_after_round1_total"]:
            return fail(f"gain-mismatch-{row['expression']['id']}")
        recomputed.append(
            {
                "id": row["expression"]["id"],
                "endless_gain": end_gain,
                "healthy_gain": healthy_gain,
                "endless_stop": end["stop_reason"],
            }
        )
        if end_gain > 0:
            return fail(f"endless-gain-not-zero-{row['expression']['id']}")

    if all(r["healthy_gain"] <= 0 for r in recomputed):
        return fail("healthy-gain-zero")

    e2_end = next(
        r for r in bundle["expression_runs"] if r["expression"]["id"] == "E2"
    )["councils"]["endless_low_info"]
    print(
        f"E2 divergence_stop={e2_end['divergence_zero_gain_but_evaluator_stop']} "
        f"gain={e2_end['info_gain_after_round1_total']} stop_at={e2_end['stopped_at']}"
    )
    if not e2_end["divergence_zero_gain_but_evaluator_stop"]:
        return fail("e2-should-stop-with-zero-gain")

    e1_end = next(
        r for r in bundle["expression_runs"] if r["expression"]["id"] == "E1"
    )["councils"]["endless_low_info"]
    if not e1_end["divergence_zero_gain_evaluator_never_stops"]:
        return fail("e1-should-never-stop-with-zero-gain")

    if not ART.is_file():
        return fail("artifact-missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    if "SUCCESS:ADV-0101" not in text:
        return fail("sentinel-absent")
    recorded = doc.get("evidence", {}).get("info_gain_divergences") or []
    live_ids = {d["expression_id"] for d in bundle["info_gain_divergences"]}
    rec_ids = {d["expression_id"] for d in recorded}
    if live_ids != rec_ids:
        return fail(f"artifact-divergence-drift live={sorted(live_ids)} rec={sorted(rec_ids)}")

    for row in bundle["expression_runs"]:
        end = row["councils"]["endless_low_info"]
        consensus = end["final_bindings"]["consensus"]
        if end["info_gain_after_round1_total"] == 0 and consensus >= 0.95:
            print(
                f"independent-split {row['expression']['id']}: "
                f"consensus={consensus} but unique-token-gain=0"
            )

    payload = {
        "pass": True,
        "probe": "probe2-info-gain",
        "divergences": bundle["info_gain_divergences"],
        "recomputed": recomputed,
        "unit_id": UNIT,
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:ADV-0101-probe2 independent information-gain")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
