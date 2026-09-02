#!/usr/bin/env python3
"""Named probe 1: listing is the archive infolist, not the inclusion rules."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from auditor import audit_archive, enumerate_zip, file_member_count, load_rules
from constants import (
    CANDIDATE_ZIP_REL,
    EXTRA_MEMBER,
    OUTPUT_REL,
    QUESTION,
    REPO,
    SENTINEL,
    UNIT_ID,
)
from contract import domain, schema_errors, schema_rejects_garbage
from pack import write_zip
from scenario import candidate_files, write_enumeration_proof_zip


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0102-probe1 {msg}")
    return 1


def main() -> int:
    art_path = REPO / OUTPUT_REL
    if not art_path.is_file() or art_path.stat().st_size <= 0:
        return fail("confirmation artifact missing")
    text = art_path.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable:{type(exc).__name__}")
    if doc.get("unit_id") != UNIT_ID:
        return fail(f"unit_id {doc.get('unit_id')}")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    payload = domain(doc)
    if payload.get("question") != QUESTION:
        return fail("question-mismatch")
    enum = payload.get("enumeration") or {}
    if enum.get("listed_from_archive") is not True:
        return fail("listed_from_archive is not true")
    if enum.get("listed_from_inclusion_rules") is not False:
        return fail("listed_from_inclusion_rules must be false")
    if enum.get("listed_from_source_tree") is not False:
        return fail("listed_from_source_tree must be false")
    if enum.get("method") != "zipfile.ZipFile.infolist":
        return fail("method is not zipfile.ZipFile.infolist")
    vacuous = schema_rejects_garbage()
    if vacuous:
        return fail(vacuous)
    errs = schema_errors(doc)
    if errs:
        return fail("schema-invalid " + "; ".join(errs[:8]))

    rules = load_rules()
    with tempfile.TemporaryDirectory(prefix="cnf0102-p1-") as tmp:
        rebuilt = Path(tmp) / "candidate.zip"
        files = candidate_files()
        write_zip(files, rebuilt)
        live_entries = enumerate_zip(rebuilt)
        live_audit = audit_archive(rebuilt, rules)
        if live_audit["totals"]["entry_count"] != file_member_count(rebuilt):
            return fail("rebuilt listing count != infolist")
        art_index = {
            e["path"]: e["uncompressed_bytes"] for e in payload.get("entries") or []
        }
        live_index = {e["path"]: e["uncompressed_bytes"] for e in live_entries}
        if art_index != live_index:
            return fail(
                f"artifact listing != rebuilt archive listing "
                f"art={sorted(art_index)} live={sorted(live_index)}"
            )
        if len(live_entries) != len(files):
            return fail("archive member count != packed file dict")
        if len(live_entries) == len(rules["allowlist_globs"]):
            return fail("listing count equals glob count; may be listing rules")

        proof = Path(tmp) / "proof.zip"
        write_enumeration_proof_zip(rebuilt, proof)
        proof_paths = {e["path"] for e in enumerate_zip(proof)}
        if EXTRA_MEMBER not in proof_paths:
            return fail("extra member not in archive listing")
        proof_audit = audit_archive(proof, rules)
        extra = next(
            e for e in proof_audit["entries"] if e["path"] == EXTRA_MEMBER
        )
        if "allowlist-miss" not in extra["flags"]:
            return fail("extra member not flagged allowlist-miss")
        if proof_audit["totals"]["entry_count"] != file_member_count(proof):
            return fail("proof listing count != infolist")

    shipped = REPO / CANDIDATE_ZIP_REL
    if shipped.is_file():
        shipped_index = {
            e["path"]: e["uncompressed_bytes"] for e in enumerate_zip(shipped)
        }
        if shipped_index != art_index:
            return fail("on-disk candidate zip listing != artifact entries")

    print(
        f"listed_from_archive=True entries={len(art_index)} "
        f"extra_member_in_proof=True allowlist_globs={len(rules['allowlist_globs'])}"
    )
    print("SUCCESS:CNF-0102-probe1 archive-enumerated listing matches artifact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
