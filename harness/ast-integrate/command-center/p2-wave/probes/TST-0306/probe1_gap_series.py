#!/usr/bin/env python3
"""Probe 1: dev-versus-shadow gap tracked per improvement iteration.

Catalog tests_required:
  * Dev-versus-shadow gap tracked per improvement iteration.
  * Detector control: deliberately tune on a shadow case and confirm the
    gap widens detectably.

Also: the series is the evidence, not a single snapshot. A one-point spike
that recovers must ALLOW (max(gap) would false-positive). An overfit climb
whose early gap is still below threshold must BLOCK by the end.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from bench.shadow_split import (  # noqa: E402
    GAP_THRESHOLD,
    N_ITER,
    SLOPE_THRESHOLD,
    GamedMemorizer,
    HonestThresholdLearner,
    draw_session,
    implementer_report,
    overfitting_verdict,
    redact_series,
    run_improvement_loop,
    spike_gap_series,
)


def fail(msg: str) -> int:
    print(f"FAILED:TST-0306-probe1 {msg}")
    return 1


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="tst0306-p1-"))
    session = draw_session(tmp, seed="tst-0306-probe1-v1")

    honest_series = run_improvement_loop(session, HonestThresholdLearner())
    gamed_series = run_improvement_loop(session, GamedMemorizer())
    one_shadow = session.shadow_cases_for("detector", "detector-control")[:1]
    tuned_series = run_improvement_loop(
        session,
        GamedMemorizer(),
        extra=one_shadow,
        actor="detector",
        purpose="detector-control",
    )
    v_honest = overfitting_verdict(honest_series)
    v_gamed = overfitting_verdict(gamed_series)
    v_tuned = overfitting_verdict(tuned_series)
    v_spike = overfitting_verdict(spike_gap_series())
    impl = implementer_report(gamed_series)
    impl_keys = {k for row in impl for k in row}

    checks = {
        "n_iter_is_10": N_ITER == 10,
        "honest_series_len": len(honest_series) == N_ITER + 1,
        "gamed_series_len": len(gamed_series) == N_ITER + 1,
        "tuned_series_len": len(tuned_series) == N_ITER + 1,
        "honest_allow": v_honest["verdict"] == "ALLOW",
        "honest_does_not_block_claim": v_honest["blocks_improvement_claim"] is False,
        "gamed_block": v_gamed["verdict"] == "BLOCK_OVERFIT",
        "gamed_blocks_claim_despite_dev": v_gamed["blocks_improvement_claim"] is True
        and gamed_series[-1]["dev"] > gamed_series[0]["dev"],
        "gamed_final_gap_ge_threshold": v_gamed["final_gap"] >= GAP_THRESHOLD,
        "gamed_slope_ge_threshold": v_gamed["slope"] >= SLOPE_THRESHOLD,
        "gamed_early_gap_below_threshold": gamed_series[1]["gap"] < GAP_THRESHOLD,
        "tune_on_one_shadow_still_blocks": v_tuned["verdict"] == "BLOCK_OVERFIT",
        "tune_on_one_shadow_gap_still_wide": v_tuned["final_gap"] >= GAP_THRESHOLD,
        "spike_allow": v_spike["verdict"] == "ALLOW",
        "spike_max_would_block": v_spike["snapshot_max_would_block"] is True,
        "spike_proves_not_max_snapshot": v_spike["verdict"] == "ALLOW"
        and v_spike["snapshot_max_would_block"] is True,
        "implementer_report_hides_shadow": "shadow" not in impl_keys
        and "gap" not in impl_keys,
        "threshold_versioned": v_gamed["threshold_version"] == "tst-0306-gap-v1",
    }
    payload = {
        "probe": "probe1-dev-versus-shadow-gap-series",
        "unit_id": "TST-0306",
        "pass": all(checks.values()),
        "checks": checks,
        "honest": {
            "verdict": v_honest["verdict"],
            "final_gap": round(v_honest["final_gap"], 6),
            "slope": round(v_honest["slope"], 6),
            "series": redact_series(honest_series),
        },
        "gamed": {
            "verdict": v_gamed["verdict"],
            "final_gap": round(v_gamed["final_gap"], 6),
            "slope": round(v_gamed["slope"], 6),
            "early_gap": round(gamed_series[1]["gap"], 6),
            "final_dev": round(gamed_series[-1]["dev"], 6),
            "final_shadow": round(gamed_series[-1]["shadow"], 6),
            "series": redact_series(gamed_series),
        },
        "tune_on_shadow_control": {
            "verdict": v_tuned["verdict"],
            "final_gap": round(v_tuned["final_gap"], 6),
            "final_shadow": round(tuned_series[-1]["shadow"], 6),
            "note": (
                "Learner was given one shadow case to special-case. The rest of "
                "the shadow split does not rise with DEV, so the gap still widens."
            ),
        },
        "spike_snapshot_control": {
            "verdict": v_spike["verdict"],
            "peak_gap": round(v_spike["peak_gap"], 6),
            "final_gap": round(v_spike["final_gap"], 6),
            "snapshot_max_would_block": v_spike["snapshot_max_would_block"],
        },
        "implementer_report_keys": sorted(impl_keys),
        "idset_sha256": session.shadow_idset_sha256(),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        failed = [k for k, v in checks.items() if not v]
        return fail(f"checks failed: {failed}")
    print(
        "SUCCESS:TST-0306-probe1 series n="
        f"{len(gamed_series)} gamed={v_gamed['verdict']} "
        f"honest={v_honest['verdict']} tune-on-shadow={v_tuned['verdict']} "
        f"spike={v_spike['verdict']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
