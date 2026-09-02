#!/usr/bin/env python3
"""Probe 2: label-blind reviewer plus control-of-the-control.

The reviewer sees transcripts without attack labels and classifies each
as healthy or collapsed via connected-components on substance_claim
(not vote labels). Agreement with a shipped HEALTHY verdict on an
evading (collapsed) transcript corroborates the evasion.

Control-of-the-control: instant-unanimity and planted dropped-dissent
must FIRE, proving the harness observes a firing control.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import controls  # noqa: E402
import councils as C  # noqa: E402
import corpus  # noqa: E402
import substance  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0135-antigroupthink-evasion.json"
RAW = HERE / "probe2-reviewer-and-coc.raw.json"


def main() -> int:
    live = corpus.measure()
    corroborations: list[dict] = []
    for row in live["attacks"]:
        # Re-classify from a copy that never carried labels.
        blind = json.loads(json.dumps(row["transcript"]))
        rev = substance.classify(blind)
        target_healthy = row["target_verdict"] == "HEALTHY"
        corroborates = (
            rev["class"] == "collapsed" and target_healthy and row["evades_target"]
        )
        corroborations.append(
            {
                "id": row["id"],
                "reviewer_class": rev["class"],
                "cc": rev["substance_clusters"],
                "uf": rev["author_clusters"],
                "target_healthy": target_healthy,
                "corroborates_evasion": corroborates,
            }
        )
        print(
            f"{row['id']} blind_class={rev['class']} cc={rev['substance_clusters']}"
            f" uf={rev['author_clusters']} target_healthy={target_healthy}"
            f" corroborates={corroborates}"
        )

    for h in live["negative_controls"]:
        print(
            f"{h['id']} reviewer={h['reviewer_class']} cc={h['substance_clusters']}"
            f" silent={h['all_shipped_silent']}"
        )

    coc_u = live["control_of_the_control"]
    coc_d = live["control_of_the_control_dropped_dissent"]
    print(
        "coc_unanimity_fired="
        + str(coc_u["fired"])
        + " caught_by="
        + ",".join(coc_u["caught_by"])
    )
    print(
        "coc_drop_fired="
        + str(coc_d["fired"])
        + " caught_by="
        + ",".join(coc_d["caught_by"])
    )

    # Independent re-run of the two CoC councils, not via measure() cache.
    u_live = controls.verdict_map(C.caught_instant_unanimity())
    d_live = controls.verdict_map(C.caught_dropped_dissent())
    u_fire = u_live["CNL-0059"]["fired"] and u_live["CNL-0086-DEBATE-SHAPE"]["fired"]
    d_fire = (
        d_live["CNL-0097"]["fired"]
        and d_live["CNL-0120"]["fired"]
        and d_live["CNL-0070"]["fired"]
    )
    print(f"independent_coc_unanimity_fire={u_fire} independent_coc_drop_fire={d_fire}")

    ok = (
        all(c["corroborates_evasion"] for c in corroborations)
        and all(c["cc"] == c["uf"] == 1 for c in corroborations)
        and all(h["reviewer_class"] == "healthy" for h in live["negative_controls"])
        and coc_u["fired"]
        and coc_d["fired"]
        and u_fire
        and d_fire
        and live["author_reviewer_agree"]
    )

    if not ART.is_file():
        print("FAILED:ADV-0135-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True or rev.get("labels_hidden") is not True:
        print("FAILED:ADV-0135-probe2 reviewer flags")
        ok = False
    if rev.get("control_executed") is not True:
        print("FAILED:ADV-0135-probe2 reviewer did not execute control")
        ok = False
    art_coc = doc.get("control_of_the_control") or {}
    if art_coc.get("fired") is not True:
        print("FAILED:ADV-0135-probe2 artifact CoC did not fire")
        ok = False
    if str(rev.get("verdict") or "").upper() != "PASS":
        print("FAILED:ADV-0135-probe2 reviewer verdict")
        ok = False

    RAW.write_text(
        json.dumps(
            {
                "probe": "probe2-reviewer-and-coc",
                "unit_id": "ADV-0135",
                "ok": ok,
                "corroborations": corroborations,
                "coc_unanimity": coc_u,
                "coc_drop": {"fired": coc_d["fired"], "caught_by": coc_d["caught_by"]},
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    if not ok:
        print("FAILED:ADV-0135-probe2 label-blind reviewer or control-of-the-control")
        return 1
    print(
        "SUCCESS:ADV-0135-probe2 label-blind reviewer corroborates five evasions; "
        "CoC instant-unanimity and dropped-dissent fire"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
