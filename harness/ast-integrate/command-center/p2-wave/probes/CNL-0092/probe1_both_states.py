#!/usr/bin/env python3
"""Probe 1: detector-control, both-states, false-positive rate, negative control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import evaluate as E  # noqa: E402

RAW = HERE / "probe1-both-states.raw.json"
ART = (
    HERE.parents[3]
    / "command-center/design/council/CNL-0092-missing-expertise-detection-and-the-recruitment-trigger.md"
)


def _check_artifact(live: dict) -> str | None:
    if not ART.is_file():
        return None
    try:
        doc = json.loads(ART.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"artifact-unparseable:{type(exc).__name__}"
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"artifact-self-declared:{doc.get('state')}"
    if "SUCCESS:CNL-0092" not in ART.read_text(encoding="utf-8"):
        return "artifact-sentinel-absent"
    both = doc.get("both_states") or {}
    if both.get("planted_bad_fired") is not True:
        return "artifact-both-states-bad"
    if both.get("known_good_silent") is not True:
        return "artifact-both-states-good"
    try:
        fp = float(doc.get("false_positive_rate"))
    except (TypeError, ValueError):
        return "artifact-fp-not-number"
    if abs(fp - float(live["false_positive_rate"])) > 1e-12:
        return f"artifact-fp-drift:{fp}"
    if live["false_positive_rate"] != 0.0:
        return f"live-fp-nonzero:{live['false_positive_rate']}"
    return None


def main() -> int:
    live = E.both_states()
    RAW.write_text(json.dumps(live, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"detector_control_fired={live.get('detector_control_fired')}")
    print(f"planted_bad_fired={live.get('planted_bad_fired')}")
    print(f"known_good_silent={live.get('known_good_silent')}")
    print(f"false_positive_rate={live.get('false_positive_rate')}")
    print(f"bad_misses={live.get('bad_misses')}")
    print(live.get("negative_control_verbatim", ""))
    if not live.get("pass"):
        print("FAILED:CNL-0092-probe1 both-states")
        print(json.dumps({k: live[k] for k in live if k not in {"verbatim_bad", "verbatim_good", "control", "known_good"}}, indent=2, default=str)[:2000])
        return 1
    art_err = _check_artifact(live)
    if art_err:
        print(f"FAILED:CNL-0092-probe1 {art_err}")
        return 1
    print("SUCCESS:CNL-0092-probe1 both-states detector-control fp-rate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
