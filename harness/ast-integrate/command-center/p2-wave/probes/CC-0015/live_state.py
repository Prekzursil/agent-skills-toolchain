"""Load live program state for CC-0015. Does not inherit PHASE-GRAPH verdicts."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OWNER_DECISIONS = REPO / "command-center" / "OWNER-DECISIONS.md"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
PHASE_GRAPH = REPO / "command-center" / "PHASE-GRAPH.json"
RECEIPTS = REPO / "command-center" / "receipts"


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _owner_question(catalog: dict, qid: str) -> dict | None:
    for row in catalog.get("owner_questions") or []:
        if isinstance(row, dict) and row.get("id") == qid:
            return row
    return None


def receipt_row(uid: str) -> dict | None:
    path = RECEIPTS / f"{uid}.json"
    if not path.is_file():
        return None
    doc = load_json(path)
    if not isinstance(doc, dict):
        return {"path": str(path.relative_to(REPO)).replace("\\", "/"), "state": "UNPARSEABLE"}
    return {
        "path": str(path.relative_to(REPO)).replace("\\", "/"),
        "state": str(doc.get("state") or ""),
        "sentinel": doc.get("sentinel"),
    }


def rel0003_ruling() -> dict:
    od_text = OWNER_DECISIONS.read_text(encoding="utf-8") if OWNER_DECISIONS.is_file() else ""
    has_heading = "## REL-0003" in od_text
    has_answer = "Marking 13 permanently N/A is rejected" in od_text
    packet = receipt_row("REL-0003")
    applied = bool(packet) and str((packet or {}).get("state") or "").upper() == "SUCCESS"
    packet_applied = False
    pkt_doc = load_json(RECEIPTS / "REL-0003.json")
    if isinstance(pkt_doc, dict):
        packet_applied = bool((pkt_doc.get("answer") or {}).get("applied"))
    recorded = (has_heading and has_answer) or packet_applied
    return {
        "recorded": recorded,
        "owner_decisions_heading": has_heading,
        "owner_decisions_answer": has_answer,
        "packet_applied": packet_applied,
        "packet_state": (packet or {}).get("state"),
        "path": "command-center/OWNER-DECISIONS.md",
        "packet_path": "command-center/receipts/REL-0003.json",
        "reask": False,
    }


def release_mode() -> dict:
    od_text = OWNER_DECISIONS.read_text(encoding="utf-8") if OWNER_DECISIONS.is_file() else ""
    catalog = load_json(CATALOG)
    oq3 = _owner_question(catalog, "OQ-3") if isinstance(catalog, dict) else None
    from_md = "PR-ONLY" in od_text and "never a private canary" in od_text.lower()
    from_oq3 = False
    if isinstance(oq3, dict):
        ans = str(oq3.get("answer") or "").upper()
        detail = str(oq3.get("answer_detail") or "").lower()
        from_oq3 = ans.startswith("PR-ONLY") and "never a private canary" in detail
    binding = from_md or from_oq3
    return {
        "binding": "PR-ONLY" if binding else None,
        "from_owner_decisions": from_md,
        "from_catalog_oq3": from_oq3,
        "canary_channel_present": False if binding else None,
    }


def load_live_state() -> dict:
    """Observations from disk. Missing evidence stays None (NOT-CHECKED)."""
    mode = release_mode()
    ruling = rel0003_ruling()
    receipts = {}
    for uid in ("REL-0003", "REL-0004", "REL-0005", "REL-0006"):
        row = receipt_row(uid)
        if row is not None:
            receipts[uid] = row
    rollback = None
    rel6 = receipts.get("REL-0006")
    if isinstance(rel6, dict):
        rollback = str(rel6.get("state") or "").upper() == "SUCCESS"

    verbatim = (REPO / "_USER-PROMPTS.md").is_file() or (
        REPO / "command-center" / "_USER-PROMPTS.md"
    ).is_file()

    pr_only = mode.get("binding") == "PR-ONLY"
    # Under PR-ONLY there is no canary channel and no marketplace release, so
    # those events did not succeed. That is an observation, not a PHASE-GRAPH inherit.
    canary_succeeded = False if pr_only else None
    marketplace = False if pr_only else None

    phase_graph = load_json(PHASE_GRAPH)
    phase_has_preconditions = isinstance(phase_graph, dict) and isinstance(
        phase_graph.get("program_preconditions"), (list, dict)
    )

    return {
        "selected_option_ids": None,
        "dispositions": None,
        "required_tests": None,
        "suites": None,
        "compatibility_cells": None,
        "benchmark": None,
        "vuln_scan_fresh": None,
        "license_scan_fresh": None,
        "docs_code_agree": None,
        "canary_succeeded": canary_succeeded,
        "marketplace_release_succeeded": marketplace,
        "merged_pr": None,
        "receipts": receipts,
        "rollback_tested": rollback,
        "unknowns": None,
        "counts": {},
        "protocol_ids": None,
        "preset_ids": None,
        "rulings": {"REL-0003": ruling},
        "release_mode": mode.get("binding"),
        "canary_channel_present": mode.get("canary_channel_present"),
        "verbatim_spec_present": verbatim,
        "input_presence": {
            "USER_PROMPTS_md": verbatim,
            "OWNER_DECISIONS_md": OWNER_DECISIONS.is_file(),
            "PHASE_GRAPH_json": PHASE_GRAPH.is_file(),
            "PHASE_GRAPH_program_preconditions": phase_has_preconditions,
            "REL-0003": "REL-0003" in receipts,
            "REL-0004": "REL-0004" in receipts,
            "REL-0005": "REL-0005" in receipts,
            "REL-0006": "REL-0006" in receipts,
        },
        "phase_graph_inherited": False,
        "release_mode_detail": mode,
        "rel0003_ruling": ruling,
    }
