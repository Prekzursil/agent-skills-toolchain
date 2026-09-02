"""Token presence vs semantic-claim presence at each downstream stage."""
from __future__ import annotations

from fixture import (
    COUNTEREXAMPLE_ID,
    DISSENT_TOKEN,
    MAJORITY_CLAIM,
    MAJORITY_TOKEN,
    STAGES,
)
from pipeline import run_pipeline, stage_order


def _claim_present(blob: str) -> bool:
    """Substance of the dissent: counterexample id plus the 0.41 FNR observation.

    Mechanically different from token substring search: a husk that keeps
    DISSENT_TOKEN but drops ADV97-COUNTER-XRAY-771 / 0.41 false-negative
    fails this check.
    """
    blob_l = blob.lower()
    has_id = COUNTEREXAMPLE_ID in blob
    has_rate = "0.41" in blob and "false-negative" in blob_l
    return has_id and has_rate


def _majority_claim_present(blob: str) -> bool:
    return MAJORITY_TOKEN in blob and "0.95 consensus cap" in blob.lower()


def _minority_registered(manifest_doc: dict) -> bool:
    entries = manifest_doc.get("entries") or []
    return any(
        isinstance(row, dict) and row.get("role") == "minority_report"
        for row in entries
    )


def inspect_run(run: dict) -> dict:
    blobs: dict = run["blobs"]
    stages_doc: dict = run["stages"]
    rows = []
    first_token_absent = None
    first_claim_absent = None
    first_majority_token_absent = None
    first_majority_claim_absent = None
    for stage in stage_order():
        blob = blobs[stage]
        token = DISSENT_TOKEN in blob
        claim = _claim_present(blob)
        maj_tok = MAJORITY_TOKEN in blob
        maj_claim = _majority_claim_present(blob)
        extra = {}
        if stage == "artifact_manifest":
            extra["minority_report_registered"] = _minority_registered(
                stages_doc[stage]
            )
            # Manifest survival is registration of the minority artifact,
            # not whether prose was duplicated into the index.
            token = extra["minority_report_registered"] and token
            claim = extra["minority_report_registered"] and claim
        if first_token_absent is None and not token:
            first_token_absent = stage
        if first_claim_absent is None and not claim:
            first_claim_absent = stage
        if first_majority_token_absent is None and not maj_tok:
            first_majority_token_absent = stage
        if first_majority_claim_absent is None and not maj_claim:
            first_majority_claim_absent = stage
        rows.append(
            {
                "stage": stage,
                "dissent_token_present": token,
                "dissent_claim_present": claim,
                "majority_token_present": maj_tok,
                "majority_claim_present": maj_claim,
                **extra,
            }
        )
    majority_ok = (
        first_majority_token_absent is None
        and first_majority_claim_absent is None
    )
    return {
        "policy": run["policy"],
        "rows": rows,
        "first_dissent_token_absent": first_token_absent,
        "first_dissent_claim_absent": first_claim_absent,
        "first_majority_token_absent": first_majority_token_absent,
        "first_majority_claim_absent": first_majority_claim_absent,
        "majority_survived_every_stage": majority_ok,
        "dissent_token_survived_every_stage": first_token_absent is None,
        "dissent_claim_survived_every_stage": first_claim_absent is None,
        "trace_broken": not majority_ok,
    }


def inspect_policy(policy: str) -> dict:
    return inspect_run(run_pipeline(policy))


def matrix() -> dict:
    out = {name: inspect_policy(name) for name in ("husk", "omit", "preserve", "drop_majority")}
    husk = out["husk"]
    preserve = out["preserve"]
    mutant = out["drop_majority"]
    omit = out["omit"]
    return {
        "live_policy": "husk",
        "husk": husk,
        "omit": omit,
        "preserve": preserve,
        "drop_majority": mutant,
        "control_majority_survives_on_live": husk["majority_survived_every_stage"],
        "control_majority_survives_on_preserve": preserve["majority_survived_every_stage"],
        "control_fires_on_majority_drop": mutant["trace_broken"],
        "preserve_keeps_token": preserve["dissent_token_survived_every_stage"],
        "preserve_keeps_claim": preserve["dissent_claim_survived_every_stage"],
        "stages": list(STAGES),
    }
