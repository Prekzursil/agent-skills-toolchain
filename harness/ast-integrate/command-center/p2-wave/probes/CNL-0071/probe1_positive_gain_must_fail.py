#!/usr/bin/env python3
"""Probe 1: information-gain trace attached; positive-gain irreducibility must FAIL.

Two independent signals per round:
  1) set-cardinality + vote Hamming (gain.py)
  2) sha256 of canonical claim/evidence dumps + vote-tuple inequality (fingerprint.py)
Disagreement between those two is a failed probe, not a picked winner.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from fingerprint import attach_moves  # noqa: E402
from gain import attach_trace, last_defined_gain  # noqa: E402
from irreducibility import attach_honest_trace, check_declaration  # noqa: E402

ART = (
    REPO
    / "command-center/design/council/CNL-0071-irreducible-disagreement-when-to-stop-trying-to-converge.md"
)
BAD = HERE / "fixtures/planted-bad.json"
GOOD = HERE / "fixtures/known-good.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def signals_agree(run: dict) -> tuple[bool, str]:
    rounds = list(run.get("rounds") or [])
    g = attach_trace(rounds)
    m = attach_moves(rounds)
    if len(g) != len(m):
        return False, f"len gain={len(g)} moves={len(m)}"
    for a, b in zip(g, m):
        if a.get("gain") is None or b.get("moved") is None:
            continue
        pos = int(a["gain"]) > 0
        if pos != bool(b["moved"]):
            return False, f"round {a.get('round')}: gain={a['gain']} moved={b['moved']}"
    return True, "ok"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNL-0071-probe1 design note missing")
        return 1
    note = json.loads(ART.read_text(encoding="utf-8"))
    blob = json.dumps(note)
    if note.get("unit_id") != "CNL-0071":
        print("FAILED:CNL-0071-probe1 unit_id", note.get("unit_id"))
        return 1
    if "SUCCESS:CNL-0071" not in blob:
        print("FAILED:CNL-0071-probe1 sentinel absent")
        return 1
    if str(note.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNL-0071-probe1 self-declared", note.get("state"))
        return 1

    raw_bad = load(BAD)
    ok, why = signals_agree(raw_bad)
    print(f"signal_agree_bad={ok} {why}")
    if not ok:
        print("FAILED:CNL-0071-probe1 independent signals disagree on planted-bad")
        return 1

    traced = attach_honest_trace(raw_bad)
    last = last_defined_gain(traced["information_gain_trace"])
    print(f"planted_bad_last_gain={last} trace_attached={True}")
    print("trace_verbatim=" + json.dumps(traced["information_gain_trace"], sort_keys=True))
    if last is None or last <= 0:
        print("FAILED:CNL-0071-probe1 planted-bad fixture is not still-gaining")
        return 1

    verdict = check_declaration(traced)
    print(
        "positive_gain_declaration "
        f"fired={verdict.get('fired')} silent={verdict.get('silent')} "
        f"reason={verdict.get('reason')} last_gain={verdict.get('last_gain')}"
    )
    if not verdict.get("fired") or verdict.get("reason") != "positive-gain":
        print("FAILED:CNL-0071-probe1 declaring irreducibility while gain>0 did not FAIL")
        return 1

    missing = copy.deepcopy(raw_bad)
    missing.pop("information_gain_trace", None)
    miss = check_declaration(missing)
    print(f"missing_trace fired={miss.get('fired')} reason={miss.get('reason')}")
    if not miss.get("fired") or miss.get("reason") != "missing-information-gain-trace":
        print("FAILED:CNL-0071-probe1 missing trace was not rejected")
        return 1

    raw_good = load(GOOD)
    ok_g, why_g = signals_agree(raw_good)
    print(f"signal_agree_good={ok_g} {why_g}")
    if not ok_g:
        print("FAILED:CNL-0071-probe1 independent signals disagree on known-good")
        return 1
    good = attach_honest_trace(raw_good)
    good_v = check_declaration(good)
    print(
        "known_good "
        f"fired={good_v.get('fired')} silent={good_v.get('silent')} "
        f"accepted={good_v.get('accepted')} reason={good_v.get('reason')}"
    )
    if good_v.get("fired") or not good_v.get("accepted"):
        print("FAILED:CNL-0071-probe1 known-good was rejected")
        return 1

    print("SUCCESS:CNL-0071-probe1 positive-gain irreducible declaration rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
