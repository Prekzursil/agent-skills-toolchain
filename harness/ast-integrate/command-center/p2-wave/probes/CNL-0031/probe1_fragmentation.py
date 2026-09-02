"""Probe 1: fragmentation — facts in a caucus that never reach plenary.

Two mechanically independent signals:
  A) live set-difference inside topology.simulate
  B) recount.recount over serialized fact_ids (dict.fromkeys + list membership)
A topology claiming no loss (flat identity) must show lost_count==0 on both.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import recount as R  # noqa: E402
import topology as T  # noqa: E402


def slim(row: dict) -> dict:
    return {
        "n": row["n"],
        "k": row["k"],
        "c": row["c"],
        "g": row["g"],
        "family": row["family"],
        "identity_fan_in": row["identity_fan_in"],
        "lost_count": row["lost_count"],
        "lost_ids": row["lost_ids"],
        "caucus_count": row["caucus_count"],
        "plenary_count": row["plenary_count"],
        "planted_fact": row["planted_fact"],
        "planted_in_group0": row["planted_in_group0"],
        "planted_in_plenary": row["planted_in_plenary"],
        "fragmentation_fires": row["fragmentation_fires"],
        "expected_lost": row["expected_lost"],
        "net_score": row["net_score"],
        "group_transcripts": [
            {"group_index": t["group_index"], "fact_ids": t["fact_ids"]}
            for t in row["group_transcripts"]
        ],
        "plenary_payloads": [
            {"group_index": p["group_index"], "fact_ids": p["fact_ids"]}
            for p in row["plenary_payloads"]
        ],
    }


def main() -> int:
    rows = T.sweep()
    print(f"sweep n={T.N_DEFAULT} c={T.C_DEFAULT} planted={T.PLANTED_FACT_ID}")
    agree = 0
    lossy_ks: list[int] = []
    flat_ok = False
    planted_lossy = False
    for row in rows:
        rec = R.recount(slim(row))
        match = (
            rec["lost_count"] == row["lost_count"]
            and rec["lost_ids"] == row["lost_ids"]
            and rec["fragmentation_fires"] == row["fragmentation_fires"]
            and row["lost_count"] == row["expected_lost"]
        )
        agree += int(match)
        print(
            f"k={row['k']} g={row['g']} family={row['family']} "
            f"lost={row['lost_count']} expected={row['expected_lost']} "
            f"recount={rec['lost_count']} planted_in_plenary={row['planted_in_plenary']} "
            f"fires={row['fragmentation_fires']} match={match}"
        )
        if not match:
            print("FAILED:CNL-0031-probe1 signal-A/B disagree or closed-form miss")
            print(json.dumps({"sim": slim(row), "recount": rec}, indent=2, sort_keys=True))
            return 1
        if row["k"] == T.N_DEFAULT:
            if row["lost_count"] != 0 or not row["planted_in_plenary"] or row["fragmentation_fires"]:
                print("FAILED:CNL-0031-probe1 flat topology claimed no loss but measurement failed")
                return 1
            flat_ok = True
        if row["lost_count"] > 0:
            lossy_ks.append(row["k"])
        if row["k"] == T.first_subdivision_from_flat() and row["fragmentation_fires"]:
            if T.PLANTED_FACT_ID not in row["lost_ids"]:
                print("FAILED:CNL-0031-probe1 planted fact not in lost set")
                return 1
            planted_lossy = True
    if agree != len(rows) or not flat_ok or not planted_lossy:
        print(
            f"FAILED:CNL-0031-probe1 agree={agree}/{len(rows)} "
            f"flat_ok={flat_ok} planted_lossy={planted_lossy}"
        )
        return 1
    xo = T.crossover_k()
    first_cut = T.first_subdivision_from_flat()
    print(f"crossover_k={xo} first_subdivision_from_flat={first_cut} lossy_ks={lossy_ks}")
    print(f"two_signal_agree={agree}/{len(rows)}")
    # Catalog requirement: measure information that exists in one caucus and
    # never reaches the plenary.
    bad = T.simulate(k=first_cut)
    print(
        f"caucus_exclusive {T.PLANTED_FACT_ID} in_group0={bad['planted_in_group0']} "
        f"in_plenary={bad['planted_in_plenary']} lost_ids={bad['lost_ids']}"
    )
    print("SUCCESS:CNL-0031-probe1 fragmentation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
