#!/usr/bin/env python3
"""IMP-0010 negative control: remove one manifest entry → exactly one path gone."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "plugin"))
import projection_map as P  # noqa: E402

PROBE = Path(__file__).resolve().parent


def main() -> int:
    deployed = P.load_deployed(REPO)
    home = Path("/tmp/imp0010-neg-home")
    baseline = P.predict_live_paths(REPO, home=home, deployed=deployed)
    removed = deployed[0]
    mutated = copy.deepcopy(deployed)
    mutated.pop(0)
    reduced = P.predict_live_paths(REPO, home=home, deployed=mutated)
    disappeared = baseline - reduced
    appeared = reduced - baseline
    exact_one = len(disappeared) == 1 and not appeared
    silent_on_good = len(baseline) == len(
        P.predict_live_paths(REPO, home=home, deployed=deployed)
    )
    fired = exact_one and silent_on_good
    only = next(iter(disappeared)) if disappeared else None
    meas = {
        "negative_control_fired": fired,
        "ok": fired,
        "exact_one_path_disappeared": exact_one,
        "disappeared_count": len(disappeared),
        "appeared_count": len(appeared),
        "removed_skill": removed.get("name") if isinstance(removed, dict) else None,
        "disappeared_path": only,
        "silent_on_good": silent_on_good,
        "baseline_count": len(baseline),
        "reduced_count": len(reduced),
    }
    (PROBE / "negative-control-measurement.json").write_text(
        json.dumps(meas, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "NEGATIVE CONTROL: REMOVE ONE DEPLOYED SKILL → EXACTLY ONE PATH GONE",
        "NEG-BEGIN:IMP-0010",
        f"removed_skill={meas['removed_skill']}",
        f"baseline_count={meas['baseline_count']}",
        f"reduced_count={meas['reduced_count']}",
        f"disappeared_count={meas['disappeared_count']}",
        f"appeared_count={meas['appeared_count']}",
        f"disappeared_path={meas['disappeared_path']}",
        f"exact_one_path_disappeared={exact_one}",
        f"silent_on_good={silent_on_good}",
        f"negative_control_fired={fired}",
        "NEG-COMPLETE:IMP-0010",
        "SUCCESS:IMP-0010-neg" if fired else "FAILED:IMP-0010-neg",
    ]
    raw = "\n".join(lines) + "\n"
    (PROBE / "negative-control.raw.txt").write_text(raw, encoding="utf-8")
    print(raw, end="")
    return 0 if fired else 1


if __name__ == "__main__":
    raise SystemExit(main())
