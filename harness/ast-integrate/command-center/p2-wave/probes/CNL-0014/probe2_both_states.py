#!/usr/bin/env python3
"""Probe 2: both-states control — fires on planted-average, silent on known-good."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import detector as D  # noqa: E402
import fixtures as F  # noqa: E402
import scenario as Sc  # noqa: E402
import selector as Sel  # noqa: E402

ART = (
    REPO
    / "command-center/design/council/CNL-0014-calibration-ranked-selection-needs-a-calibration-store-tha.md"
)
SENTINEL = "SUCCESS:CNL-0014"


def main() -> int:
    m = Sc.run_all()
    mixed_store = F.mixed_store()
    honest = Sel.rank_calibration(mixed_store, F.COLD_CANDIDATES)
    bad = Sel.rank_with_average_imputation(mixed_store, F.COLD_CANDIDATES)
    both = D.both_states(mixed_store, honest, bad)
    line = D.verbatim_line("both-states-mixed", both)
    print(line)
    print(
        f"planted_bad_codes={sorted({f['code'] for f in both['planted_bad_findings']})}"
    )
    print(f"cara_beats_bob_under_imputation={m['mixed']['cara_beats_bob_under_imputation']}")
    print(f"imputed_average={m['mixed']['imputed_average']}")
    print(f"imputed_ranked_ids={m['mixed']['imputed_ranked_ids']}")
    print(f"imputed_overlap={m['mixed']['imputed_overlap']}")

    cold_store = F.cold_start_store()
    cold_honest = Sel.rank_calibration(cold_store, F.COLD_CANDIDATES)
    cold_bad = Sel.rank_with_average_imputation(cold_store, F.COLD_CANDIDATES)
    both_cold = D.both_states(cold_store, cold_honest, cold_bad)
    print(D.verbatim_line("both-states-cold", both_cold))
    print(f"cold_impute_source={cold_bad.get('impute_source')} value={cold_bad.get('imputed_average')}")

    repaired = {
        "method": "calibration-rank",
        "ranked": [row for row in bad["ranked"] if row["resolved_n"] >= mixed_store["min_resolved_n"]],
        "unrankable": [],
    }
    repaired_fires = D.fires(mixed_store, repaired)
    print(f"repaired_zero_history_removed_fires={repaired_fires}")

    v = m["store_validation"]
    print(
        f"store-gate known_good_accepted={v['known_good_accepted']} "
        f"planted_invented_rejected={v['planted_invented_rejected']} "
        f"invented_errors={v['planted_invented_errors']}"
    )

    checks = [
        ("discriminates_mixed", both["discriminates"]),
        ("silent_on_good", both["silent_on_good"]),
        ("fires_on_bad", both["fires_on_bad"]),
        ("discriminates_cold", both_cold["discriminates"]),
        ("cara_outRanks_bob_when_imputed", m["mixed"]["cara_beats_bob_under_imputation"]),
        ("repair_silences", repaired_fires is False),
        ("store_gate", Sc.store_gate_ok(m)),
        ("both_ok", Sc.both_ok(m)),
    ]
    failed = False
    for name, ok in checks:
        print(f"{name}={ok}")
        if not ok:
            failed = True

    if not ART.is_file():
        print("FAILED:CNL-0014-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        print("FAILED:CNL-0014-probe2 sentinel-absent")
        return 1
    rec = doc.get("both_states") or {}
    if rec.get("discriminates") is not True:
        print("FAILED:CNL-0014-probe2 artifact both_states.discriminates is not true")
        return 1
    if rec.get("on_known_good") != "SILENT" or rec.get("on_planted_bad") != "FIRES":
        print(f"FAILED:CNL-0014-probe2 artifact both_states labels {rec}")
        return 1
    nc = doc.get("negative_controls") or []
    if not nc:
        print("FAILED:CNL-0014-probe2 negative_controls missing")
        return 1
    if nc[0].get("on_planted_bad") != "FIRES" or nc[0].get("on_known_good") != "SILENT":
        print("FAILED:CNL-0014-probe2 negative control did not record both states")
        return 1

    if failed:
        print("FAILED:CNL-0014-probe2 both-states control did not discriminate")
        return 1
    print("SUCCESS:CNL-0014-probe2 both-states fires on planted-average, silent on known-good")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
