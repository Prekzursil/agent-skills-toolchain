#!/usr/bin/env python3
"""Probe 2: statistics-mandate reviewer + de-anonymisation control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import deanonymise as D  # noqa: E402
import experiment as E  # noqa: E402
import stats as S  # noqa: E402

ART = REPO / "command-center/receipts/TST-0289.json"
UID = "TST-0289"
TOL = 1e-12


def fail(msg: str) -> int:
    print(f"FAILED:TST-0289-probe2 {msg}")
    return 1


def close(a: float, b: float, tol: float = TOL) -> bool:
    return abs(float(a) - float(b)) <= tol


def main() -> int:
    if not ART.is_file():
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:TST-0289" not in text:
        return fail("sentinel-absent")

    cases = doc.get("per_case") or []
    if len(cases) < 20:
        return fail(f"per_case n={len(cases)} < 20")

    live_ind: list[float] = []
    live_pull: list[float] = []
    live_dis: list[float] = []
    concealed_items: list[tuple[str, str]] = []
    for row in cases:
        r_vecs = row["revealed"]["vectors"]
        c_vecs = row["concealed"]["vectors"]
        r_pair = E.pairwise_from_vectors(r_vecs)
        c_pair = E.pairwise_from_vectors(c_vecs)
        if not close(r_pair, row["revealed"]["pairwise_mean"]):
            return fail(f"seed {row['seed']} revealed pairwise recount mismatch")
        if not close(c_pair, row["concealed"]["pairwise_mean"]):
            return fail(f"seed {row['seed']} concealed pairwise recount mismatch")
        ind = c_pair - r_pair
        if not close(ind, row["independence_delta"]):
            return fail(f"seed {row['seed']} independence_delta mismatch")
        pull = float(row["revealed"]["pull_mean"]) - float(row["concealed"]["pull_mean"])
        if not close(pull, row["pull_delta"]):
            return fail(f"seed {row['seed']} pull_delta mismatch")
        live_ind.append(ind)
        live_pull.append(pull)
        live_dis.append(1.0 if row["verdict_disagree"] else 0.0)
        for opening_text, sid in zip(
            row["concealed"]["texts"], row["concealed"]["seat_ids"]
        ):
            concealed_items.append((opening_text, sid))

    boot_ind = S.bootstrap_mean_ci(live_ind)
    boot_pull = S.bootstrap_mean_ci(live_pull)
    boot_dis = S.bootstrap_mean_ci(live_dis)
    norm_ind = S.normal_mean_ci(live_ind)
    dz_ind = S.cohens_dz(live_ind)
    dz_pull = S.cohens_dz(live_pull)

    reported_ind = doc["independence_delta"]
    reported_pull = doc["pull_delta"]
    reported_dis = doc["verdict_disagree_rate"]
    if not close(boot_ind["mean"], reported_ind["mean"]):
        return fail("independence mean not reproduced")
    if not close(boot_ind["lo"], reported_ind["lo"]) or not close(
        boot_ind["hi"], reported_ind["hi"]
    ):
        return fail("independence bootstrap interval not reproduced")
    if not close(boot_pull["mean"], reported_pull["mean"]):
        return fail("pull mean not reproduced")
    if not close(boot_dis["mean"], reported_dis["mean"]):
        return fail("disagree rate not reproduced")
    if doc.get("independence_cohens_dz") is not None and dz_ind is not None:
        if not close(float(doc["independence_cohens_dz"]), float(dz_ind), 1e-9):
            return fail("independence Cohen dz not reproduced")
    if doc.get("pull_cohens_dz") is not None and dz_pull is not None:
        if not close(float(doc["pull_cohens_dz"]), float(dz_pull), 1e-9):
            return fail("pull Cohen dz not reproduced")

    if S.ci_excludes_zero(boot_ind) != S.ci_excludes_zero(norm_ind):
        return fail("bootstrap vs normal CI disagree on independence zero-exclusion")
    if not close(norm_ind["mean"], boot_ind["mean"]):
        return fail("Welford/normal mean diverged from bootstrap mean")

    live = E.run_experiment()
    for seed in (cases[0]["seed"], cases[-1]["seed"]):
        live_row = next(r for r in live["rows"] if r["seed"] == seed)
        rec_row = next(r for r in cases if r["seed"] == seed)
        if live_row["revealed"]["hash"] != rec_row["revealed"]["hash"]:
            return fail(f"seed {seed} revealed hash drifted from receipt")
        if live_row["concealed"]["hash"] != rec_row["concealed"]["hash"]:
            return fail(f"seed {seed} concealed hash drifted from receipt")

    personas = live["personas"]
    de_con = D.accuracy(concealed_items, personas)
    planted = D.accuracy(D.plant_traces(concealed_items), personas)
    de_rev = live["deanonymisation"]["revealed"]
    de_cer = live["deanonymisation"]["ceremony_mask_only"]

    if de_con["above_chance"]:
        return fail(
            f"concealed re-id accuracy {de_con['accuracy']} beats chance; "
            "anonymity is nominal"
        )
    if planted["accuracy"] < 1.0 - 1e-12 or not planted["above_chance"]:
        return fail("planted-trace negative control did not re-identify; check is vacuous")
    if not de_rev["above_chance"]:
        return fail("revealed-style classifier is vacuous (cannot identify when cues exist)")
    if not de_cer["above_chance"]:
        return fail("ceremony mask-only still should leak style/tool traces")

    print(
        json.dumps(
            {
                "probe": "probe2-reviewer-stats-deanonymisation",
                "unit_id": UID,
                "n": len(cases),
                "reproduced_independence_mean": boot_ind["mean"],
                "reproduced_independence_ci": [boot_ind["lo"], boot_ind["hi"]],
                "independent_normal_ci": [norm_ind["lo"], norm_ind["hi"]],
                "reproduced_cohens_dz": dz_ind,
                "zero_exclusion_agrees": S.ci_excludes_zero(boot_ind)
                == S.ci_excludes_zero(norm_ind),
                "deanonymisation_concealed": de_con,
                "deanonymisation_planted": planted,
                "deanonymisation_revealed": {
                    "accuracy": de_rev["accuracy"],
                    "above_chance": de_rev["above_chance"],
                },
                "pass": True,
            },
            indent=2,
            sort_keys=True,
        )
    )
    print(
        f"reproduced_mean={boot_ind['mean']:.6f} "
        f"ci=[{boot_ind['lo']:.6f},{boot_ind['hi']:.6f}] "
        f"dz={dz_ind} concealed_acc={de_con['accuracy']:.4f} "
        f"planted_acc={planted['accuracy']:.4f}"
    )
    print("SUCCESS:TST-0289-probe2 reviewer reproduced effect size and interval")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
