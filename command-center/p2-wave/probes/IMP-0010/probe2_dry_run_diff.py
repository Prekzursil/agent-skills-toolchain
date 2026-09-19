#!/usr/bin/env python3
"""IMP-0010 probe2: dry-run deploy vs prediction diff (signal 2)."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "plugin"))
import projection_map as P  # noqa: E402

PROBE = Path(__file__).resolve().parent
EVIDENCE = (
    "TWO independent signals: (1) the projection map's predicted live-path set "
    "for the current manifest; (2) an actual dry-run deploy into a throwaway HOME "
    "whose resulting file listing is diffed against the prediction. Any "
    "predicted-but-absent or present-but-unpredicted path fails the unit."
)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="imp0010-probe2-"))
    home = tmp / "HOME"
    try:
        predicted = P.predict_live_paths(REPO, home=home)
        actual = P.dry_run_deploy(REPO, home=home)
        diff = P.diff_prediction_against_dry_run(predicted, actual)
        confirmed = bool(diff.get("ok")) and diff.get("predicted_count", 0) > 0
        meas = {
            "probe": "probe2-dry-run-diff",
            "probe_2_confirmed": confirmed,
            "ok": confirmed,
            "home": str(home),
            "diff": diff,
            "actual_sample": actual[:8],
        }
        (PROBE / "probe2-measurement.json").write_text(
            json.dumps(meas, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        lines = [
            "NAMED PROBE 2: DRY-RUN DEPLOY DIFF AGAINST PREDICTION",
            "PROBE-2-BEGIN:IMP-0010",
            "stage=p2-deliver",
            f"evidence_requirement_verbatim={EVIDENCE}",
            f"home={home}",
            f"predicted_count={diff.get('predicted_count')}",
            f"actual_count={diff.get('actual_count')}",
            f"predicted_but_absent={diff.get('predicted_but_absent')}",
            f"present_but_unpredicted={diff.get('present_but_unpredicted')}",
            f"diff_ok={diff.get('ok')}",
            f"probe_2_confirmed={confirmed}",
            "PROBE-2-COMPLETE:IMP-0010",
            "SUCCESS:IMP-0010-probe2" if confirmed else "FAILED:IMP-0010-probe2",
        ]
        raw = "\n".join(lines) + "\n"
        (PROBE / "probe2-dry-run-diff.raw.txt").write_text(raw, encoding="utf-8")
        print(raw, end="")
        return 0 if confirmed else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
