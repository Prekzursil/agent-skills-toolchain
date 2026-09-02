#!/usr/bin/env python3
"""Shared live pipeline for emit + named probes (compute first, then open the sealed lane)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent

import adjudicate  # noqa: E402
import blind  # noqa: E402
import gaming  # noqa: E402
import recompute as R  # noqa: E402
import substrate as S  # noqa: E402


def live_independent() -> dict[str, Any]:
    """Collect records, score, detect gaming. Does not import fusion_lane."""
    check = blind.is_blind()
    if not check["ok"]:
        raise RuntimeError(f"recompute module is not blind: {check}")
    records = S.collect_raw_records()
    if not S.budget_parity(records):
        raise RuntimeError("budget parity failed")
    if not S.failed_arms_retained(records):
        raise RuntimeError("failed arms dropped")
    floor = S.variance_floor(records)
    if not floor["measured"]:
        raise RuntimeError("variance floor unmeasured")
    game = gaming.detect()
    if not game["hits"]["fused_gaming"]:
        raise RuntimeError("planted gaming workflow not caught")
    if not game["genuine_static_silent"]:
        raise RuntimeError("gaming detector false-positive on source_alpha")
    if not game["perturbation"]["genuine_holds"]:
        raise RuntimeError("perturbation broke the genuine workflow")
    if not game["perturbation"]["gaming_collapses"]:
        raise RuntimeError("perturbation did not collapse gaming")
    independent = R.recompute(
        records,
        n_cases=len(S.CASES),
        source_ids=S.SOURCE_IDS,
        fused_ids=S.FUSED_IDS,
        floor=float(floor["floor"]),
        gaming_hits=game["hits"],
    )
    if independent["read_fusion_summary"] is not False:
        raise RuntimeError("recompute claimed to have read a fusion summary")
    return {
        "blind": check,
        "records": records,
        "floor": floor,
        "gaming": game,
        "independent": independent,
    }


def reproduce_triple(records: list[dict]) -> list[dict]:
    by_id = {
        r["run_id"]: r
        for r in records
        if r.get("control") != "same-workflow-twice"
    }
    rows = []
    for wf, cid in S.REPRODUCE_TRIPLE:
        live = S.run_one(wf, S.case_by_id(cid))
        recorded = by_id[live["run_id"]]
        rows.append(
            {
                "run_id": live["run_id"],
                "workflow_id": wf,
                "case_id": cid,
                "live_input_hash": live["input_hash"],
                "recorded_input_hash": recorded["input_hash"],
                "input_hash_match": live["input_hash"] == recorded["input_hash"],
                "live_oracle_pass": live["oracle_pass"],
                "recorded_oracle_pass": recorded["oracle_pass"],
                "oracle_match": live["oracle_pass"] == recorded["oracle_pass"],
                "live_artifact": live["artifact"],
                "recorded_artifact": recorded["artifact"],
            }
        )
    return rows


def open_sealed_and_adjudicate(independent: dict) -> dict[str, Any]:
    """Open the sealed fusion-lane scorer only after independent verdicts exist."""
    import fusion_lane  # local import: independent path never loads this

    records = independent["records"]
    sealed = fusion_lane.naive_verdicts(records, S.FUSED_IDS)
    if sealed["canary"] != fusion_lane.CANARY:
        raise RuntimeError("fusion-lane canary missing")
    evidence = {
        "fused_complement": {
            "sufficient": True,
            "independent_supported": True,
            "fusion_supported": True,
            "notes": "both probes PASS; complementarity on case.delta is in the raw records",
        },
        "fused_worse": {
            "sufficient": True,
            "independent_supported": True,
            "fusion_supported": True,
            "notes": "both probes FAIL; fused_worse is below both sources",
        },
        "fused_gaming": {
            "sufficient": True,
            "independent_supported": True,
            "fusion_supported": False,
            "notes": (
                "independent VOID from static oracle-constants plus perturbation "
                "collapse; fusion-lane PASS is naive pass-rate only"
            ),
        },
        "fused_absent": {
            "sufficient": False,
            "independent_supported": False,
            "fusion_supported": False,
            "notes": "no raw records for this arm",
        },
    }
    independent_plus = list(independent["independent"]["verdicts"]) + [
        {"workflow_id": "fused_absent", "verdict": "REFUTED", "reason": "no raw records"}
    ]
    fusion_plus = list(sealed["verdicts"]) + [
        {"workflow_id": "fused_absent", "verdict": "PASS"}
    ]
    votes = {
        "fused_gaming": {"codex": "PASS", "claude": "VOID"},
        "fused_absent": {"codex": "PASS", "claude": "PASS"},
    }
    split = adjudicate.resolve(independent_plus, fusion_plus, evidence, votes=votes)
    chosen = {row["workflow_id"]: row for row in split["rows"]}
    for key, want in (
        ("fused_complement", "PASS"),
        ("fused_worse", "FAIL"),
        ("fused_gaming", "VOID"),
        ("fused_absent", "REFUTED"),
    ):
        if chosen[key]["chosen"] != want:
            raise RuntimeError(f"{key} chosen={chosen[key]['chosen']} want={want}")
    if chosen["fused_gaming"]["which_side_right"] != "independent":
        raise RuntimeError("split not awarded to independent probe")
    if not chosen["fused_gaming"]["votes_ignored"]:
        raise RuntimeError("votes were consulted")
    return {"sealed": sealed, "split": split, "chosen": chosen}


def verdict_map(rows: list[dict]) -> dict[str, str]:
    return {r["workflow_id"]: r["verdict"] for r in rows}


def freeze_records(records: list[dict]) -> list[dict]:
    out = []
    for row in records:
        item = dict(row)
        item.pop("wall_ns", None)
        out.append(item)
    return out


def dump_json(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")
