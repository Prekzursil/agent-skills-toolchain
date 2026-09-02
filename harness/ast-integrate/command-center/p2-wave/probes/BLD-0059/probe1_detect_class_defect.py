#!/usr/bin/env python3
"""Probe 1: sampling scheme detects an injected class-wide defect at claimed confidence.

Also rejects a scheme that would pass a 20%-defective class. Recomputes against
the live receipt so a stale n* cannot hide.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import params as P  # noqa: E402
import power as PW  # noqa: E402
import simulate as S  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0059.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:BLD-0059-probe1 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "BLD-0059":
        print("FAILED:BLD-0059-probe1 unit_id", doc.get("unit_id"))
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:BLD-0059-probe1 self-declared", doc.get("state"))
        return 1
    if P.SENTINEL not in ART.read_text(encoding="utf-8"):
        print("FAILED:BLD-0059-probe1 sentinel absent")
        return 1

    n_star = PW.min_sample_size(P.DESIGN_PREVALENCE, P.CLAIMED_CONFIDENCE)
    claimed = PW.scheme_accepted(n_star, P.DESIGN_PREVALENCE, P.CLAIMED_CONFIDENCE)
    weak = PW.scheme_accepted(P.WEAK_SCHEME_N, P.DESIGN_PREVALENCE, P.CLAIMED_CONFIDENCE)
    print(
        f"n*={n_star} det={claimed['detection_probability']:.6f} "
        f"accepted={claimed['accepted']}"
    )
    print(
        f"weak_n={P.WEAK_SCHEME_N} det={weak['detection_probability']:.6f} "
        f"accepted={weak['accepted']} pass_defective={weak['probability_pass_defective_class']:.4f}"
    )
    if n_star != 14:
        print(f"FAILED:BLD-0059-probe1 n*={n_star} want=14")
        return 1
    if not claimed["accepted"]:
        print("FAILED:BLD-0059-probe1 claimed scheme not accepted")
        return 1
    if weak["accepted"]:
        print("FAILED:BLD-0059-probe1 weak scheme was not rejected")
        return 1
    if weak["probability_pass_defective_class"] < 0.4:
        print("FAILED:BLD-0059-probe1 weak scheme is not actually weak")
        return 1

    rec_n = int((doc.get("sampling") or {}).get("n_per_stratum") or 0)
    if rec_n != n_star:
        print(f"FAILED:BLD-0059-probe1 receipt n={rec_n} live n={n_star}")
        return 1
    if (doc.get("sampling") or {}).get("acceptance_criterion", {}).get("weak_n3_scheme", {}).get(
        "accepted"
    ) is not False:
        print("FAILED:BLD-0059-probe1 receipt did not reject n=3")
        return 1

    mc = S.monte_carlo_detection(
        class_size=P.HYPERGEOMETRIC_N_10X,
        prevalence=P.DESIGN_PREVALENCE,
        n_sample=n_star,
        theta=P.ESCALATION_THRESHOLD,
        trials=P.MC_TRIALS,
        seed=P.MC_SEED,
    )
    print(
        f"mc empirical={mc['empirical_detection']:.4f} "
        f"hypergeometric={mc['hypergeometric_detection']:.4f} "
        f"binomial={mc['binomial_detection']:.4f}"
    )
    if mc["empirical_detection"] < P.CLAIMED_CONFIDENCE - 0.03:
        print("FAILED:BLD-0059-probe1 MC detection below claimed confidence")
        return 1
    if mc["binomial_detection"] < P.CLAIMED_CONFIDENCE:
        print("FAILED:BLD-0059-probe1 binomial detection below claim")
        return 1
    if mc["hypergeometric_detection"] < P.CLAIMED_CONFIDENCE:
        print("FAILED:BLD-0059-probe1 hypergeometric detection below claim")
        return 1

    n_half = PW.min_sample_size(P.DESIGN_PREVALENCE / 2.0, P.CLAIMED_CONFIDENCE)
    print(f"sensitivity n(p=0.20)={n_star} n(p=0.10)={n_half}")
    if n_half <= n_star:
        print("FAILED:BLD-0059-probe1 halving p did not increase n")
        return 1

    print("SUCCESS:BLD-0059-probe1 class-wide defect detection and weak-scheme rejection")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
