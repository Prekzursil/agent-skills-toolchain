#!/usr/bin/env python3
"""Probe 1: P0/P1 early-stop must be refused; n never exceeds fixed-n."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center" / "sampling"))
import curtailed_sprt as CS  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0141.json"
FRAME = HERE / "fixtures/frozen_frame.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0141-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("receipt missing")
    raw = ART.read_text(encoding="utf-8")
    if "SUCCESS:CNF-0141" not in raw:
        return fail("sentinel absent")
    doc = json.loads(raw)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    params = CS.default_params()
    p0 = CS.CurtailedSPRT(params, severity="P0", population_n=40, stratum_id="S-P0")
    try:
        p0.try_declare_stop("ACCEPT_H0")
        return fail("P0 try_declare_stop was not refused")
    except CS.CensusGuardError:
        pass
    try:
        CS.CurtailedSPRT(
            params,
            severity="P0",
            population_n=40,
            allow_early_stop=True,
            stratum_id="S-P0-ctor",
        )
        return fail("P0 allow_early_stop=True was not refused")
    except CS.CensusGuardError:
        pass
    try:
        CS.CurtailedSPRT(
            params, severity="P1", population_n=25, n_max=5, stratum_id="S-P1"
        )
        return fail("P1 n_max < N was not refused")
    except CS.CensusGuardError:
        pass

    p0b = CS.CurtailedSPRT(params, severity="P0", population_n=40, stratum_id="S-P0-stream")
    st = p0b.consume([True] * 40)
    if st.n != 40:
        return fail(f"P0 census stopped at n={st.n}, want 40")
    if st.decision == "CONTINUE":
        return fail("P0 census ended in CONTINUE")
    if st.truncated:
        return fail("P0 census must not report sequential truncation")

    p1 = CS.CurtailedSPRT(params, severity="P1", population_n=25, stratum_id="S-P1-stream")
    st1 = p1.consume([False] * 25)
    if st1.n != 25:
        return fail(f"P1 census stopped at n={st1.n}, want 25")

    try:
        CS.normalize_severity("")
        return fail("empty severity defaulted")
    except ValueError:
        pass
    try:
        CS.normalize_severity("LOW")
        return fail("unknown severity defaulted to low")
    except ValueError:
        pass

    path = CS.make_continuation_path(params)
    if len(path) != params.n_max:
        return fail(f"continuation length {len(path)} != n_max {params.n_max}")
    seq = CS.CurtailedSPRT(params, severity="P2", population_n=10**6)
    stc = seq.consume(path)
    if stc.n != params.n_max:
        return fail(f"borderline n={stc.n} want n_max={params.n_max}")
    if not stc.truncated:
        return fail("borderline did not truncate at n_max")
    try:
        seq.observe(True)
        return fail("observe after close did not raise")
    except CS.SequentialClosedError:
        pass

    over = CS.CurtailedSPRT(params, severity="P2", population_n=10**6)
    st_over = over.consume([False] * (params.n_max + 500))
    if st_over.n > params.n_max:
        return fail(f"n={st_over.n} exceeded n_max={params.n_max}")

    frame = json.loads(FRAME.read_text(encoding="utf-8"))
    plan = CS.apply_plan(frame, params)
    if plan["census_shrunk"]:
        return fail("plan shrunk the P0/P1 census")
    if plan["census_n_required"] != 65:
        return fail(f"census_n_required={plan['census_n_required']} want 65")
    if any(s["early_stop_allowed"] for s in plan["strata"] if s["mode"] == "CENSUS"):
        return fail("census stratum marked early_stop_allowed")

    cited = (doc.get("guard") or {}).get("path_line") or ""
    live = CS.guard_path_line()
    if cited != live:
        return fail(f"guard path_line {cited!r} != live {live!r}")

    print(
        json.dumps(
            {
                "probe": "probe1-guard-and-bound",
                "unit_id": "CNF-0141",
                "p0_n": st.n,
                "p1_n": st1.n,
                "n_max": params.n_max,
                "borderline_truncated": stc.truncated,
                "census_n": plan["census_n_required"],
                "guard": live,
                "pass": True,
            }
        )
    )
    print("SUCCESS:CNF-0141-probe1 census guard and fixed-n bound")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
