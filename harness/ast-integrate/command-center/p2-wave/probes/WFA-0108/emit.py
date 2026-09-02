#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0108-fusion-capability-loss-detector.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from detector import attempt_certify, exercise, scan_corpus  # noqa: E402
from fixtures import (  # noqa: E402
    EXTRACTION_RULE,
    FAILURE_CLASS_ID,
    FUSIONS,
    MECH_LICENSE,
    MECH_RETRY,
    NAMED_FAILURE,
    SEVERITY_P1,
    SPEC_ANCHOR,
    SRC_BETA,
    TOKENS,
    UNIT,
)

OUT_REL = "command-center/wfa/WFA-0108-fusion-capability-loss-detector.json"
SCHEMA_REL = "command-center/wfa/schema/wfa-schema-pack.json#/$defs/RegressionFixture"
SENTINEL = f"SUCCESS:{UNIT}"
QUESTION = (
    "Implementation target: a detector computing, for every fusion, whether "
    "its capability set is a superset of the union of its sources' capability "
    "sets - and failing the fusion when any source capability is missing, the "
    "spec's named failure class workflow fusion loses a source capability."
)


def _wf(fusion_id: str) -> dict:
    for spec in FUSIONS:
        if spec["id"] == fusion_id:
            return spec["workflow"]
    raise KeyError(fusion_id)


def build() -> dict:
    scan = scan_corpus(FUSIONS)
    by_id = {v["fusion_id"]: v for v in scan["verdicts"]}
    keep = by_id["fusion-keep"]
    loss = by_id["fusion-lossy-planted"]
    disc = by_id["fusion-disconnected"]
    phantom = by_id["fusion-phantom-declaration"]

    src_retry = exercise(SRC_BETA, MECH_RETRY)
    disc_retry = exercise(_wf("fusion-disconnected"), MECH_RETRY)
    keep_retry = exercise(_wf("fusion-keep"), MECH_RETRY)
    loss_retry = exercise(_wf("fusion-lossy-planted"), MECH_RETRY)

    both_states = {
        "lossless_fusion_id": "fusion-keep",
        "lossless_detector_silent": keep["detector_fired"] is False,
        "lossless_may_certify": keep["may_proceed_to_certification"] is True,
        "lossy_fusion_id": "fusion-lossy-planted",
        "lossy_detector_fired": loss["detector_fired"] is True,
        "lossy_signal_a_caught": MECH_RETRY in loss["signal_a"]["missing"],
        "lossy_signal_b_caught": MECH_RETRY in loss["signal_b"]["missing"],
        "lossy_both_signals": (
            MECH_RETRY in loss["signal_a"]["missing"]
            and MECH_RETRY in loss["signal_b"]["missing"]
        ),
        "pass": (
            keep["detector_fired"] is False
            and keep["may_proceed_to_certification"] is True
            and loss["detector_fired"] is True
            and MECH_RETRY in loss["signal_a"]["missing"]
            and MECH_RETRY in loss["signal_b"]["missing"]
        ),
    }
    planted = {
        "fusion_id": "fusion-lossy-planted",
        "dropped_mechanism": MECH_RETRY,
        "signal_a_missing": loss["signal_a"]["missing"],
        "signal_b_missing": loss["signal_b"]["missing"],
        "caught_by_both_signals": both_states["lossy_both_signals"],
        "pass": both_states["lossy_both_signals"] and not loss["divergence"]["present"],
    }
    disconnected = {
        "fusion_id": "fusion-disconnected",
        "mechanism_id": MECH_RETRY,
        "source_token_present": src_retry["token_present"],
        "fusion_token_present": disc_retry["token_present"],
        "keep_control_token_present": keep_retry["token_present"],
        "lossy_token_present": loss_retry["token_present"],
        "signal_a_silent": disc["signal_a"]["missing"] == [],
        "signal_b_fired": MECH_RETRY in disc["signal_b"]["missing"],
        "divergence_present": disc["divergence"]["present"] is True,
        "divergence_only_in_behaviour": disc["divergence"]["only_in_behaviour"],
        "pass": (
            src_retry["token_present"]
            and not disc_retry["token_present"]
            and keep_retry["token_present"]
            and not loss_retry["token_present"]
            and disc["signal_a"]["missing"] == []
            and MECH_RETRY in disc["signal_b"]["missing"]
            and disc["divergence"]["present"] is True
        ),
    }
    phantom_div = {
        "fusion_id": "fusion-phantom-declaration",
        "divergence_present": phantom["divergence"]["present"] is True,
        "only_in_matrix": phantom["divergence"]["only_in_matrix"],
        "only_in_behaviour": phantom["divergence"]["only_in_behaviour"],
        "pass": (
            phantom["divergence"]["present"] is True
            and phantom["divergence"]["only_in_matrix"] == [MECH_LICENSE]
            and phantom["divergence"]["only_in_behaviour"] == []
        ),
    }

    cert_keep = attempt_certify(keep)
    cert_loss = attempt_certify(loss)
    cert_disc = attempt_certify(disc)
    p1_gate = {
        "severity": SEVERITY_P1,
        "rule": scan["certification_gate"]["rule"],
        "lossless_status": cert_keep["status"],
        "lossy_status": cert_loss["status"],
        "disconnected_status": cert_disc["status"],
        "lossy_certification_record": cert_loss["certification_record"],
        "disconnected_certification_record": cert_disc["certification_record"],
        "pass": (
            cert_keep["status"] == "ADMITTED"
            and cert_loss["status"] == "REFUSED"
            and cert_disc["status"] == "REFUSED"
            and cert_loss["certification_record"] is None
            and cert_disc["certification_record"] is None
        ),
    }

    tests_ok = (
        both_states["pass"]
        and planted["pass"]
        and disconnected["pass"]
        and phantom_div["pass"]
        and p1_gate["pass"]
    )
    if not tests_ok:
        raise SystemExit(
            "FAILED:WFA-0108 emit live detector did not satisfy required tests "
            + json.dumps(
                {
                    "both_states": both_states["pass"],
                    "planted": planted["pass"],
                    "disconnected": disconnected["pass"],
                    "phantom": phantom_div["pass"],
                    "p1_gate": p1_gate["pass"],
                    "keep": keep,
                    "loss": loss,
                    "disc": disc,
                    "phantom_verdict": phantom,
                },
                default=str,
            )[:6000]
        )

    pack = REPO / "command-center/wfa/schema/wfa-schema-pack.json"
    return {
        "record_type": "RegressionFixture",
        "schema_ref": SCHEMA_REL,
        "schema_pack_present_on_worktree": pack.is_file(),
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": (
            "Detector proving a fusion's capability set contains the union of "
            "its sources' capabilities"
        ),
        "question": QUESTION,
        "named_failure_class": NAMED_FAILURE,
        "failure_class_id": FAILURE_CLASS_ID,
        "spec_anchor": SPEC_ANCHOR,
        "severity_on_loss": SEVERITY_P1,
        "honesty": {
            "upstream_wfa_0059_artifact": "absent on this worktree",
            "upstream_wfa_0094_artifact": "absent on this worktree",
            "stand_in": (
                "Incidence cells are extracted from fixture workflow stage "
                "definitions (not prose). The detector is live on that matrix "
                "and on executable pipelines; it does not claim the 284-candidate "
                "estate matrix exists here."
            ),
            "schema_pack": (
                "WFA-0001 schema pack is absent; this record is a RegressionFixture "
                "by this unit's field contract, not a jsonschema-validated pack hit."
            ),
        },
        "extraction_rule": EXTRACTION_RULE,
        "evidence": {
            "A": {
                "name": "superset check over the mechanism incidence matrix",
                "method": "union(source declared sets) - fusion declared set",
                "computed": True,
            },
            "B": {
                "name": "behavioural probe exercising each source capability",
                "method": (
                    "walk reachable stages from fusion entry and require the "
                    "source mechanism's distinctive token in the fused output"
                ),
                "computed": True,
            },
        },
        "tokens": TOKENS,
        "incidence_matrix": scan["incidence_matrix"],
        "fusions": scan["verdicts"],
        "certification_gate": scan["certification_gate"],
        "controls": {
            "both_states": both_states,
            "planted_lossy_caught_by_both_signals": planted,
            "disconnected_capability_behavioural": disconnected,
            "divergence_phantom_declaration": phantom_div,
            "p1_certification_refusal": p1_gate,
        },
        "tests_required": [
            "a planted lossy fusion must be caught by BOTH signals, and a divergence between them is itself reported",
            "the behavioural probe must be shown to detect a capability that was deliberately disconnected",
            "capability loss is P1: a fusion failing this detector may not proceed to certification",
        ],
        "tests_result": {
            "planted_lossy_both_signals": planted["pass"],
            "divergence_reported": disconnected["pass"] and phantom_div["pass"],
            "behavioural_disconnected_detected": disconnected["pass"],
            "p1_blocks_certification": p1_gate["pass"],
            "all_pass": True,
        },
        "computed_not_asserted": True,
        "SUCCESS:WFA-0108": True,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generated_by": "command-center/p2-wave/probes/WFA-0108/emit.py",
    }


def main() -> int:
    doc = build()
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=True)
        fh.write("\n")
    print(f"wrote {OUT_REL} bytes={out.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
