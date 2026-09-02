"""Live IMP-0343 scenarios against tools/council/antifail/independence.py."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.antifail.independence import (  # noqa: E402
    CEILING,
    audit_independence,
    identical_ceiling,
    load_council,
    shared_phrase_census,
)

FIX = HERE / "fixtures"
BLIND = FIX / "council-blind-independent.json"
NONBLIND = FIX / "council-nonblind-leak.json"
THEATRE = FIX / "council-theatre-blind.json"
IDENTICAL = FIX / "identical-brief.txt"


def _compact_sep(sep: dict) -> dict:
    return {
        "separated": sep["separated"],
        "gap": sep["gap"],
        "gap_ok": sep["gap_ok"],
        "iqr_separated": sep["iqr_separated"],
        "blind_mean": sep["blind_mean"],
        "nonblind_mean": sep["nonblind_mean"],
        "blind_p75": sep["blind_p75"],
        "nonblind_p25": sep["nonblind_p25"],
        "reason": sep["reason"],
    }


def blind_versus_nonblind() -> dict:
    report = audit_independence(BLIND, NONBLIND)
    return {
        "verdict": report["verdict"],
        "independence_achieved": report["independence_achieved"],
        "configured_blind": report["configured_blind"],
        "separation": _compact_sep(report["separation"]),
        "blind_token_distribution": report["blind_token_distribution"],
        "nonblind_token_distribution": report["nonblind_token_distribution"],
        "claimed_shared_phrase_count": report["shared_phrase_census"]["claimed_count"],
        "control_shared_phrase_count": report["shared_phrase_census"]["control_count"],
        "control_shared_phrases_head": [
            p["phrase"] for p in report["shared_phrase_census"]["control_run"][:5]
        ],
        "claimed_shared_phrases_head": [
            p["phrase"] for p in report["shared_phrase_census"]["claimed_run"][:5]
        ],
        "summary": report["summary"],
        "seat_count_claimed": report["council"]["claimed"]["seat_count"],
        "seat_count_control": report["council"]["control"]["seat_count"],
    }


def theatre_versus_nonblind() -> dict:
    """Configured-blind but copied briefs must NOT be declared independent."""
    report = audit_independence(THEATRE, NONBLIND)
    return {
        "verdict": report["verdict"],
        "independence_achieved": report["independence_achieved"],
        "configured_blind": report["configured_blind"],
        "separation": _compact_sep(report["separation"]),
        "claimed_shared_phrase_count": report["shared_phrase_census"]["claimed_count"],
        "summary": report["summary"],
    }


def identical_control() -> dict:
    text = IDENTICAL.read_text(encoding="utf-8")
    report = identical_ceiling(text, copies=3)
    council = load_council(
        {
            "council_id": "identical-negative-control",
            "configuration": {"blind_first_round": True},
            "briefs": [
                {"seat_id": "dup-0", "text": text},
                {"seat_id": "dup-1", "text": text},
                {"seat_id": "dup-2", "text": text},
            ],
        }
    )
    census = shared_phrase_census(council.texts())
    return {
        "copies": report["copies"],
        "token_scores": report["token_scores"],
        "all_token_at_ceiling": report["all_token_at_ceiling"],
        "ceiling": report["ceiling"],
        "shared_phrase_count": report["shared_phrase_count"],
        "shared_phrases_head": [p["phrase"] for p in report["shared_phrases_head"][:5]],
        "census_from_loader": len(census),
        "configured_blind": council.configured_blind,
    }


def dump() -> dict:
    return {
        "blind_versus_nonblind": blind_versus_nonblind(),
        "theatre_versus_nonblind": theatre_versus_nonblind(),
        "identical_control": identical_control(),
    }


if __name__ == "__main__":
    print(json.dumps(dump(), indent=2, sort_keys=True))
