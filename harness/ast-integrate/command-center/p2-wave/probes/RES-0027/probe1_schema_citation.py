#!/usr/bin/env python3
"""Probe 1: block schema from captured source, not from docs.

Rehashes GitHub Contents API vs raw bytes (structured identity) and resolves
packages/config-yaml/src/schemas/index.ts:194 in the captured snapshot.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check as C  # noqa: E402


def main() -> int:
    if not C.ART.is_file():
        print("FAILED:RES-0027-probe1 artifact missing")
        return 1
    doc = C.load_art()
    errs = C.validate_source_citation(doc)
    # Length-1 singleton is visible in source; docs do not independently
    # state it, so the artifact must not promote it to E2 measured fact.
    for claim in doc.get("claims") or []:
        mech = str(claim.get("canonical_mechanism") or "")
        if "length(1)" in mech or "length 1" in mech.lower():
            if str(claim.get("evidence_tier") or "") in C.MEASURED_TIERS:
                errs.append(f"{claim.get('id')}:length-1-promoted-to-measured")
            if claim.get("citable_as_measured_fact") is True:
                errs.append(f"{claim.get('id')}:length-1-cited-as-measured-fact")
    schema = (C.SNAP / "github-raw-block-schema.ts").read_text(encoding="utf-8")
    lines = schema.splitlines()
    print(
        json.dumps(
            {
                "blockSchema_line": C.BLOCK_SCHEMA_LINE,
                "line_text": lines[C.BLOCK_SCHEMA_LINE - 1],
                "api_raw_identity_ok": not any(
                    e.startswith("api-raw-mismatch") for e in errs
                ),
                "errors": errs,
            },
            indent=2,
            sort_keys=True,
        )
    )
    if errs:
        print("FAILED:RES-0027-probe1 " + "; ".join(errs[:8]))
        return 1
    print(
        "SUCCESS:RES-0027-probe1 blockSchema "
        "packages/config-yaml/src/schemas/index.ts:194 source-cited "
        "GitHub-API-raw-identity"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
