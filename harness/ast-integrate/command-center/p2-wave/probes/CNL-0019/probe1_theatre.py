"""Theatre probe: assigned-position vs real-prior must converge differently.

Thresholds are read from fixtures.json (declared before scoring).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import simulate as SIM  # noqa: E402
from priors import load_fixtures  # noqa: E402


def compare() -> dict:
    doc = load_fixtures()
    thr = SIM.thresholds_from_fixtures(doc)
    theatre = SIM.run_roster(
        doc["rosters"]["theatre_assigned_position"]["seats"],
        rounds=int(thr["ROUNDS"]),
        alpha=float(thr["ALPHA"]),
    )
    real = SIM.run_roster(
        doc["rosters"]["real_prior"]["seats"],
        rounds=int(thr["ROUNDS"]),
        alpha=float(thr["ALPHA"]),
    )
    revealed_gap = abs(
        theatre["revealed_disagreement"] - real["revealed_disagreement"]
    )
    theatre_ok = SIM.theatre_signature(theatre, thr)
    real_ok = SIM.real_signature(real, thr)
    different = revealed_gap >= thr["MEASURABLE_REVEALED_GAP"]
    # Assigned-position must NOT match the real-prior revealed channel.
    same_would_unprove = (
        abs(theatre["revealed_disagreement"] - real["revealed_disagreement"])
        < thr["MEASURABLE_REVEALED_GAP"]
    )
    ok = theatre_ok and real_ok and different and not same_would_unprove
    return {
        "ok": ok,
        "theatre_ok": theatre_ok,
        "real_ok": real_ok,
        "measurably_different": different,
        "revealed_gap": revealed_gap,
        "thresholds": thr,
        "theatre": {
            "public_disagreement": theatre["public_disagreement"],
            "revealed_disagreement": theatre["revealed_disagreement"],
            "channel_gap": theatre["channel_gap"],
            "public_final": theatre["public_final"],
            "revealed_final": theatre["revealed_final"],
            "seat_ids": theatre["seat_ids"],
        },
        "real": {
            "public_disagreement": real["public_disagreement"],
            "revealed_disagreement": real["revealed_disagreement"],
            "channel_gap": real["channel_gap"],
            "public_final": real["public_final"],
            "revealed_final": real["revealed_final"],
            "seat_ids": real["seat_ids"],
        },
    }


def main() -> int:
    row = compare()
    print(json.dumps(row, sort_keys=True))
    print(
        "theatre_public={:.4f} theatre_revealed={:.4f} "
        "real_public={:.4f} real_revealed={:.4f} revealed_gap={:.4f}".format(
            row["theatre"]["public_disagreement"],
            row["theatre"]["revealed_disagreement"],
            row["real"]["public_disagreement"],
            row["real"]["revealed_disagreement"],
            row["revealed_gap"],
        )
    )
    print(
        f"theatre_ok={row['theatre_ok']} real_ok={row['real_ok']} "
        f"measurably_different={row['measurably_different']}"
    )
    if not row["ok"]:
        print("FAILED:CNL-0019-probe1 theatre and real-prior did not diverge")
        return 1
    print("SUCCESS:CNL-0019-probe1 assigned-position vs real-prior divergence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
