#!/usr/bin/env python3
"""Probe 2: semantic search over basic-memory notes.

Synonym-expanded token overlap, not a ledger substring scan. Control: the
planted Program B note must be retrieved by 'durable semantic checkpoint'
even though that exact phrase is absent; zero hits means the check is inert
or is a disguised keyword grep.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft7Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402
import stores as S  # noqa: E402

ART = REPO / "command-center/audit/AUD-0065-ledger-memory-state-inventory.json"
SCHEMA = REPO / "command-center/schema/claim-record.schema.json"
SENTINEL = "SUCCESS:AUD-0065"
COMPLETION = (
    "SUCCESS:AUD-0065 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0065-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    blob = json.dumps(doc)
    if SENTINEL not in blob:
        return fail("sentinel absent")
    if COMPLETION not in blob:
        return fail("completion_sentinel absent")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errs = list(Draft7Validator(schema).iter_errors(doc))
    print(f"schema_errors={len(errs)}")
    if errs:
        return fail(f"schema {errs[0].message}")
    garbage_n = sum(
        1 for _ in Draft7Validator(schema).iter_errors({"totally": "unrelated"})
    )
    print(f"garbage_schema_errors={garbage_n}")
    if garbage_n < 1:
        return fail("schema does not discriminate garbage")

    pack = S.load_stores()
    try:
        inv = E.inventory(pack)
    except RuntimeError as exc:
        return fail(str(exc))
    h = inv["headline"]
    rec_h = doc.get("headline") or {}
    rec_syn = {x["id"] for x in (doc.get("synonym_hits") or []) if isinstance(x, dict)}
    live_syn = {x["id"] for x in inv["synonym_hits"]}
    rec_contra = {x["id"] for x in (doc.get("contradictions") or []) if isinstance(x, dict)}
    live_contra = {x["id"] for x in inv["contradictions"]}
    print(
        json.dumps(
            {
                "probe": "probe2-memory-semantic",
                "unit_id": "AUD-0065",
                "live_known_term_hits": h["memory_known_term_hits"],
                "live_synonym_hits": h["synonym_semantic_hits"],
                "recorded_synonym_hits": len(rec_syn),
                "live_contradictions": h["contradiction_entries"],
                "synonym_exact_substring": h["synonym_exact_substring"],
                "isolation": h["cross_store_isolation"],
                "equal_synonym": rec_syn == live_syn,
                "equal_contra": rec_contra == live_contra,
            },
            sort_keys=True,
        )
    )
    if h["memory_known_term_hits"] < 1:
        return fail("known-present workflow_design produced zero semantic hits")
    if rec_syn != live_syn:
        return fail(f"synonym set mismatch live={sorted(live_syn)} rec={sorted(rec_syn)}")
    if rec_contra != live_contra:
        return fail(
            f"contradiction set mismatch live={sorted(live_contra)} rec={sorted(rec_contra)}"
        )
    for key in (
        "memory_known_term_hits",
        "synonym_semantic_hits",
        "contradiction_entries",
        "live_memory_notes",
        "cross_store_isolation",
        "synonym_exact_substring",
    ):
        if rec_h.get(key) != h.get(key):
            return fail(f"headline {key} disagrees live={h.get(key)} rec={rec_h.get(key)}")
    if h["synonym_exact_substring"]:
        return fail("synonym query is a disguised keyword grep")
    if h["contradiction_entries"] < 1:
        return fail("planted PIN-CI-DECAYS contradiction produced zero flags; detector inert")
    if not h["cross_store_isolation"]:
        return fail("cross-store isolation failed")
    if any("soup-decoy" in i for i in live_syn):
        return fail("soup decoy retrieved")
    print(
        "negative_control verbatim: known term workflow_design HITS; synonym "
        f"query {E.SYNONYM_QUERY!r} HITS {sorted(live_syn)} without exact "
        f"substring; planted contradictions={sorted(live_contra)}; soup decoy "
        "SILENT; ledger nonce does not retrieve from memory."
    )
    print("SUCCESS:AUD-0065-probe2 memory semantic search matches live extraction")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
