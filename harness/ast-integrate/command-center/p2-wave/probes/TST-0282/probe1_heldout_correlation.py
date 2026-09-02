#!/usr/bin/env python3
"""Probe 1: held-out Spearman correlation of completeness_score vs rubric labels.

Mechanically: score every held-out gold case with tools/council/completeness.py
(which must not read human_label), then Spearman + bootstrap percentile CI.
Does not run the padding/complete both-states (probe 2).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import evaluate as E  # noqa: E402
import gold as G  # noqa: E402
import stats as ST  # noqa: E402

ART = REPO / "command-center/receipts/TST-0282.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0282-probe1 {msg}")
    return 1


def check_artifact() -> str | None:
    if not ART.is_file():
        return None
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0282" not in text:
        return "artifact sentinel absent"
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"artifact self-declared {st}"
    heading = str(doc.get("heading") or doc.get("receipt_heading") or "")
    validated = bool((doc.get("validation") or {}).get("validated"))
    if validated and heading.startswith("UNVERIFIED"):
        return "validated=true but heading UNVERIFIED"
    if (not validated) and heading.startswith("VERIFIED") and "UNVERIFIED" not in heading:
        return "validated=false but heading claims VERIFIED"
    return None


def main() -> int:
    art_err = check_artifact()
    if art_err:
        return fail(art_err)
    if not E.scorer_ignores_labels():
        return fail("scorer source mentions human_label/rubric (not blind)")

    cases = G.all_cases()
    if any("human_label" not in c for c in cases):
        return fail("gold case missing human_label")
    rows = E.per_case_rows(cases)
    held = E.heldout_rows(rows)
    if len(held) < E.MIN_HELDOUT_N:
        return fail(f"held-out n={len(held)} < {E.MIN_HELDOUT_N}")

    corr = E.correlation_report(rows)
    rho = corr["spearman_rho"]
    if rho != rho:
        return fail("Spearman is NaN")
    if corr["n_distinct_scores"] < 3:
        return fail("held-out scores are not diverse (vacuous constant scorer)")
    if corr["n_distinct_labels"] < 3:
        return fail("held-out labels are not diverse")
    boot = corr["bootstrap_ci95"]
    if boot[0] != boot[0] or boot[1] != boot[1]:
        return fail("bootstrap CI is NaN")
    if boot[0] > rho or rho > boot[1]:
        return fail("point estimate outside bootstrap CI")

    xs = [float(r["score"]) for r in held]
    ys = [float(r["human_label"]) for r in held]
    rho2 = ST.spearman(xs, ys)
    if abs(rho2 - rho) > 1e-12:
        return fail("live Spearman disagrees with report")

    summary = {
        "pass": True,
        "probe": "probe1-heldout-correlation",
        "unit_id": "TST-0282",
        "n_heldout": corr["n_heldout"],
        "spearman_rho": rho,
        "bootstrap_ci95": boot,
        "validated": corr["validated"],
        "n_distinct_scores": corr["n_distinct_scores"],
        "n_distinct_labels": corr["n_distinct_labels"],
        "pairs": corr["pairs"],
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"heldout n={corr['n_heldout']} spearman={rho:.4f} "
        f"bootstrap=[{boot[0]:.4f},{boot[1]:.4f}] validated={corr['validated']}"
    )
    print("SUCCESS:TST-0282-probe1 held-out Spearman with bootstrap interval")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
