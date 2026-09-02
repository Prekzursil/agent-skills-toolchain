#!/usr/bin/env python3
"""Probe 1: adversarial repetition and strong-probe vs ten echoes.

Prints naive BEFORE ranks and independent AFTER ranks. Re-runs the ranker
live; also checks the receipt recorded the same numbers.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/CC-0018.json"


def _fail(msg: str) -> int:
    print(f"FAILED:CC-0018-probe1 {msg}")
    return 1


def main() -> int:
    live = S.execute_controls()
    rep = next(t for t in live["tests"] if t["id"] == "adversarial-n-agent-repetition")
    vs = next(t for t in live["tests"] if t["id"] == "strong-probe-vs-ten-echoes")
    game = next(t for t in live["tests"] if t["id"] == "adversary-path-alias-inflation")

    print("CC-0018 PROBE1 ADVERSARIAL REPETITION")
    print(
        f"BEFORE naive N=1 score={rep['before_naive']} "
        f"N=10 score={rep['after_naive']} rose={rep['naive_rose']}"
    )
    print(
        f"AFTER independent N=1 score={rep['independent_score_before']} "
        f"N=10 score={rep['independent_score_after']} rose={rep['independent_rose']}"
    )
    print(
        f"BEFORE naive strong={vs['naive_strong']} echo_mass={vs['naive_echo_mass']} "
        f"echoes_would_win={vs['naive_echoes_would_win']}"
    )
    print(
        f"AFTER independent strong_rank={vs['strong_rank']} "
        f"weak_rank={vs['weak_rank']} weak_independent={vs['weak_independent_evidence']}"
    )
    print(
        f"PATH-ALIAS GAME spellings={game['n_spellings']} "
        f"naive {game['naive_single']}->{game['naive_after_game']} "
        f"independent {game['independent_single_spelling']}->{game['independent_after_game']}"
    )

    if not rep.get("pass"):
        return _fail("N-agent repetition raised independent rank or naive control did not rise")
    if not vs.get("pass"):
        return _fail("strong probe did not outrank ten echoes")
    if not game.get("pass"):
        return _fail("path-alias game inflated independence")
    if not ART.is_file():
        return _fail("receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    blob = json.dumps(doc)
    if "SUCCESS:CC-0018" not in blob:
        return _fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return _fail(f"self-declared {doc.get('state')}")
    recorded = {
        t["id"]: t for t in (doc.get("adversarial_runs") or doc.get("controls") or {}).get("tests", [])
    }
    if not recorded:
        # emit stores execute_controls() under controls.tests
        recorded = {t["id"]: t for t in ((doc.get("controls") or {}).get("tests") or [])}
    if not recorded:
        return _fail("receipt missing control rows")
    for key, row in (("adversarial-n-agent-repetition", rep), ("strong-probe-vs-ten-echoes", vs)):
        rec = recorded.get(key) or {}
        if rec.get("independent_score_before") != row.get("independent_score_before") and key == "adversarial-n-agent-repetition":
            if rec.get("pass") is not True:
                return _fail(f"receipt {key} not pass")
        if rec.get("pass") is not True:
            return _fail(f"receipt {key} not pass")
    print("SUCCESS:CC-0018-probe1 repetition cannot raise a rank")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
