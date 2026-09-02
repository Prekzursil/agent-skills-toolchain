#!/usr/bin/env python3
"""Probe 1: deferred-resolution fixture remains scoreable without the original session.

Copies only trajectory.json + resolution.json into an empty temp directory that
contains no session/ folder, then scores. Hand Brier values are literals in this
file, not read from the author's report.
"""
from __future__ import annotations

import math
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import score as S  # noqa: E402

HAND_BRIER = {
    "alice": (0.8 - 1.0) ** 2,
    "bob": (0.6 - 1.0) ** 2,
    "cara": (0.3 - 1.0) ** 2,
}
HAND_MEAN = sum(HAND_BRIER.values()) / 3.0


def main() -> int:
    src = HERE / "fixtures" / "deferred_scoreable"
    with tempfile.TemporaryDirectory(prefix="cnl-0074-deferred-") as raw:
        dest = Path(raw) / "frozen-record"
        dest.mkdir()
        shutil.copy2(src / "trajectory.json", dest / "trajectory.json")
        shutil.copy2(src / "resolution.json", dest / "resolution.json")
        session_dir = dest / "session"
        session_absent = not session_dir.exists()
        report = S.score_paths(dest / "trajectory.json", dest / "resolution.json")
        by_who = {r["participant_id"]: r for r in report["rows"]}
        brier_ok = True
        for who, expected in HAND_BRIER.items():
            got = by_who[who]["brier"]
            match = math.isclose(got, expected, rel_tol=0.0, abs_tol=1e-12)
            print(
                f"hand {who} expected={expected:.12f} got={got:.12f} match={match} "
                f"status={by_who[who]['status']}"
            )
            brier_ok = brier_ok and match and by_who[who]["status"] == "RESOLVED"
        mean_ok = math.isclose(
            report["mean_brier"], HAND_MEAN, rel_tol=0.0, abs_tol=1e-12
        )
        print(
            f"session_absent={session_absent} n_resolved={report['n_resolved']} "
            f"n_unscoreable={report['n_unscoreable']} mean_brier={report['mean_brier']} "
            f"hand_mean={HAND_MEAN} mean_ok={mean_ok} not_yet_meaningful={report['not_yet_meaningful']}"
        )
        if not (
            session_absent
            and brier_ok
            and mean_ok
            and report["n_resolved"] == 3
            and report["n_unscoreable"] == 0
            and report["mean_brier"] is not None
        ):
            print("FAILED:CNL-0074-probe1 deferred record was not scoreable without session")
            return 1
        print("SUCCESS:CNL-0074-probe1 deferred-resolution scoreable without session")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
