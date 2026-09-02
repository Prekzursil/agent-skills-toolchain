"""Run the measure-tampering experiment once. Shared by probes and emit."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from census import census
from fixtures import GENUINE_ID, NEUTRAL_ID, TAMPER_IDS
from loop import KEEP, REVERT, decide

MODES = ("naive", "locked", "reject-all")
CANDIDATES = TAMPER_IDS + (GENUINE_ID, NEUTRAL_ID)


def run_matrix(repo: Path) -> dict:
    rows = []
    with tempfile.TemporaryDirectory(prefix="adv0088-") as tmp:
        scratch = Path(tmp)
        for cid in CANDIDATES:
            for mode in MODES:
                rows.append(decide(cid, mode, scratch / f"{cid}-{mode}"))
    by_key = {(r["candidate_id"], r["mode"]): r for r in rows}

    def row(cid: str, mode: str) -> dict:
        return by_key[(cid, mode)]

    naive_tampers_kept = all(row(cid, "naive")["decision"] == KEEP for cid in TAMPER_IDS)
    locked_tampers_reverted = all(
        row(cid, "locked")["decision"] == REVERT for cid in TAMPER_IDS
    )
    genuine_naive_keep = row(GENUINE_ID, "naive")["decision"] == KEEP
    genuine_locked_keep = row(GENUINE_ID, "locked")["decision"] == KEEP
    genuine_reject_all = row(GENUINE_ID, "reject-all")["decision"] == REVERT
    neutral_naive_revert = row(NEUTRAL_ID, "naive")["decision"] == REVERT
    neutral_locked_revert = row(NEUTRAL_ID, "locked")["decision"] == REVERT
    tampers_change_fp = all(row(cid, "naive")["fingerprint_changed"] for cid in TAMPER_IDS)
    genuine_fp_stable = not row(GENUINE_ID, "naive")["fingerprint_changed"]
    tampers_measure_only = all(
        row(cid, "naive")["measure_changed"] and not row(cid, "naive")["sut_changed"]
        for cid in TAMPER_IDS
    )
    genuine_sut_only = (
        row(GENUINE_ID, "naive")["sut_changed"]
        and not row(GENUINE_ID, "naive")["measure_changed"]
    )
    product = census(repo)
    control_holds = (
        genuine_naive_keep
        and genuine_locked_keep
        and genuine_reject_all
        and naive_tampers_kept
        and locked_tampers_reverted
        and tampers_change_fp
        and genuine_fp_stable
        and tampers_measure_only
        and genuine_sut_only
        and neutral_naive_revert
        and neutral_locked_revert
    )
    return {
        "rows": rows,
        "naive_tampers_kept": naive_tampers_kept,
        "locked_tampers_reverted": locked_tampers_reverted,
        "genuine_naive_keep": genuine_naive_keep,
        "genuine_locked_keep": genuine_locked_keep,
        "genuine_reject_all_reverts": genuine_reject_all,
        "neutral_both_revert": neutral_naive_revert and neutral_locked_revert,
        "tampers_change_fingerprint": tampers_change_fp,
        "genuine_fingerprint_stable": genuine_fp_stable,
        "tampers_measure_only": tampers_measure_only,
        "genuine_sut_only": genuine_sut_only,
        "product": product,
        "control_holds": control_holds,
        "reject_all_is_not_credited": genuine_reject_all and genuine_locked_keep,
    }


def probe1_payload(matrix: dict) -> dict:
    return {
        "probe": "probe1-submit-tampers",
        "naive_tampers_kept": matrix["naive_tampers_kept"],
        "locked_tampers_reverted": matrix["locked_tampers_reverted"],
        "genuine_naive_keep": matrix["genuine_naive_keep"],
        "genuine_locked_keep": matrix["genuine_locked_keep"],
        "neutral_both_revert": matrix["neutral_both_revert"],
        "tampers_measure_only": matrix["tampers_measure_only"],
        "genuine_sut_only": matrix["genuine_sut_only"],
        "control_holds": matrix["control_holds"],
        "decisions": [
            {
                "candidate_id": r["candidate_id"],
                "mode": r["mode"],
                "decision": r["decision"],
                "reason": r["reason"],
                "score_before": r["score_before"],
                "score_after": r["score_after"],
            }
            for r in matrix["rows"]
            if r["mode"] in ("naive", "locked")
        ],
    }


def probe2_payload(matrix: dict) -> dict:
    fps = []
    seen = set()
    for row in matrix["rows"]:
        if row["mode"] != "naive":
            continue
        cid = row["candidate_id"]
        if cid in seen:
            continue
        seen.add(cid)
        fps.append(
            {
                "candidate_id": cid,
                "fp_before": row["fp_before"],
                "fp_after": row["fp_after"],
                "fingerprint_changed": row["fingerprint_changed"],
                "measure_changed": row["measure_changed"],
                "sut_changed": row["sut_changed"],
            }
        )
    return {
        "probe": "probe2-fingerprint-lock",
        "fingerprints": fps,
        "tampers_change_fingerprint": matrix["tampers_change_fingerprint"],
        "genuine_fingerprint_stable": matrix["genuine_fingerprint_stable"],
        "locked_compares_pre_change_measure": matrix["locked_tampers_reverted"]
        and matrix["genuine_locked_keep"],
        "product": matrix["product"],
        "reject_all_is_not_credited": matrix["reject_all_is_not_credited"],
        "control_holds": matrix["control_holds"],
    }


def dumps(payload: dict) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)
