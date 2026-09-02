#!/usr/bin/env python3
"""Probe 1: five evasions slip their target controls; healthy twins stay silent.

Both-states: each attack is collapsed (substance clusters == 1) with the
named control HEALTHY; the paired healthy council (same n, topology,
round_budget) is not flagged by that control or by any other shipped
predicate in this harness.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import councils as C  # noqa: E402
import corpus  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0135-antigroupthink-evasion.json"
RAW = HERE / "probe1-evasion-both-states.raw.json"
GEOMETRY = {
    "n_participants": C.N_PARTICIPANTS,
    "topology": C.TOPOLOGY,
    "round_budget": C.ROUND_BUDGET,
}


def main() -> int:
    live = corpus.measure()
    attacks = live["attacks"]
    negatives = {h["id"]: h for h in live["negative_controls"]}

    print(
        "n_attacks="
        + str(live["n_attacks"])
        + " n_evading="
        + str(live["n_evading"])
        + " n_fully_silent="
        + str(live["n_fully_silent_on_shipped"])
        + " n_nc_pass="
        + str(live["n_negative_passed"])
        + " n_reviewer_collapsed="
        + str(live["n_reviewer_collapsed"])
    )
    for row in attacks:
        nc = negatives[row["negative_control_id"]]
        fired = ",".join(
            v["control_id"] for v in row["control_verdicts"] if v["fired"]
        ) or "none"
        print(
            f"{row['id']} target={row['defeated_control']}"
            f" target_verdict={row['target_verdict']}"
            f" fired=[{fired}]"
            f" clusters={row['substance_clusters']}"
            f" reviewer={row['reviewer_class']}"
            f" nc_silent={nc['all_shipped_silent']}"
            f" nc_clusters={nc['substance_clusters']}"
            f" geometry_match="
            + str(
                nc["n_participants"] == GEOMETRY["n_participants"]
                and nc["topology"] == GEOMETRY["topology"]
                and nc["round_budget"] == GEOMETRY["round_budget"]
            )
        )

    ok = (
        live["ok"]
        and live["n_attacks"] >= 5
        and live["n_evading"] >= 5
        and live["n_fully_silent_on_shipped"] >= 5
        and live["n_negative_passed"] == live["n_attacks"]
        and live["n_reviewer_collapsed"] == live["n_attacks"]
        and all(h["all_shipped_silent"] for h in live["negative_controls"])
        and all(h["reviewer_class"] == "healthy" for h in live["negative_controls"])
        and all(
            h["n_participants"] == GEOMETRY["n_participants"]
            and h["topology"] == GEOMETRY["topology"]
            and h["round_budget"] == GEOMETRY["round_budget"]
            for h in live["negative_controls"]
        )
    )

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:ADV-0135-probe1 artifact missing")
        RAW.write_text(json.dumps({"pass": False, "live": live}, indent=2) + "\n")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ADV-0135-probe1 self-declared {doc.get('state')}")
        return 1
    art_attacks = corpus.artifact_attacks(doc)
    art_ids = [a["id"] for a in art_attacks]
    live_ids = [a["id"] for a in attacks]
    if art_ids != live_ids:
        print(f"FAILED:ADV-0135-probe1 attack-id drift art={art_ids} live={live_ids}")
        ok = False
    for live_a, art_a in zip(attacks, art_attacks):
        if live_a["target_verdict"] != art_a.get("target_verdict"):
            print(
                f"FAILED:ADV-0135-probe1 verdict drift {live_a['id']} "
                f"live={live_a['target_verdict']} art={art_a.get('target_verdict')}"
            )
            ok = False
        if live_a["substance_clusters"] != art_a.get("substance_clusters"):
            print(f"FAILED:ADV-0135-probe1 cluster drift {live_a['id']}")
            ok = False

    RAW.write_text(
        json.dumps(
            {
                "probe": "probe1-evasion-both-states",
                "unit_id": "ADV-0135",
                "ok": ok,
                "n_evading": live["n_evading"],
                "n_fully_silent_on_shipped": live["n_fully_silent_on_shipped"],
                "n_negative_passed": live["n_negative_passed"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    if not ok:
        print("FAILED:ADV-0135-probe1 evasion both-states")
        return 1
    print("SUCCESS:ADV-0135-probe1 five evasions silent on shipped controls, healthy twins silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
