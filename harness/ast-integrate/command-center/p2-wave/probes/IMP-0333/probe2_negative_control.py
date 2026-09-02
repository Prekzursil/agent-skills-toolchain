#!/usr/bin/env python3
"""Named probe 2: negative control + timing audit (adversarial reviewer).

Starts from the tests, not the author's summary. Re-runs test_oxford.py,
then independently checks:
  * evidence-decisive motion + evidence-bound speakers -> LOW side-swap flip
  * same motion + side-bound speakers -> HIGH flip (detector is not vacuous)
  * turn-timing audit: overrun flagged, in-budget silent
A high flip rate on the decisive evidence-bound condition would mean the
protocol is measuring rhetoric, not truth.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

import scenario as S  # noqa: E402
from tools.council.protocol.oxford import (  # noqa: E402
    DebateConfig,
    EvidenceBoundSpeaker,
    HIGH_FLIP_FLOOR,
    LOW_FLIP_CEILING,
    LocalTurnLoop,
    OxfordProtocol,
    side_swap_experiment,
)

ART = REPO / S.ART


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0333-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:IMP-0333-probe2 receipt unparseable {exc}")
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:IMP-0333-probe2 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:IMP-0333" not in text:
        print("FAILED:IMP-0333-probe2 sentinel absent")
        return 1

    test = subprocess.run(
        ["python3", "-B", "tools/council/tests/test_oxford.py"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=120,
    )
    combined = ((test.stdout or "") + (test.stderr or "")).strip()
    if test.returncode != 0 or "SUCCESS:IMP-0333 tests" not in combined:
        print("FAILED:IMP-0333-probe2 unit tests did not pass")
        print(combined[-3000:])
        return 1

    low = side_swap_experiment(
        S.decisive(), S.evidence_speakers(), S.ASSIGNMENTS, S.CONFIG
    )
    high = side_swap_experiment(
        S.decisive(), S.side_speakers(), S.ASSIGNMENTS, S.CONFIG
    )
    if not low["evidence_decisive"]:
        print("FAILED:IMP-0333-probe2 decisive motion not marked decisive")
        return 1
    if float(low["flip_rate"]) > LOW_FLIP_CEILING:
        print(
            f"FAILED:IMP-0333-probe2 negative control failed: "
            f"evidence-bound decisive flip_rate={low['flip_rate']}"
        )
        return 1
    if float(high["flip_rate"]) < HIGH_FLIP_FLOOR:
        print(
            f"FAILED:IMP-0333-probe2 detector vacuous: "
            f"side-bound decisive flip_rate={high['flip_rate']}"
        )
        return 1

    slow = {
        "alice": EvidenceBoundSpeaker("alice", elapsed_ms=5000),
        "bob": EvidenceBoundSpeaker("bob", elapsed_ms=5000),
    }
    fast = {
        "alice": EvidenceBoundSpeaker("alice", elapsed_ms=10),
        "bob": EvidenceBoundSpeaker("bob", elapsed_ms=10),
    }
    cfg = DebateConfig(turn_budget_ms=100, max_rebuttal_depth=1)
    over = OxfordProtocol(cfg, LocalTurnLoop()).run(
        S.decisive(), slow, S.ASSIGNMENTS
    )
    ok = OxfordProtocol(cfg, LocalTurnLoop()).run(
        S.decisive(), fast, S.ASSIGNMENTS
    )
    if over.timing is None or over.timing.overrun_count != len(over.turns):
        print(
            f"FAILED:IMP-0333-probe2 overrun not flagged "
            f"overruns={getattr(over.timing, 'overrun_count', None)}"
        )
        return 1
    if not all(t.timed_out for t in over.turns):
        print("FAILED:IMP-0333-probe2 timed_out flag missing on overruns")
        return 1
    if ok.timing is None or ok.timing.overrun_count != 0:
        print("FAILED:IMP-0333-probe2 in-budget run was not silent")
        return 1
    if any(t.timed_out for t in ok.turns):
        print("FAILED:IMP-0333-probe2 in-budget turn marked timed_out")
        return 1

    reviewer = doc.get("reviewer") or {}
    if str(reviewer.get("verdict") or "").upper() != "PASS":
        print(f"FAILED:IMP-0333-probe2 reviewer verdict {reviewer.get('verdict')}")
        return 1

    payload = {
        "detector_not_vacuous": True,
        "evidence_bound_decisive_flip_rate": low["flip_rate"],
        "in_budget_silent": True,
        "overrun_flagged": True,
        "overrun_count": over.timing.overrun_count,
        "pass": True,
        "probe": "probe2-negative-control",
        "side_bound_decisive_flip_rate": high["flip_rate"],
        "tests_passed": True,
        "unit_id": "IMP-0333",
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"tests_ok=True low_flip={low['flip_rate']} high_flip={high['flip_rate']} "
        f"overruns={over.timing.overrun_count} in_budget_silent=True"
    )
    print("SUCCESS:IMP-0333-probe2 negative control and timing audit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
