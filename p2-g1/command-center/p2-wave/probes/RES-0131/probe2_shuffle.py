#!/usr/bin/env python3
"""Probe 2: shuffle negative control + independent Spearman implementation.

Both-states: identity pairing must keep rho; shuffling online scores must
collapse median |rho| toward zero. Treating identity as the shuffle must fail.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import compute as C  # noqa: E402
import stats as ST  # noqa: E402

ART = REPO / C.ART_REL
EPS = 1e-9


def fail(msg: str) -> int:
    print(f"FAILED:RES-0131-probe2 {msg}")
    return 1


def main() -> int:
    live = C.measure()
    reasons: list[str] = []
    if not live["alt_agrees"]:
        reasons.append("alt spearman disagrees")
    if not live["shuffle_collapses"]:
        reasons.append(
            f"shuffle median |rho|={live['shuffle_median_abs_rho_final']} "
            f"did not collapse vs {live['rho_offline_vs_npms_final']}"
        )
    if not live["identity_does_not_collapse"]:
        reasons.append("identity pairing changed rho")
    if live["constructed_sorted_rho_final"] <= abs(live["rho_offline_vs_npms_final"]) + 0.2:
        reasons.append(
            f"sorted-vs-sorted rho={live['constructed_sorted_rho_final']} "
            f"did not rise above observed {live['rho_offline_vs_npms_final']}"
        )
    if not live["offline_not_copy_of_online"]:
        reasons.append("offline copies online")

    # both-states: fake shuffle = identity must NOT count as collapse
    offline = [r["offline_score"] for r in live["rows"]]
    final = [r["online_final"] for r in live["rows"]]
    fake = [ST.spearman(offline, final) for _ in live["shuffle_seeds"]]
    fake_med = ST.median([abs(x) for x in fake])
    fake_collapses = fake_med < abs(live["rho_offline_vs_npms_final"]) and fake_med < 0.30
    if fake_collapses:
        reasons.append("identity-as-shuffle incorrectly collapsed")

    if not ART.is_file():
        reasons.append("artifact missing")
    else:
        doc = json.loads(ART.read_text(encoding="utf-8"))
        nc = doc.get("negative_control") or {}
        if nc.get("collapses_toward_zero") is not True:
            reasons.append("artifact shuffle flag false")
        if nc.get("identity_does_not_collapse") is not True:
            reasons.append("artifact identity flag false")
        if abs(float(nc.get("shuffle_median_abs_rho_final")) - live["shuffle_median_abs_rho_final"]) > EPS:
            reasons.append("artifact shuffle median mismatch")
        if abs(float(nc.get("observed_rho_final")) - live["rho_offline_vs_npms_final"]) > EPS:
            reasons.append("artifact observed rho mismatch")
        if (doc.get("reviewer") or {}).get("independent") is not True:
            reasons.append("reviewer not independent")
        if str((doc.get("reviewer") or {}).get("verdict") or "").upper() != "PASS":
            reasons.append("reviewer verdict not PASS")

    payload = {
        "probe": "probe2-shuffle",
        "unit_id": "RES-0131",
        "rho_final": live["rho_offline_vs_npms_final"],
        "shuffle_median_abs_rho_final": live["shuffle_median_abs_rho_final"],
        "identity_rho_final": live["identity_rho_final"],
        "fake_identity_shuffle_median": fake_med,
        "fake_would_collapse": fake_collapses,
        "constructed_sorted_rho": live["constructed_sorted_rho_final"],
        "reasons": reasons,
    }
    print(json.dumps(payload, sort_keys=True))
    if reasons:
        return fail("; ".join(reasons))
    print(
        f"shuffle_median_abs={live['shuffle_median_abs_rho_final']:.6f} "
        f"observed={live['rho_offline_vs_npms_final']:.6f} "
        f"identity={live['identity_rho_final']:.6f}"
    )
    print("SUCCESS:RES-0131-probe2 shuffle negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
