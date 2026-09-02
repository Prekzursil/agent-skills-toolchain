#!/usr/bin/env python3
"""Named probe 1: pairwise contradiction matrix with file:line citations."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from pairwise import run  # noqa: E402

REPO = HERE.parents[3]
ART = REPO / "command-center/adversarial/ADV-0057-governance-policy-legal-coherence.json"
ALLOWED = {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0057-probe1 {msg}")
    return 1


def verify_artifact(live: dict) -> str | None:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return None
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return f"unparseable:{exc}"
    if doc.get("unit_id") != "ADV-0057":
        return f"unit_id {doc.get('unit_id')}"
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"self-declared:{st}"
    if "SUCCESS:ADV-0057" not in text:
        return "sentinel-absent"
    if not live["negative_control"]["ok"]:
        return "live-negative-control-failed"
    recorded = ((doc.get("report") or {}).get("pairwise") or {}).get(
        "contradiction_count"
    )
    if recorded is not None and recorded != live["live"]["contradiction_count"]:
        return f"artifact-matrix-drift recorded={recorded} live={live['live']['contradiction_count']}"
    targets = doc.get("targets")
    if not isinstance(targets, list) or not targets:
        targets = ((doc.get("report") or {}).get("targets") or [])
    verdicts = [
        str(t.get("verdict"))
        for t in targets
        if isinstance(t, dict)
    ]
    if not verdicts:
        return "no-targets"
    bad = [v for v in verdicts if v not in ALLOWED]
    if bad:
        return f"illegal-verdict:{bad[:3]}"
    return None


def main() -> int:
    live = run()
    print(json.dumps(live, sort_keys=True))
    print(
        "comparable_pairs={0} contradictions={1} planted_fired={2} planted_silent_clean={3}".format(
            live["live"]["comparable_pair_count"],
            live["live"]["contradiction_count"],
            live["negative_control"]["detector_fired"],
            live["negative_control"]["silent_on_good"],
        )
    )
    if not live.get("pass"):
        return fail("planted contradiction detector did not calibrate")
    err = verify_artifact(live)
    if err:
        return fail(err)
    print("SUCCESS:ADV-0057-probe1 pairwise matrix and planted CLA-vs-DCO control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
