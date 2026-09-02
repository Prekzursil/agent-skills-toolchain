#!/usr/bin/env python3
"""Probe 2: independent flatten recount, paper lineage, IMP-0187, honesty mutant."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import measure as M  # noqa: E402
import papers as P  # noqa: E402
from contract import OUT_REL, SENTINEL  # noqa: E402

ART = REPO / OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:RES-0165-probe2 {msg}")
    return 1


def reviewer_flatten(rows: list[dict], *, floor: int = 0, persist: int = 2, min_n: int = 2) -> int | None:
    """BFS-style recount: scan the curve; do not call curve.flatten_n."""
    if len(rows) < persist:
        return None
    for i in range(len(rows)):
        n = int(rows[i]["n"])
        if n < min_n:
            continue
        window = rows[i - persist + 1 : i + 1]
        if len(window) < persist:
            continue
        if any(int(w["n"]) < min_n for w in window):
            continue
        if all(int(w["marginal_unique"]) <= floor for w in window):
            return n
    return None


def main() -> int:
    live = M.run()
    land_n = reviewer_flatten(live["landscape"]["author_curve"])
    targ_n = reviewer_flatten(live["targeted"]["author_curve"])
    pub = P.extract()
    monkeys = pub["papers"]["llm-monkeys"]["compute_matched"]
    ensemble = live["estate_ensemble"]
    floor = live["noise_floor"]

    agree = (
        floor["author_reviewer_agree"]
        and land_n == live["flatten"]["landscape_n"]
        and targ_n == live["flatten"]["targeted_n"]
    )

    print(
        json.dumps(
            {
                "reviewer_landscape_n": land_n,
                "reviewer_targeted_n": targ_n,
                "author_landscape_n": live["flatten"]["landscape_n"],
                "author_targeted_n": live["flatten"]["targeted_n"],
                "agree": agree,
                "monkeys_first_over_later": monkeys["first_sample_over_later_mean"],
                "monkeys_delta_pp": monkeys["coverage_delta_pp"],
                "correlated_verdict": ensemble["correlated"]["independence"],
                "correlated_n": ensemble["correlated"]["n_agents"],
                "correlated_unique_hashes": ensemble["correlated"]["unique_output_hashes"],
                "honesty_live": "ok" if floor["clustered_added"] == 0 else "clone-counted",
            },
            sort_keys=True,
        )
    )

    if not agree:
        return fail("reviewer flatten disagrees with author")
    if land_n is None or targ_n is None or targ_n >= land_n:
        return fail(f"reviewer targeted {targ_n} not earlier than landscape {land_n}")

    # Honesty mutant: treating naive string-unique added as the floor would
    # make the clone look like 12 real claims. That must not be the gate.
    if floor["naive_added"] <= 0:
        return fail("honesty mutant has no naive inflation to reject")
    if floor["clustered_added"] >= floor["naive_added"]:
        return fail("clustered rail did not drop clone yield below naive")

    # Paper bytes still contain the compute-matched locators.
    atom = (HERE / "snapshots" / "llm-monkeys-structured-api.body").read_text(
        encoding="utf-8", errors="replace"
    )
    if P.MONKEYS_SWE_1 not in atom or P.MONKEYS_SWE_250 not in atom:
        return fail("llm-monkeys locators missing from captured atom")
    if abs(monkeys["coverage_delta_pp"] - 40.1) > 1e-9:
        return fail("compute-matched delta drifted")
    extra = monkeys["extra_samples"]
    if extra != 249:
        return fail(f"extra_samples {extra} != 249")
    if monkeys["mean_pp_per_extra_sample"] != round(40.1 / 249.0, 6):
        return fail("mean pp per extra sample not recomputed")

    snell = (HERE / "snapshots" / "snell-test-time-structured-api.body").read_text(
        encoding="utf-8", errors="replace"
    )
    if P.SNELL_4X not in snell:
        return fail("snell 4x locator missing")

    if ensemble["correlated"]["independence"] != "non-independent":
        return fail("IMP-0187 correlated ensemble not flagged")
    if ensemble["correlated"]["n_agents"] != 3:
        return fail("IMP-0187 correlated n_agents != 3")
    if ensemble["correlated"]["unique_output_hashes"] != 1:
        return fail("IMP-0187 correlated unique outputs != 1")
    if ensemble["independent"]["independence"] != "independent":
        return fail("IMP-0187 disjoint-input ensemble not independent")

    if not ART.is_file():
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    rec_pub = ((doc.get("measurements") or {}).get("published") or {}).get("llm-monkeys") or {}
    live_delta = pub["papers"]["llm-monkeys"]["compute_matched"]["coverage_delta_pp"]
    got_delta = (rec_pub.get("compute_matched") or {}).get("coverage_delta_pp")
    if got_delta != live_delta:
        return fail("artifact published delta drifted from live")

    # Mutant: a receipt that treated naive clone yield as real must fail.
    mutant_reason = "naive-clone-accepted" if floor["naive_added"] > 0 else "missing"
    print(f"honesty_control mutant_reason={mutant_reason}")
    print(
        f"SUCCESS:RES-0165-probe2 reviewer_flat landscape={land_n} targeted={targ_n} "
        f"papers+IMP-0187"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
