#!/usr/bin/env python3
"""Probe 2: bibliographic metadata resolution.

Resolves scholarly identifiers against a local Crossref-shaped catalog and
compares title/author/year to the citation as written. Never opens document
bodies — mechanically different from probe 1.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from detect import load_all_pairs, load_metadata, metadata_resolution, run_detector  # noqa: E402

UNIT = "ADV-0080"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    catalog = load_metadata()
    by_id = {p["id"]: p for p in load_all_pairs()}

    # Probe 2 must not depend on body bytes: identity of the real paper MATCHES
    # even when the attached claim is unsupported (wrong-page fabrication).
    good = metadata_resolution(by_id["plant-real-doi-wrong-page"], catalog)
    if good.get("status") != "MATCH" or not good.get("identity_match"):
        return fail(f"real DOI identity should MATCH, got {good}")

    bad_ident = metadata_resolution(by_id["plant-doi-identity-mismatch"], catalog)
    if bad_ident.get("status") != "MISMATCH":
        return fail(f"identity mismatch should MISMATCH, got {bad_ident}")
    if not {"title", "year", "authors"} <= set(bad_ident.get("mismatches") or []):
        # title+year required; authors expected
        if "title" not in (bad_ident.get("mismatches") or []) or "year" not in (
            bad_ident.get("mismatches") or []
        ):
            return fail(f"identity mismatch fields {bad_ident.get('mismatches')}")

    missing = metadata_resolution(by_id["plant-nonexistent-doi"], catalog)
    if missing.get("status") != "UNRESOLVED":
        return fail(f"nonexistent DOI should UNRESOLVED, got {missing}")

    no_id = metadata_resolution(by_id["plant-genuine-local"], catalog)
    if no_id.get("status") != "NO-IDENTIFIER":
        return fail(f"local genuine should NO-IDENTIFIER, got {no_id}")

    # Independence: flipping body_rel must not change probe-2 output.
    mutated = dict(by_id["plant-real-doi-wrong-page"])
    mutated["body_rel"] = None
    again = metadata_resolution(mutated, catalog)
    if again.get("status") != good.get("status") or again.get("mismatches") != good.get(
        "mismatches"
    ):
        return fail("probe2 changed when body_rel was stripped (not independent)")

    doc = run_detector()
    if doc["planted_recall"] != 1.0:
        return fail(f"recall {doc['planted_recall']}")

    out = {
        "probe": "probe2-metadata-resolution",
        "unit_id": UNIT,
        "pass": True,
        "both_states": True,
        "real_doi_identity": good["status"],
        "identity_mismatch": bad_ident["status"],
        "identity_mismatch_fields": bad_ident.get("mismatches"),
        "nonexistent_doi": missing["status"],
        "local_genuine": no_id["status"],
        "body_independent": True,
        "catalog_records": len(catalog),
        "method": "doi-title-author-year-identity",
        "does_not_read_document_bodies": True,
        "planted_recall": doc["planted_recall"],
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"meta good={good['status']} mismatch={bad_ident['status']} "
        f"unresolved={missing['status']} body_independent=True"
    )
    print(f"SUCCESS:{UNIT}-probe2 metadata identity; body-independent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
