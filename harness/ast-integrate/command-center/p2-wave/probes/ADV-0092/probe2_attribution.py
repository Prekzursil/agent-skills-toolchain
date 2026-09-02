#!/usr/bin/env python3
"""Probe 2: recover hidden role labels above chance with a separate classifier.

Does not read Probe 1 measurement JSON or stance fields.
"""
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
from measure import measure_probe2  # noqa: E402
from metrics import fmt  # noqa: E402

ART = REPO / OUTPUT_REL
DEFAULT_RAW = HERE / "probe2-attribution.raw.txt"
DEFAULT_MEAS = HERE / "probe2-measurement.json"


def _count_blob(counts: dict) -> str:
    return ",".join(f"{k}:{counts[k]}" for k in counts)


def render(live: dict) -> str:
    lines = [
        "Probe 2 (mechanically different): role-attribution test - present "
        "unlabelled briefs to an independent classifier and measure whether the "
        "assigned role can be recovered above chance; unrecoverable roles are "
        "collapsed regardless of surface wording differences.",
        f"mechanism={live['mechanism']}",
        f"classifier_input={live['classifier_input']}",
        f"classifier_fixture={live['classifier_fixture']}",
        f"classifier_prototypes_sha256={live['classifier_prototypes_sha256']}",
        f"chance_accuracy={fmt(live['chance_accuracy'])}",
    ]
    for block in (live["diverse"], live["surface_varied_collapse"]):
        for row in block["rows"]:
            lines.append(
                "ATTRIBUTION|dataset={ds}|item={item}|predicted={pred}|"
                "truth_revealed_after_prediction={truth}|correct={ok}|"
                "best_score={score}".format(
                    ds=row["dataset"],
                    item=row["item"],
                    pred=row["predicted"],
                    truth=row["truth_revealed_after_prediction"],
                    ok=str(row["correct"]).lower(),
                    score=fmt(row["best_score"]),
                )
            )
        lines.append(
            "ATTRIBUTION-SUMMARY|dataset={ds}|correct={c}|n={n}|accuracy={a}|"
            "chance={ch}|binomial_tail_p={p:.8f}|predicted_role_counts={cnt}".format(
                ds=block["dataset"],
                c=block["correct"],
                n=block["n"],
                a=fmt(block["accuracy"]),
                ch=fmt(block["chance"]),
                p=block["binomial_tail_p"],
                cnt=_count_blob(block["predicted_role_counts"]),
            )
        )
    chk = live["check"]
    lines.append(
        "check.diverse_roles_recovered_above_chance="
        + str(chk["diverse_roles_recovered_above_chance"]).lower()
    )
    lines.append(
        "check.diverse_recovery_binomial_p_lte_0_05="
        + str(chk["diverse_recovery_binomial_p_lte_0_05"]).lower()
    )
    lines.append(
        "check.surface_varied_collapse_unrecoverable="
        + str(chk["surface_varied_collapse_unrecoverable"]).lower()
    )
    lines.append(
        "inventory.eligible_real_council_count="
        + str(live["inventory"]["eligible_real_council_count"])
    )
    lines.append(f"real_council_scored={str(live['real_council_scored']).lower()}")
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
    art = doc.get("probe2") or {}
    art_sha = str(art.get("classifier_prototypes_sha256") or "")
    if art_sha and art_sha != live["classifier_prototypes_sha256"]:
        return "prototype-sha-drift"
    art_div = (art.get("diverse") or {}).get("accuracy")
    if art_div is not None and abs(float(art_div) - live["diverse"]["accuracy"]) > 1e-9:
        return "diverse-accuracy-drift"
    # Independence: artifact must record that Probe 2 does not consume Probe 1.
    mech = str(art.get("mechanism") or live["mechanism"])
    if "no Probe 1" not in mech and "no probe 1" not in mech.lower():
        return "probe2-not-independent"
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(DEFAULT_RAW))
    parser.add_argument("--measurement", default=str(DEFAULT_MEAS))
    args = parser.parse_args()
    live = measure_probe2()
    text = render(live)
    Path(args.measurement).write_text(
        json.dumps(live, indent=2, default=str) + "\n", encoding="utf-8"
    )
    Path(args.output).write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    chk = live["check"]
    if not chk["diverse_roles_recovered_above_chance"]:
        sys.stdout.write("FAILED:ADV-0092-probe2 diverse-not-recovered\n")
        return 1
    if not chk["surface_varied_collapse_unrecoverable"]:
        sys.stdout.write("FAILED:ADV-0092-probe2 collapse-still-recoverable\n")
        return 1
    err = artifact_ok(live)
    if err:
        sys.stdout.write(f"FAILED:ADV-0092-probe2 {err}\n")
        return 1
    sys.stdout.write("SUCCESS:ADV-0092-probe2\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
