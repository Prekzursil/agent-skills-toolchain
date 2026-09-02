#!/usr/bin/env python3
"""Probe 1: execute the cheapest count-gaming attack against F01.

The attack MUST run; a designed-but-not-executed attack is NOT-CHECKED.
Reports the unique-count number. Reproduces _USER-PROMPTS.md:11339 first.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import attack  # noqa: E402

ART = REPO / (
    "command-center/design/council/"
    "CNL-0052-adversarial-attack-on-the-unique-idea-counter-count-gaming.md"
)


def main() -> int:
    live = attack.measure()
    cheapest = live["cheapest_attack"]
    naive = int(cheapest["naive_unique"])
    f01n = int(cheapest["f01_unique"])
    print(f"named_failure_reproduced={live['named_failure_reproduced']}")
    print(f"cheapest_id={cheapest['id']}")
    print(f"extra_tokens={cheapest['extra_tokens']}")
    print(f"naive_unique={naive}")
    print(f"jaccard_only_unique={cheapest['jaccard_only_unique']}")
    print(f"f01_unique={f01n}")
    print(f"f01_survives={cheapest['f01_survives']}")
    print(f"naive_gate_ge_100={cheapest['naive_gate_ge_100']}")
    print(f"f01_gate_ge_100={cheapest['f01_gate_ge_100']}")
    mixed = cheapest["mixed_seed_and_rewrite"]
    print(
        "mixed_jaccard_only="
        f"{mixed['jaccard_only_unique']} mixed_f01={mixed['f01_unique']}"
    )
    print(f"negative_control_verbatim={live['negative_control']['verbatim']}")

    if not live["named_failure_reproduced"] or naive < 100:
        print("FAILED:CNL-0052-probe1 named failure :11339 not reproduced")
        return 1
    if f01n >= 100 or cheapest["f01_gate_ge_100"]:
        print("FAILED:CNL-0052-probe1 F01 did not survive cheapest attack")
        return 1
    if not isinstance(f01n, int):
        print("FAILED:CNL-0052-probe1 F01 result is not a number")
        return 1
    bad = live["both_states"]["planted_bad"]
    good = live["both_states"]["known_good"]
    print(f"both_bad_fires_reject={bad['fires_reject']} f01_unique={bad['f01_unique']}")
    print(f"both_good_silent_accept={good['silent_accept']} f01_unique={good['f01_unique']}")
    if not bad["fires_reject"] or not good["silent_accept"]:
        print("FAILED:CNL-0052-probe1 both-states control")
        return 1
    if not mixed["jaccard_only_splits_rewrite"] or not mixed["f01_collapses_rewrite"]:
        print("FAILED:CNL-0052-probe1 mixed rewrite did not separate S1 from S2")
        return 1
    if not live["distinct_audit"]["below_threshold"]:
        print("FAILED:CNL-0052-probe1 distinct corpus self-merges")
        return 1

    if not ART.is_file():
        print("FAILED:CNL-0052-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:CNL-0052" not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNL-0052-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNL-0052-probe1 self-declared {doc.get('state')}")
        return 1
    art_n = int(doc["attack"]["f01_unique"])
    if art_n != f01n:
        print(f"FAILED:CNL-0052-probe1 artifact f01_unique {art_n} != live {f01n}")
        return 1
    if int(doc["attack"]["naive_unique"]) != naive:
        print("FAILED:CNL-0052-probe1 artifact naive_unique drift")
        return 1
    print(f"attack_result_number={f01n}")
    print("SUCCESS:CNL-0052-probe1 attack executed named-failure reproduced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
