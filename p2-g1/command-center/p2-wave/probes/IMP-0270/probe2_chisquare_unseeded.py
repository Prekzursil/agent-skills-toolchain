"""IMP-0270 probe 2: stratified proportions hold; unseeded runs are not
reproducible; under-fill is refused loudly.

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0270/probe2_chisquare_unseeded.py
Exit 0 iff, on the live select_random module: over 1000 stratified draws the
seat-stratum census matches quotas*n_draws exactly (chi-square 0.0); the
uniform sampler's stratum distribution DEVIATES from the same quotas
(chi-square above the df=2 p<0.05 threshold 5.99, so the stratifier is doing
real work); two independent unseeded runs differ (unseeded reproducibility
check fires); and a quota exceeding its stratum raises SamplingError.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools" / "council" / "participants"))
from select_random import (  # noqa: E402
    SamplingError,
    accumulate_stratum_counts,
    chi_square_gof,
    select_stratified,
    select_uniform,
    stratum_expected_from_quotas,
)

N_DRAWS = 1000
SEED = 20260824
pool = (
    [{"id": f"anthropic-{i:02d}", "vendor": "anthropic"} for i in range(10)]
    + [{"id": f"google-{i:02d}", "vendor": "google"} for i in range(6)]
    + [{"id": f"openai-{i:02d}", "vendor": "openai"} for i in range(4)]
)
quotas = {"anthropic": 2, "google": 2, "openai": 2}

strat_runs = [
    select_stratified(pool, quotas, seed=SEED + i) for i in range(N_DRAWS)
]
strat_obs = accumulate_stratum_counts(strat_runs)
strat_exp = stratum_expected_from_quotas(quotas, N_DRAWS)
strat_chi = chi_square_gof(strat_obs, strat_exp)

unif_runs = [select_uniform(pool, 6, seed=SEED + i) for i in range(N_DRAWS)]
unif_obs = accumulate_stratum_counts(unif_runs)
unif_exp = stratum_expected_from_quotas(quotas, N_DRAWS)
unif_chi = chi_square_gof(unif_obs, unif_exp)

a = select_uniform(pool, 6, seed=None)
b = select_uniform(pool, 6, seed=None)
underfill_refused = False
try:
    select_stratified(pool, {"anthropic": 11, "google": 2, "openai": 2}, seed=1)
except SamplingError:
    underfill_refused = True

checks = {
    "stratified_proportions_match": bool(strat_chi["proportions_match"]),
    "stratified_chi_square_zero": strat_chi["chi_square"] == 0.0,
    "uniform_chi_square_rejects": unif_chi["chi_square"] > 5.99,
    "unseeded_runs_differ": not (
        list(a["roster_ids"]) == list(b["roster_ids"])
    ),
    "unseeded_seeds_recorded": a["seed_source"] == "fresh-entropy" and b["seed_source"] == "fresh-entropy",
    "underfill_refused": underfill_refused,
}
ok = all(checks.values())
out = {"probe": "probe2-chisquare-unseeded", "unit_id": "IMP-0270",
       "n_draws": N_DRAWS,
       "stratified_observed": strat_obs,
       "stratified_expected": strat_exp,
       "stratified_chi_square": strat_chi["chi_square"],
       "uniform_observed": unif_obs,
       "uniform_chi_square": unif_chi["chi_square"],
       "checks": checks, "pass": ok}
print(json.dumps(out, sort_keys=True))
RAW = Path(__file__).resolve().parent / "probe2-chisquare.raw.json"
RAW.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
if not ok:
    print("FAILED:IMP-0270-probe2 %s" % [k for k, v in checks.items() if not v])
    raise SystemExit(1)
print("SUCCESS:IMP-0270-probe2 stratified quotas hold over 1000 draws; uniform deviates; under-fill refused")
