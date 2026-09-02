#!/usr/bin/env python3
"""Named probe 2: planted-wrong-median negative control and identity leak.

If evidence gating works, a planted wrong median must not drag the panel. If it
does drag, the module must emit an ANCHORING finding rather than suppress it.
The ungated ablation must follow the plant (both-states). Honest feedback must
not flag anchoring. Feedback payloads must not carry panelist identities; the
scanner must fire on an injected id.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from tools.council.topology.delphi import experiment_planted_median  # noqa: E402


def main() -> int:
    result = experiment_planted_median(seed=286)
    slim = {k: v for k, v in result.items() if k != "pass_rule"}
    print(json.dumps(slim, default=str))
    print(
        "gated_drag={g} ungated_drag={u} honest_drag={h} "
        "leak_fire={lf} leak_silent={ls} finding={f}".format(
            g=result["gated_anchoring_detected"],
            u=result["ungated_ablation_anchoring_detected"],
            h=result["honest_feedback_anchoring_detected"],
            lf=result["leak_scanner_fired_on_injected_id"],
            ls=result["leak_scanner_silent_on_clean_feedback"],
            f=result["anchoring_finding"] is not None,
        )
    )
    if result.get("anchoring_finding") is not None:
        print("ANCHORING finding (not suppressed):", result["anchoring_finding"])
        print("FAILED:IMP-0286-probe2 gated path followed the planted median")
        return 1
    if not result["passed"]:
        print("FAILED:IMP-0286-probe2 planted-median / anonymity contract")
        return 1
    print("SUCCESS:IMP-0286-probe2 planted-wrong-median and anonymity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
