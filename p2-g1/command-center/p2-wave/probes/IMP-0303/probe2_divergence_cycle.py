"""IMP-0303 probe 2: divergence is surfaced, never silently resolved.

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0303/probe2_divergence_cycle.py
Exit 0 iff the live evaluate_all: on the Tennessee ballots (four different
winners) it reports divergent=True, binding_winner=None and
owner_action=SURFACE_DIVERGENCE; on the constructed Condorcet cycle it
reports cycle_reported=True and still surfaces (never a default winner);
hides_divergence is False for both live reports; the binding-default MUTANT
sets a binding winner on a divergent report and is therefore caught by
hides_divergence (fired_on_bad) while the agreeing ballot set is reported
RECORD_AGREEMENT with hides_divergence False (silent_on_good).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools" / "council" / "vote"))
import ballots as B  # noqa: E402

fx = B.textbook_fixtures()

tn_report = B.evaluate_all(fx["tennessee-capital"].ballots, fx["tennessee-capital"].candidates)
cycle_report = B.evaluate_all(fx["condorcet-cycle-unequal"].ballots, fx["condorcet-cycle-unequal"].candidates)
pairwise_cycle = cycle_report.by_method["pairwise-condorcet"]

agree_ballots = B._copies(("A", "B", "C"), 9)
agree_report = B.evaluate_all(agree_ballots, ["A", "B", "C"])

mutant = B.mutant_silent_default(tn_report, "ranked-choice")

checks = {
    "tennessee_divergent_surfaced": tn_report.divergent is True
    and tn_report.binding_winner is None
    and tn_report.owner_action == "SURFACE_DIVERGENCE",
    "tennessee_winner_set": sorted(set(tn_report.winners_by_method.values())) == ["Knoxville", "Nashville"],
    "cycle_reported": pairwise_cycle.status == "CONDORCET_CYCLE" and cycle_report.cycle_reported is True,
    "cycle_surfaced": cycle_report.divergent is True
    and cycle_report.binding_winner is None
    and cycle_report.owner_action == "SURFACE_DIVERGENCE",
    "live_reports_never_hide": B.hides_divergence(tn_report) is False
    and B.hides_divergence(cycle_report) is False,
    "mutant_fires_hides_divergence": mutant.binding_winner is not None
    and B.hides_divergence(mutant) is True,
    "agreeing_set_records_agreement": agree_report.divergent is False
    and agree_report.owner_action == "RECORD_AGREEMENT"
    and B.hides_divergence(agree_report) is False,
}
both_states = {
    "fired_on_bad": B.hides_divergence(mutant) is True,
    "silent_on_good": B.hides_divergence(tn_report) is False and B.hides_divergence(agree_report) is False,
}
ok = all(checks.values())
out = {"probe": "probe2-divergence-cycle", "unit_id": "IMP-0303",
       "tennessee_owner_action": tn_report.owner_action,
       "tennessee_binding": tn_report.binding_winner,
       "cycle_status": pairwise_cycle.status,
       "cycle_binding": cycle_report.binding_winner,
       "mutant_binding": mutant.binding_winner,
       "both_states": both_states,
       "checks": checks, "pass": ok}
print(json.dumps(out, sort_keys=True))
RAW = Path(__file__).resolve().parent / "probe2-divergence.raw.json"
RAW.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
if not ok:
    print("FAILED:IMP-0303-probe2 %s" % [k for k, v in checks.items() if not v])
    raise SystemExit(1)
print("SUCCESS:IMP-0303-probe2 divergence surfaced (binding null); Condorcet cycle reported; binding-default mutant caught")
