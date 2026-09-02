"""Probe 1: null-change control measures the noise band on the live harness.

Catalog tests_required[0]: control: null-change run establishes the noise band.
The width must equal max(samples)-min(samples) from THIS run. An assumed
constant (2%, 0.05, comparison against zero) cannot satisfy that equality
unless the live samples happen to match — and we also require sample
spread, so a hardcoded zero band fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from selfimprove.measure import Harness, measure_null_change, measurement_session  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0372-probe1 {msg}")
    return 1


def main() -> int:
    with measurement_session() as (origin, parent):
        result = measure_null_change(origin, harness=Harness(), parent=parent, label="probe1")
    band = result["noise_band"]
    samples = [float(x) for x in band["samples"]]
    independent_width = max(samples) - min(samples)
    distinct = {round(x, 6) for x in samples}

    checks = {
        "source_measured": band.get("source") == "measured-null-change",
        "not_assumed": band.get("assumed") is False,
        "not_vs_zero": band.get("compared_against_zero") is False,
        "n_ge_5": int(band.get("n") or 0) >= 5,
        "spread": len(distinct) >= 3 and independent_width > 0,
        "width_matches_samples": abs(float(band["width"]) - independent_width) < 1e-12,
        "origin_unchanged": result["isolation"]["origin_unchanged"] is True,
        "method_git_worktree": result["isolation"]["method"] == "git-worktree",
        "regression_passed": result["suite"]["regression"]["ok"] is True,
    }
    payload = {
        "probe": "probe1-null-change-noise-band",
        "unit_id": "IMP-0372",
        "pass": all(checks.values()),
        "checks": checks,
        "n": band["n"],
        "width": band["width"],
        "independent_width": independent_width,
        "source": band["source"],
        "assumed": band["assumed"],
        "samples": samples,
        "isolation": result["isolation"],
        "compared_against": result["compared_against"],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        failed = [k for k, v in checks.items() if not v]
        return fail(f"checks failed: {failed}")
    print(
        "SUCCESS:IMP-0372-probe1 null-change measured noise band "
        f"n={band['n']} width={band['width']:.6f} source={band['source']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
