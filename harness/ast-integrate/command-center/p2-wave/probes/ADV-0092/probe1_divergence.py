#!/usr/bin/env python3
"""Probe 1: pairwise lexical and stance divergence after calibrating anchors."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import (  # noqa: E402
    COMPLETION_SENTINEL,
    NOT_DELIVERING,
    OUTPUT_REL,
    REPO,
    UNIT,
)
from measure import measure_probe1  # noqa: E402
from metrics import fmt  # noqa: E402

ART = REPO / OUTPUT_REL
DEFAULT_RAW = HERE / "probe1-divergence.raw.txt"
DEFAULT_MEAS = HERE / "probe1-measurement.json"


def render(live: dict) -> str:
    lines = [
        "Probe 1: pairwise lexical and stance divergence between participants' "
        "first-round briefs, with a planted collapsed council as the low-divergence "
        "anchor.",
        f"mechanism={live['mechanism']}",
        f"evaluation_order={live['evaluation_order']}",
        f"combined_statistic={live['combined_statistic']}",
    ]
    for block in (live["collapsed"], live["diverse"]):
        for pair in block["pairs_detail"]:
            lines.append(
                "PAIR|council={council}|left={left}|right={right}|"
                "lexical_divergence={lex}|stance_divergence={st}|"
                "combined_divergence={comb}".format(
                    council=pair["council"],
                    left=pair["left"],
                    right=pair["right"],
                    lex=fmt(pair["lexical_divergence"]),
                    st=fmt(pair["stance_divergence"]),
                    comb=fmt(pair["combined_divergence"]),
                )
            )
        lines.append(
            "SUMMARY|council={c}|briefs={b}|pairs={p}|mean_lexical_divergence={ml}|"
            "mean_stance_divergence={ms}|mean_combined_divergence={mc}".format(
                c=block["council"],
                b=block["briefs"],
                p=block["pairs"],
                ml=fmt(block["mean_lexical_divergence"]),
                ms=fmt(block["mean_stance_divergence"]),
                mc=fmt(block["mean_combined_divergence"]),
            )
        )
    gate = live["gate"]
    lines.append(f"anchor_margin={fmt(gate['anchor_margin'])}")
    lines.append(
        "threshold.max_collapsed_divergence="
        + fmt(gate["threshold"]["max_collapsed_divergence"])
    )
    lines.append(
        "threshold.min_diverse_divergence="
        + fmt(gate["threshold"]["min_diverse_divergence"])
    )
    lines.append("threshold.min_margin=" + fmt(gate["threshold"]["min_margin"]))
    chk = live["check"]
    lines.append(
        "check.all_collapsed_participants_given_same_role="
        + str(chk["all_collapsed_participants_given_same_role"]).lower()
    )
    lines.append("check.diverse_roles_exact=" + str(chk["diverse_roles_exact"]).lower())
    lines.append(
        "check.anchor_separation_passed="
        + str(chk["anchor_separation_passed"]).lower()
    )
    inv = live["inventory"]
    docs = inv["documents_with_participant_briefs_key"]
    lines.append(
        "inventory.documents_with_participant_briefs_key="
        + (",".join(docs) if docs else "none")
    )
    lines.append(f"inventory.candidate_set_count={inv['candidate_set_count']}")
    lines.append(
        f"inventory.eligible_real_council_count={inv['eligible_real_council_count']}"
    )
    lines.append(f"real_council_scored={str(live['real_council_scored']).lower()}")
    if live.get("real_council"):
        rc = live["real_council"]
        lines.append(
            "SUMMARY|council=real-council|briefs={b}|pairs={p}|"
            "mean_combined_divergence={mc}".format(
                b=rc["briefs"], p=rc["pairs"], mc=fmt(rc["mean_combined_divergence"])
            )
        )
    lines.append(f"target_verdict={live['target_verdict']}")
    lines.append(f"target_reason={live['target_reason']}")
    return "\n".join(lines) + "\n"


def artifact_ok(live: dict) -> str | None:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return "artifact-missing"
    text = ART.read_text(encoding="utf-8")
    if COMPLETION_SENTINEL not in text:
        return "sentinel-absent"
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return "unparseable"
    if str(doc.get("unit_id") or "") != UNIT:
        return "unit-id"
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return f"self-declared:{st}"
    named = doc.get("named_probes") or []
    if not any(isinstance(p, dict) and p.get("id") in {"probe1", "T-PROBE-1-PAIRWISE-DIVERGENCE"} for p in named):
        if not any(
            isinstance(t, dict) and t.get("id") == "T-PROBE-1-PAIRWISE-DIVERGENCE"
            for t in (doc.get("tests") or [])
        ):
            return "probe1-not-recorded"
    live_c = live["collapsed"]["mean_combined_divergence"]
    art_p1 = (doc.get("probe1") or {}).get("collapsed") or {}
    if art_p1:
        art_c = float(art_p1.get("mean_combined_divergence") or -1)
        if abs(art_c - live_c) > 1e-9:
            return "collapsed-mean-drift"
    if not bool((doc.get("probe1") or {}).get("check", {}).get("anchor_separation_passed")):
        if not live["check"]["anchor_separation_passed"]:
            return "anchor-gate-red"
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(DEFAULT_RAW))
    parser.add_argument("--measurement", default=str(DEFAULT_MEAS))
    args = parser.parse_args()
    live = measure_probe1(clone_diverse_from_collapsed=False)
    text = render(live)
    Path(args.measurement).write_text(
        json.dumps(
            {
                k: v
                for k, v in live.items()
                if k not in {"collapsed", "diverse", "real_council"}
                or True
            },
            indent=2,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )
    Path(args.output).write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    if not live["check"]["anchor_separation_passed"]:
        sys.stdout.write("FAILED:ADV-0092-probe1 anchor-separation-red\n")
        return 1
    if not live["check"]["all_collapsed_participants_given_same_role"]:
        sys.stdout.write("FAILED:ADV-0092-probe1 collapsed-roles-not-identical\n")
        return 1
    if not live["check"]["diverse_roles_exact"]:
        sys.stdout.write("FAILED:ADV-0092-probe1 diverse-roles\n")
        return 1
    err = artifact_ok(live)
    if err:
        sys.stdout.write(f"FAILED:ADV-0092-probe1 {err}\n")
        return 1
    sys.stdout.write("SUCCESS:ADV-0092-probe1\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
