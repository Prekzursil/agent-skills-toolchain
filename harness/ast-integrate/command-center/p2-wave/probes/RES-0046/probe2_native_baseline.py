#!/usr/bin/env python3
"""Probe 2: native deferred-tool is the baseline, not doing-nothing."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import catalog as C  # noqa: E402

OUT = REPO / "command-center/research/RES-0046.json"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0046-probe2 {msg}")
    return 1


def main() -> int:
    if not OUT.is_file() or OUT.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    if not C.baseline_is_native(doc):
        return fail(
            f"comparison_baseline={doc.get('comparison_baseline')} "
            f"expected={C.BASELINE_ID}"
        )
    if str(doc.get("comparison_baseline_not") or "") != "doing-nothing":
        return fail("control marker comparison_baseline_not missing")
    mutant = C.mutant_doing_nothing(doc)
    if C.baseline_is_native(mutant):
        return fail("negative control collapsed: doing-nothing still counts as native")
    table = doc.get("candidate_table") or []
    beaters = [
        r.get("id")
        for r in table
        if r.get("beats_native_lazy_activation") is True
    ]
    if beaters:
        return fail(f"lazy-activation beaters vs native: {beaters}")
    if doc.get("any_candidate_beats_native_lazy_activation") is not False:
        return fail("summary flag any_candidate_beats_native_lazy_activation not false")
    tier = doc.get("tier2_grade_under_test") or {}
    verdict = str(tier.get("verdict") or "").upper()
    if verdict not in {"CORROBORATE", "REFUTE"}:
        return fail(f"tier2 verdict not corroborate-or-refute: {verdict}")
    if str(tier.get("not") or "").upper() != "RESTATE":
        return fail("tier2 must explicitly disclaim RESTATE")
    if C.TIER2_PRESCRIPTION not in json.dumps(tier):
        return fail("tier2 prescription missing")
    baseline_rows = [r for r in table if r.get("is_baseline") is True]
    if [r.get("id") for r in baseline_rows] != [C.BASELINE_ID]:
        return fail("is_baseline must be exactly the native row")
    # Doing-nothing would score a daemon gateway as a win because it beats idle.
    # The live record must refuse that scoring by keeping the native row as baseline.
    idle_win = [
        r.get("id")
        for r in table
        if r.get("requires_persistent_daemon") is True
        and r.get("solves_session_server_multiplication") is True
    ]
    if not idle_win:
        return fail("control set empty; cannot show doing-nothing would mislead")
    report = {
        "pass": True,
        "probe": "probe2-native-baseline",
        "unit_id": "RES-0046",
        "comparison_baseline": doc.get("comparison_baseline"),
        "mutant_rejected": True,
        "tier2_verdict": verdict,
        "idle_would_mislead_on": idle_win,
        "lazy_activation_beaters": beaters,
        "reviewer_id": "RES-0046-probe2-native-baseline",
        "independent": True,
    }
    print(json.dumps(report, sort_keys=True))
    print(
        f"baseline={C.BASELINE_ID} mutant_rejected=True "
        f"tier2={verdict} idle_mislead={idle_win}"
    )
    print("SUCCESS:RES-0046-probe2 native baseline not doing-nothing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
