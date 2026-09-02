#!/usr/bin/env python3
"""Probe 1: cold-start zero-history must not be ranked as average."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import detector as D  # noqa: E402
import scenario as Sc  # noqa: E402

ART = (
    REPO
    / "command-center/design/council/CNL-0014-calibration-ranked-selection-needs-a-calibration-store-tha.md"
)
SENTINEL = "SUCCESS:CNL-0014"


def main() -> int:
    m = Sc.run_all()
    cold = m["cold"]
    mixed = m["mixed"]
    print(f"cold_ranked_count={cold['ranked_count']}")
    print(f"cold_unrankable_count={cold['unrankable_count']}")
    print(f"cold_switched_method={cold['switched_method']}")
    print(f"cold_zero_ids={cold['sets']['zero_history_ids']}")
    print(f"cold_ranked_ids={cold['sets']['ranked_ids']}")
    print(f"cold_overlap={cold['sets']['overlap']}")
    print(f"cold_disjoint={cold['sets']['disjoint']}")
    print(
        f"cold_impute source={cold['impute_source']} "
        f"ranked_count={cold['imputed_ranked_count']} overlap={cold['imputed_overlap']}"
    )
    print(f"mixed_ranked_ids={mixed['ranked_ids']}")
    print(f"mixed_unrankable_ids={sorted(mixed['unrankable_ids'])}")
    print(f"mixed_disjoint={mixed['sets']['disjoint']}")
    print(f"alice_brier={mixed['alice_brier']} bob_brier={mixed['bob_brier']}")
    print(f"cara_resolved_n={mixed['cara_resolved_n']} cara_rank_class={mixed['cara_rank_class']}")
    print(f"store_good_accepted={m['store_validation']['known_good_accepted']}")
    print(
        "store_invented_rejected="
        f"{m['store_validation']['planted_invented_rejected']} "
        f"errors={m['store_validation']['planted_invented_errors']}"
    )

    checks = [
        ("cold_not_average", Sc.cold_ok(m)),
        ("mixed_only_scored", Sc.mixed_ok(m)),
        ("store_gate", Sc.store_gate_ok(m)),
        ("cold_impute_would_rank_all_four", cold["imputed_ranked_count"] == 4),
        ("cold_impute_overlap_nonempty", len(cold["imputed_overlap"]) == 4),
        ("unscoreable_cara_unrankable", mixed["cara_resolved_n"] == 0),
    ]
    failed = False
    for name, ok in checks:
        print(f"{name}={ok}")
        if not ok:
            failed = True

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNL-0014-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNL-0014-probe1 self-declared {doc.get('state')}")
        return 1
    if SENTINEL not in text:
        print("FAILED:CNL-0014-probe1 sentinel-absent")
        return 1
    policy = str(doc.get("zero_history_policy") or "")
    if "UNRANKABLE" not in policy:
        print("FAILED:CNL-0014-probe1 zero_history_policy missing UNRANKABLE")
        return 1
    if "must NOT be ranked as average" not in policy:
        print("FAILED:CNL-0014-probe1 zero_history_policy does not refuse average-default")
        return 1
    rec_ranked = (doc.get("cold_start") or {}).get("ranked_count")
    if rec_ranked != 0:
        print(f"FAILED:CNL-0014-probe1 artifact cold ranked_count={rec_ranked}")
        return 1
    rec_mixed = (doc.get("mixed_history") or {}).get("ranked_ids")
    if rec_mixed != mixed["ranked_ids"]:
        print(f"FAILED:CNL-0014-probe1 artifact mixed ranked drift {rec_mixed}")
        return 1

    # Independent detector on the honest cold ranking must be silent.
    silent = not D.fires(F_store(), cold_honest_from(m))
    print(f"detector_silent_on_honest_cold={silent}")
    if not silent:
        print("FAILED:CNL-0014-probe1 detector fired on honest cold-start")
        return 1

    if failed:
        print("FAILED:CNL-0014-probe1 cold-start / mixed checks")
        return 1
    print("SUCCESS:CNL-0014-probe1 cold-start zero-history is UNRANKABLE not average")
    return 0


def F_store():
    import fixtures as F

    return F.cold_start_store()


def cold_honest_from(m: dict) -> dict:
    return {
        "method": "calibration-rank",
        "ranked": m["cold"]["ranked"],
        "unrankable": m["cold"]["unrankable"],
    }


if __name__ == "__main__":
    raise SystemExit(main())
