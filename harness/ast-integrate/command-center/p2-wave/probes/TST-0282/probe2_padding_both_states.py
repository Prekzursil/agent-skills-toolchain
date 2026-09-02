#!/usr/bin/env python3
"""Probe 2: padding / both-states plus independent Fisher-z reproduction.

Mechanically different from probe 1: does not compute a bootstrap interval.
Re-scores raw held-out pairs and reports Spearman + Fisher z CI. Also requires
the padded fixture stay below 0.90 and the complete fixture reach it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

import evaluate as E  # noqa: E402
import gold as G  # noqa: E402
import stats as ST  # noqa: E402
from council.completeness import THRESHOLD, score_output  # noqa: E402

ART = REPO / "command-center/receipts/TST-0282.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0282-probe2 {msg}")
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
    reported = (doc.get("validation") or {}).get("spearman_rho")
    return None if reported is None else "ok"


def main() -> int:
    art_note = check_artifact()
    if art_note not in {None, "ok"}:
        return fail(art_note)

    rows = E.per_case_rows()
    states = E.both_states(rows)
    if not states["padded_below_threshold"]:
        return fail(
            f"padded score {states['padded_score']} reached {THRESHOLD}"
        )
    if not states["complete_reaches_threshold"]:
        return fail(
            f"complete score {states['complete_score']} below {THRESHOLD} (unreachable gate)"
        )
    if not states["padding_is_heavier"]:
        return fail("padded fixture is not heavier than complete (padding not load-bearing)")
    if not states["extra_padding_still_complete"]:
        return fail("extra undeclared padding punished a complete output")

    empty = E.empty_objective_control()
    if not empty["unverified"] or empty["gate_fires"]:
        return fail("empty objective must be NOT-CHECKED and must not fire the gate")

    drop_cites = G.make_output(
        sq_ids=[s[0] for s in G.SUBQUESTIONS],
        categories=G.CATEGORIES,
        evidence_classes=G.EVIDENCE_CLASSES,
        uncited_evidence=True,
    )
    dropped = score_output(G.default_objective(), drop_cites)
    if dropped["score"] is None or dropped["score"] >= THRESHOLD:
        return fail("dropping evidence cites still reached 0.90")

    held = E.heldout_rows(rows)
    xs = [float(r["score"]) for r in held]
    ys = [float(r["human_label"]) for r in held]
    rho = ST.spearman(xs, ys)
    fish_lo, fish_hi = ST.fisher_z_ci(rho, len(held))
    if rho != rho or fish_lo != fish_lo:
        return fail("Fisher-z reproduction produced NaN")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        reported = (doc.get("validation") or {}).get("spearman_rho")
        if reported is None:
            return fail("receipt missing validation.spearman_rho")
        if abs(float(reported) - rho) > 1e-9:
            return fail(
                f"reviewer Spearman {rho} != receipt {reported}"
            )

    corr = E.correlation_report(rows)
    length_rho = corr["word_count_spearman_rho"]
    if length_rho == length_rho and rho == rho and length_rho > rho:
        return fail(
            f"word-count Spearman {length_rho} exceeds score Spearman {rho} "
            "(verbosity proxy)"
        )

    summary = {
        "pass": True,
        "probe": "probe2-padding-both-states-fisher",
        "unit_id": "TST-0282",
        "padded_score": states["padded_score"],
        "complete_score": states["complete_score"],
        "threshold": THRESHOLD,
        "padded_below_threshold": True,
        "complete_reaches_threshold": True,
        "padding_word_count": states["padded_word_count"],
        "complete_word_count": states["complete_word_count"],
        "uncited_complete_score": dropped["score"],
        "empty_objective_unverified": empty["unverified"],
        "reviewer_spearman_rho": rho,
        "fisher_z_ci95": [fish_lo, fish_hi],
        "word_count_spearman_rho": length_rho,
        "n_heldout": len(held),
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"padded={states['padded_score']:.4f}<{THRESHOLD} "
        f"complete={states['complete_score']:.4f}>={THRESHOLD} "
        f"fisher_rho={rho:.4f} ci=[{fish_lo:.4f},{fish_hi:.4f}]"
    )
    print("SUCCESS:TST-0282-probe2 padding both-states and Fisher-z reproduction")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
