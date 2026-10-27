"""Contract checker for the WFA-0065 MechanismRecord.

Live artifact must pass. Mutants (no falsification; illegal IR kind adopted)
must fail. Probe 1 is the both-states control.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from classify import ADOPTED, ALREADY, OOS, SPECULATIVE, classify_all
from ir import IR_KINDS, IR_SOURCE
from transfers import TRANSFERS, unknown_kinds

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures" / "source_protocols.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
BUCKETS = (
    "evidence_backed_transfers",
    "speculative_transfers",
    "already_specified_in_catalog",
    "out_of_scope",
)
BUCKET_DISP = {
    "evidence_backed_transfers": ADOPTED,
    "speculative_transfers": SPECULATIVE,
    "already_specified_in_catalog": ALREADY,
    "out_of_scope": OOS,
}


def _load_protocols() -> dict[str, dict]:
    doc = json.loads(FIXTURES.read_text(encoding="utf-8"))
    return {p["id"]: p for p in doc.get("protocols") or []}


def _all_rows(doc: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in BUCKETS:
        for row in doc.get(key) or []:
            if isinstance(row, dict):
                rows.append(row)
    return rows


def check_artifact(doc: dict[str, Any], scan: dict[str, Any]) -> tuple[bool, list[str]]:
    errs: list[str] = []
    if not isinstance(doc, dict):
        return False, ["not-an-object"]
    if str(doc.get("record_type") or "") != "MechanismRecord":
        errs.append("record_type-not-MechanismRecord")
    if str(doc.get("unit_id") or "") != "WFA-0065":
        errs.append("unit_id")
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        errs.append(f"self-declared:{doc.get('state')}")
    text = json.dumps(doc, sort_keys=True)
    if "SUCCESS:WFA-0065" not in text:
        errs.append("sentinel-absent")
    if str(doc.get("sentinel") or "") != "SUCCESS:WFA-0065":
        errs.append("sentinel-field")

    eb = doc.get("evidence_backed_transfers") or []
    sp = doc.get("speculative_transfers") or []
    if not isinstance(eb, list) or not isinstance(sp, list):
        errs.append("buckets-not-lists")
        return False, errs
    if not eb:
        errs.append("no-evidence-backed-transfers")
    if not sp:
        errs.append("no-speculative-transfers")

    ids_eb = [r.get("id") for r in eb if isinstance(r, dict)]
    ids_sp = [r.get("id") for r in sp if isinstance(r, dict)]
    overlap = set(ids_eb) & set(ids_sp)
    if overlap:
        errs.append(f"speculative-mixed-into-evidence-backed:{sorted(overlap)}")

    expected = classify_all(scan)
    live_disp: dict[str, str] = {}
    for key, want in BUCKET_DISP.items():
        for row in doc.get(key) or []:
            if not isinstance(row, dict):
                errs.append(f"{key}:non-object")
                continue
            tid = str(row.get("id") or "")
            live_disp[tid] = str(row.get("disposition") or "")
            if row.get("disposition") != want:
                errs.append(f"{tid}:bucket {key} vs disposition {row.get('disposition')}")

    for tid, want in expected.items():
        got = live_disp.get(tid)
        if got != want:
            errs.append(f"{tid}:expected {want} got {got}")

    protocols = _load_protocols()
    by_id = {t["id"]: t for t in TRANSFERS}
    for row in _all_rows(doc):
        tid = str(row.get("id") or "")
        src = by_id.get(tid)
        mapping = row.get("mapping_table") or []
        if not mapping:
            errs.append(f"{tid}:empty-mapping")
        for m in mapping:
            kind = str(m.get("ir_kind") or "")
            if row.get("disposition") == ADOPTED and kind not in IR_KINDS:
                errs.append(f"{tid}:adopted-unknown-ir-kind:{kind}")
        fals = row.get("falsification") or {}
        if not isinstance(fals, dict) or not fals.get("attempted"):
            errs.append(f"{tid}:falsification-missing")
        elif not str(fals.get("source_property_that_does_not_hold") or "").strip():
            errs.append(f"{tid}:falsification-empty")
        proto_id = str(row.get("source_protocol_id") or "")
        if proto_id not in protocols:
            errs.append(f"{tid}:source-protocol-absent:{proto_id}")
        else:
            quote = str(protocols[proto_id].get("quote") or "")
            if quote and quote not in json.dumps(row):
                # artifact must carry the source quote so the mapping is anchored
                if quote not in str(row.get("source_quote") or ""):
                    errs.append(f"{tid}:source-quote-not-carried")
        if src and unknown_kinds(src) and row.get("disposition") == ADOPTED:
            errs.append(f"{tid}:inexpressible-adopted")
        if row.get("disposition") == ADOPTED and not row.get("ir_expressible"):
            errs.append(f"{tid}:adopted-not-expressible")

    ir = doc.get("ir") or {}
    kinds = set(ir.get("kinds") or [])
    if kinds != set(IR_KINDS):
        errs.append("ir-kinds-mismatch")
    if ir.get("spec_artifact_present") is True:
        # WFA-0044 artifact is absent; claiming it present is an overclaim
        if (REPO / IR_SOURCE["artifact_path"]).is_file() is False:
            errs.append("overclaim-ir-spec-present")

    voc = doc.get("vocabulary") or {}
    vocab_path = REPO / "command-center/wfa/WFA-0058-mechanism-vocabulary.json"
    if voc.get("WFA-0058_present") is True and not vocab_path.is_file():
        errs.append("overclaim-vocabulary-present")

    return not errs, errs
