#!/usr/bin/env python3
"""Probe 2: NOT-CHECKED is UNCOVERED; CONFIRMED/REFUTED is COVERED; no self-ref.

Also remaps three questions independently and checks the live artifact
against a fresh disk compute.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
from matrix import (  # noqa: E402
    artifact_matrix_fields,
    compute_matrix,
    question_cells,
    write_scratch_receipt,
)
from questions import (  # noqa: E402
    ELEVEN,
    SELF_ID,
    first_unit_for_each_question,
    load_catalog_units,
)

CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
ART = REPO / "command-center/receipts/BLD-0063.json"
LIVE_RECEIPTS = REPO / "command-center/receipts"


def _cov(matrix: dict) -> dict[str, str]:
    return {row["question"]: row["coverage"] for row in matrix["questions"]}


def main() -> int:
    catalog_units = load_catalog_units(CATALOG)
    first = first_unit_for_each_question(catalog_units)
    q_nc, q_conf, q_ref = ELEVEN[0][1], ELEVEN[1][1], ELEVEN[2][1]
    u_nc, u_conf, u_ref = first[q_nc], first[q_conf], first[q_ref]

    with tempfile.TemporaryDirectory(prefix="bld0063-p2-") as tmp:
        receipts = Path(tmp)
        write_scratch_receipt(receipts, u_nc, q_nc, ["NOT-CHECKED"])
        write_scratch_receipt(receipts, u_conf, q_conf, ["CONFIRMED"])
        write_scratch_receipt(receipts, u_ref, q_ref, ["REFUTED"])
        write_scratch_receipt(
            receipts,
            SELF_ID,
            q_nc,
            ["CONFIRMED"],
            extra={"note": "self-receipt must not cover"},
        )
        mixed = compute_matrix(CATALOG, receipts)
        cov = _cov(mixed)
        print(f"not_checked_only {q_nc}={cov.get(q_nc)} unit={u_nc}")
        print(f"confirmed {q_conf}={cov.get(q_conf)} unit={u_conf}")
        print(f"refuted {q_ref}={cov.get(q_ref)} unit={u_ref}")
        if cov.get(q_nc) != "UNCOVERED":
            print("FAILED:BLD-0063-probe2 NOT-CHECKED-only classified COVERED")
            return 1
        if cov.get(q_conf) != "COVERED":
            print("FAILED:BLD-0063-probe2 CONFIRMED classified UNCOVERED")
            return 1
        if cov.get(q_ref) != "COVERED":
            print("FAILED:BLD-0063-probe2 REFUTED classified UNCOVERED")
            return 1
        covering_nc = [
            r["id"]
            for row in mixed["questions"]
            if row["question"] == q_nc
            for r in row["receipt_units"]
        ]
        if SELF_ID in covering_nc:
            print("FAILED:BLD-0063-probe2 self-id appeared in receipt_units")
            return 1
        if mixed["receipts_read"] != 3:
            print(
                "FAILED:BLD-0063-probe2 self-receipt was counted "
                f"receipts_read={mixed['receipts_read']}"
            )
            return 1

        write_scratch_receipt(receipts, u_nc, q_nc, ["NOT-CHECKED", "CONFIRMED"])
        both = compute_matrix(CATALOG, receipts)
        both_cov = _cov(both)
        print(f"mixed_not_checked_plus_confirmed {q_nc}={both_cov.get(q_nc)}")
        if both_cov.get(q_nc) != "COVERED":
            print("FAILED:BLD-0063-probe2 false negative on mixed CONFIRMED")
            return 1

        remap_ok = 0
        for label in (q_nc, q_conf, q_ref):
            live_row = next(r for r in both["questions"] if r["question"] == label)
            print(f"scratch_control {live_row['id']} {label}={live_row['coverage']}")
            remap_ok += 1
        if remap_ok != 3:
            print("FAILED:BLD-0063-probe2 independent remap count")
            return 1

    if not ART.is_file():
        print("FAILED:BLD-0063-probe2 live artifact missing")
        return 1
    live_doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(live_doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:BLD-0063-probe2 self-declared {live_doc.get('state')}")
        return 1
    if "SUCCESS:BLD-0063" not in ART.read_text(encoding="utf-8"):
        print("FAILED:BLD-0063-probe2 sentinel absent")
        return 1
    fields = artifact_matrix_fields(live_doc)
    if fields.get("self_reference_excluded") is not True:
        print("FAILED:BLD-0063-probe2 self_reference_excluded not true")
        return 1

    recomputed = compute_matrix(CATALOG, LIVE_RECEIPTS)
    art_uncovered = list(fields.get("uncovered_questions") or [])
    live_uncovered = list(recomputed["uncovered_questions"])
    print(f"live_uncovered={live_uncovered}")
    print(f"artifact_uncovered={art_uncovered}")
    if art_uncovered != live_uncovered:
        print("FAILED:BLD-0063-probe2 artifact uncovered set drifted from disk")
        return 1
    art_read = fields.get("receipts_read")
    live_read = recomputed["receipts_read"]
    print(f"receipts_read artifact={art_read} live={live_read}")
    if art_read != live_read:
        print("FAILED:BLD-0063-probe2 receipts_read drift")
        return 1
    if fields.get("receipts_expected") != 62:
        print("FAILED:BLD-0063-probe2 receipts_expected is not 62")
        return 1

    art_questions = {row["question"]: row for row in fields.get("questions") or []}
    for label in (q_nc, q_conf, q_ref):
        live_row = next(r for r in recomputed["questions"] if r["question"] == label)
        art_row = art_questions.get(label) or {}
        print(
            f"remap {live_row['id']} {label}="
            f"{live_row['coverage']} artifact={art_row.get('coverage')}"
        )
        if live_row["coverage"] != art_row.get("coverage"):
            print("FAILED:BLD-0063-probe2 independent live remap drifted")
            return 1
        art_ids = [r.get("id") for r in art_row.get("receipt_units") or []]
        live_ids = [r.get("id") for r in live_row.get("receipt_units") or []]
        if art_ids != live_ids:
            print(
                "FAILED:BLD-0063-probe2 independent live remap receipt_units "
                f"{label} artifact={art_ids} live={live_ids}"
            )
            return 1

    cells = fields.get("cells") or []
    if len(cells) < 5:
        print(f"FAILED:BLD-0063-probe2 cells minItems 5 got {len(cells)}")
        return 1
    by_id = {c.get("id"): c for c in cells if isinstance(c, dict)}
    for row in question_cells(recomputed):
        cell = by_id.get(row["id"])
        if not isinstance(cell, dict):
            print(f"FAILED:BLD-0063-probe2 missing cell {row['id']}")
            return 1
        if cell.get("verdict") != row["verdict"]:
            print(
                f"FAILED:BLD-0063-probe2 cell {row['id']} "
                f"{cell.get('verdict')} != {row['verdict']}"
            )
            return 1
    disk_cell = by_id.get("CTRL-LIVE-DISK") or {}
    if f"receipts_read={live_read}" not in str(disk_cell.get("evidence") or ""):
        print("FAILED:BLD-0063-probe2 CTRL-LIVE-DISK receipts_read drifted")
        return 1

    for row in fields.get("questions") or []:
        for ru in row.get("receipt_units") or []:
            if ru.get("id") == SELF_ID:
                print("FAILED:BLD-0063-probe2 live matrix counted self")
                return 1
    print("SUCCESS:BLD-0063-probe2 verdict rules and live remap")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
