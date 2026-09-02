#!/usr/bin/env python3
"""Named probe 2: recompute majority error vs correlation; both-states control.

Signal 1: live beta-binomial curve matches the artifact points.
Signal 2: at rho=0 majority beats a single voter; at rho=1 they are equal.
A detector that only checked rho=0 would miss the identical-ballot collapse.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import curve as C  # noqa: E402

ART = REPO / "command-center/research/RES-0078.json"
SENTINEL = (
    "SUCCESS:RES-0078 in the receipt AND a traced-or-untraced verdict "
    "on the correlation figure plus an error-versus-correlation curve"
)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0078-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("catalog sentinel absent")
    doc = json.loads(text)
    block = doc.get("error_versus_correlation_curve") or {}
    points = block.get("points") or []
    if len(points) < 11:
        return fail(f"curve too short n={len(points)}")
    ascii_tbl = str(block.get("ascii") or "")
    if "majority" not in ascii_tbl or "dictator" not in ascii_tbl:
        return fail("ascii curve missing")

    n = int(block.get("n") or C.DEFAULT_N)
    p = float(block.get("p") or C.DEFAULT_P)
    live = C.error_curve(n, p)
    if len(live) != len(points):
        return fail(f"len live={len(live)} artifact={len(points)}")

    prev = -1.0
    mismatches = []
    for art, got in zip(points, live):
        rho = float(art["rho"])
        if abs(rho - got["rho"]) > 1e-12:
            return fail(f"rho grid drift {rho} vs {got['rho']}")
        ae = float(art["majority_error"])
        ge = got["majority_error"]
        if abs(ae - ge) > 1e-9:
            mismatches.append((rho, ae, ge))
        if ge + 1e-9 < prev:
            return fail(f"majority error not monotone at rho={rho}")
        prev = ge
    if mismatches:
        return fail(f"point mismatch {mismatches[:3]}")

    e0 = C.majority_error(n, p, 0.0)
    e1 = C.majority_error(n, p, 1.0)
    single = 1.0 - p
    if not (e0 < single - 1e-6):
        return fail(f"rho=0 control: majority {e0} not < single {single}")
    if abs(e1 - single) > 1e-9:
        return fail(f"rho=1 control: majority {e1} != single {single}")

    c0 = block.get("control_independent") or {}
    c1 = block.get("control_identical") or {}
    if c0.get("majority_beats_single") is not True:
        return fail("artifact missing independent-state control")
    if c1.get("majority_equals_single") is not True:
        return fail("artifact missing identical-state control")

    # Same-model copies: plurality mixture at gamma=1 equals single error.
    mix_id = C.mixture_plurality_error(n, p, 1.0)
    if abs(mix_id - single) > 1e-12:
        return fail(f"gamma=1 plurality {mix_id} != single {single}")
    mix_block = block.get("plurality_shared_draw_mixture") or {}
    if abs(float(mix_block.get("identical_copies_error")) - mix_id) > 1e-9:
        return fail("artifact identical-copies plurality error drift")

    g = C.kim_gamma_helm()
    if abs(g - 0.4) > 1e-9:
        return fail(f"Kim 0.60 map is gamma={g} not 0.40")
    fig = doc.get("correlation_figure") or {}
    if abs(float(fig.get("mapped_gamma")) - g) > 1e-9:
        return fail("artifact mapped_gamma drift")

    verdict = doc.get("voting_rule_verdict") or {}
    if verdict.get("majority_style_defensible_for_same_model") is not False:
        return fail("same-model majority still marked defensible")

    payload = {
        "pass": True,
        "probe": "probe2-majority-curve",
        "unit_id": "RES-0078",
        "n": n,
        "p": p,
        "n_points": len(points),
        "rho0_majority_error": round(e0, 12),
        "rho1_majority_error": round(e1, 12),
        "single_error": round(single, 12),
        "mapped_gamma": g,
        "both_states": True,
        "computed_not_asserted": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"rho0={e0:.4f}<{single:.4f} rho1={e1:.4f}=={single:.4f} "
        f"gamma={g} points={len(points)}"
    )
    print("SUCCESS:RES-0078-probe2 majority error-vs-correlation curve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
