#!/usr/bin/env python3
"""Probe 2: accumulation trips the concentration cap; independent recount.

Reviewer method: Kahn leftover-nodes (not DFS) for cycles; a second walk for
terminal weights. A disagreement in the number blocks the unit.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import delegate as D  # noqa: E402
import recount as R  # noqa: E402

ART = REPO / "command-center/design/council/CNL-0067-delegation-and-proxy-voting-without-delegation-cycles.md"
FIX = HERE / "fixtures"


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0067-probe2 {msg}")
    return 1


def spy_process(profile: dict, **kwargs) -> tuple[dict, int]:
    n = {"calls": 0}

    def spy(p, effective):
        n["calls"] += 1
        return D.tabulate(p, effective)

    row = D.process(profile, tabulate_fn=spy, **kwargs)
    return row, n["calls"]


def main() -> int:
    acc = D.load_profile(FIX / "accumulate-to-D.json")
    good = D.load_profile(FIX / "good-under-cap.json")
    cycle = D.load_profile(FIX / "cycle-abc.json")

    acc_row, acc_calls = spy_process(acc)
    print("accumulate-to-D " + D.compact(acc_row) + f" tabulate_calls={acc_calls}")
    if acc_row["status"] != D.STATUS_CAP:
        return fail(f"accumulate status={acc_row['status']}")
    if acc_row["tabulated"] is not False or acc_row["winner"] is not None:
        return fail("accumulate produced a tabulated winner")
    if acc_calls != 0:
        return fail("accumulate called tabulate")
    if not acc_row["offenders"] or acc_row["offenders"][0]["seat"] != "D":
        return fail("cap did not name seat D")
    share = acc_row["offenders"][0]["share"]
    if abs(share - 0.8) > 1e-9:
        return fail(f"D share {share} != 0.8")

    good_row, good_calls = spy_process(good)
    print("good-under-cap " + D.compact(good_row) + f" tabulate_calls={good_calls}")
    if good_row["status"] != D.STATUS_OK or good_calls != 1:
        return fail("good fixture did not tabulate")
    b_share = good_row["effective"]["B"] / sum(good_row["effective"].values())
    if not (b_share < 0.5):
        return fail(f"good B share {b_share} should be under cap")

    # Independent recount (Kahn), not DFS.
    cyclic = R.kahn_cyclic_nodes(cycle)
    acyclic = R.kahn_cyclic_nodes(acc)
    acyclic_good = R.kahn_cyclic_nodes(good)
    print(f"kahn cycle-abc leftover={sorted(cyclic)}")
    print(f"kahn accumulate leftover={sorted(acyclic)}")
    print(f"kahn good leftover={sorted(acyclic_good)}")
    if cyclic != {"A", "B", "C"}:
        return fail(f"Kahn/DFS disagreement on cycle members: {cyclic}")
    if acyclic or acyclic_good:
        return fail("Kahn reported a cycle on an acyclic fixture")

    ind_acc = R.independent_effective(acc)
    ind_good = R.independent_effective(good)
    print(f"independent accumulate D={ind_acc['D']} total={sum(ind_acc.values())}")
    print(f"independent good B={ind_good['B']} total={sum(ind_good.values())}")
    if abs(ind_acc["D"] - 4.0) > 1e-9 or abs(sum(ind_acc.values()) - 5.0) > 1e-9:
        return fail("independent accumulate weights disagree")
    if abs(ind_good["B"] - 2.0) > 1e-9:
        return fail("independent good B weight disagrees")
    if abs(ind_acc["D"] - acc_row["effective"]["D"]) > 1e-9:
        return fail("author vs reviewer D weight disagreement")

    mutant, mutant_calls = spy_process(acc, skip_cap_check=True)
    print(
        "mutant-skip-cap "
        + D.compact(mutant)
        + f" tabulate_calls={mutant_calls}"
    )
    if mutant.get("status") != D.STATUS_OK or mutant_calls != 1:
        return fail("skip_cap_check mutant did not tabulate; cap gate not live")
    if mutant.get("winner") is None:
        return fail("skip_cap_check mutant produced no winner")

    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:CNL-0067" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel absent")
    claims = {c["id"]: c for c in doc.get("claims") or []}
    for cid in ("C1", "C2", "C3"):
        if cid not in claims or claims[cid].get("verdict") != "CONFIRMED":
            return fail(f"claim {cid} missing or not CONFIRMED")
    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True or rev.get("verdict") != "PASS":
        return fail("reviewer not independent PASS")
    ncs = doc.get("negative_controls") or []
    if not any("CONCENTRATION_CAP" in str(n.get("observed") or "") for n in ncs):
        return fail("negative_controls missing cap observation")

    print(
        "NEGATIVE-CONTROL accumulate-to-D: "
        "check concentration_offenders + CAP-GATE refuse tabulation; "
        f"observed {D.compact(acc_row)}; "
        f"mutant skip_cap_check tabulated winner={mutant.get('winner')}"
    )
    print("SUCCESS:CNL-0067-probe2 concentration cap and independent recount")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
