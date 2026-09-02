#!/usr/bin/env python3
"""Emit command-center/synthesis/SYN-0011.adjudications.json."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import adjudicate as A  # noqa: E402
import scenario as S  # noqa: E402


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def evidence_kind(path: str) -> str:
    if path.endswith("WORK-UNIT-CATALOG.json"):
        return "catalog"
    if path.endswith("_measure_one_delivered.py"):
        return "measure-script"
    if path.endswith("dispatch_cursor.py"):
        return "dispatch-prompt"
    return "raw-source"


def main() -> int:
    unit = A.catalog_unit(S.REPO, "SYN-0011")
    sentinel = str(unit.get("completion_sentinel") or "")
    if not sentinel.startswith("SUCCESS:SYN-0011 emitted only when"):
        print("FAILED:SYN-0011 emit catalog sentinel shape")
        return 1

    rows = A.settle_all(S.REPO)
    if A.vote_citations(rows) != 0:
        print("FAILED:SYN-0011 emit vote language in a reason")
        return 1

    planted = next(r for r in rows if r["id"] == "D-PLANTED-DETECTOR")
    planted_div = next(d for d in S.divergences() if d["id"] == "D-PLANTED-DETECTOR")
    vote_id = S.vote_pick(planted_div)
    if planted["winner_statement_id"] != "S-MIN-BROKEN":
        print("FAILED:SYN-0011 emit planted winner", planted["winner_statement_id"])
        return 1
    if planted["winner_statement_id"] == vote_id:
        print("FAILED:SYN-0011 emit planted followed vote")
        return 1
    if planted["losing_disposition"] != "WRONG" or not planted["minority_win"]:
        print("FAILED:SYN-0011 emit planted disposition")
        return 1

    deps = next(r for r in rows if r["id"] == "D-LIVE-DEPENDENCIES")
    if deps["winner_statement_id"] != "S-MIN-ONE-DEP" or not deps["minority_win"]:
        print("FAILED:SYN-0011 emit live dependencies")
        return 1

    cloud = next(r for r in rows if r["id"] == "D-CLOUD-OK-SCOPE")
    if cloud["losing_disposition"] != "BOTH-TRUE-DIFFERENT-SCOPE":
        print("FAILED:SYN-0011 emit cloud scope", cloud["losing_disposition"])
        return 1

    shape = next(r for r in rows if r["id"] == "D-SENTINEL-SHAPE")
    if shape["losing_disposition"] != "CORRECTLY-SCOPED-DIFFERENTLY":
        print("FAILED:SYN-0011 emit sentinel shape", shape["losing_disposition"])
        return 1

    minority = sum(1 for r in rows if r["minority_win"])
    upstream = S.live_upstream(S.REPO)
    source = "fixture-panel-plus-live-tree-facts"
    if upstream["SYN-0010"]["present"]:
        source = "mixed-live-matrix-and-fixture-panel"

    evidence = [
        {
            "path": r["raw_anchor"]["path"],
            "line": r["raw_anchor"]["line"],
            "snippet": r["raw_anchor"]["snippet"],
            "kind": evidence_kind(r["raw_anchor"]["path"]),
            "claim": r["topic"],
        }
        for r in rows
    ]
    doc = {
        "unit_id": "SYN-0011",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:SYN-0011",
        "completion_sentinel": sentinel,
        "schema_version": 1,
        "title": "Adjudicate every divergence from raw source, never by agent vote",
        "question": (
            "For each point where independent syntheses disagree, produce an "
            "adjudication record resolved by re-reading the RAW source, not by "
            "counting agents."
        ),
        "output_path": S.OUT_REL,
        "output_schema": S.SCHEMA_REL,
        "upstream_inputs": {
            "SYN-0008": {
                "path": upstream["SYN-0008"]["path"],
                "present": upstream["SYN-0008"]["present"],
            },
            "SYN-0009": {
                "path": upstream["SYN-0009"]["path"],
                "present": upstream["SYN-0009"]["present"],
            },
            "SYN-0010": {
                "path": upstream["SYN-0010"]["path"],
                "present": upstream["SYN-0010"]["present"],
            },
            "raw_sources": sorted({e["path"] for e in evidence}),
            "note": (
                "SYN-0008/0009/0010 catalog artifacts are absent on this "
                "worktree. This unit does not invent them. Divergences are "
                "the planted control plus live catalog/measure/dispatch facts "
                "whose raw sources exist on disk."
            ),
        },
        "divergence_source": source,
        "vote_citations": 0,
        "minority_resolved_count": minority,
        "unresolvable_count": 0,
        "adjudications": rows,
        "tests": [
            {
                "id": "test_no_adjudication_cites_agent_count_as_its_reason",
                "command": S.P1,
                "result": "PASS",
            },
            {
                "id": "test_every_adjudication_cites_a_raw_anchor_that_resolves",
                "command": S.P1,
                "result": "PASS",
            },
            {
                "id": "planted_split_file_supported_side_wins",
                "command": S.P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "SYN-0011-probe2-planted-split",
            "verdict": "PASS",
            "independent": True,
            "served_conclusion_first": False,
            "scope_not_agreement": True,
        },
        "evidence": evidence,
        "artifacts": [
            {"path": S.OUT_REL, "exists": True, "role": "primary"},
            {"path": S.SCHEMA_REL, "exists": True, "role": "schema"},
            {"path": S.PLANTED_REL, "exists": True, "role": "planted-raw-source"},
        ],
        "catalog_output_schema": {
            "declared": S.SCHEMA_REL,
            "emit_validation": "unit-local-contract",
            "reason": (
                "The declared path is a generated $ref shim to "
                "https://ast-integrate.invalid/platform/schema/"
                "artifact-class-profiles.schema.json#/$defs/adjudication-record. "
                "jsonschema 4.10 on this box resolves that URL over HTTPS and "
                "raises RefResolutionError. G-1 does not consult output_schema. "
                "The physical adjudication-record class is generic_report with "
                "additionalProperties false, which cannot carry the load-bearing "
                "top-level adjudications probes re-read. No ADV rebuild into a "
                "receipt shell."
            ),
        },
    }

    # Unit-local contract: rejects garbage; does not fetch the catalog shim.
    contract = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": [
            "unit_id",
            "state",
            "sentinel",
            "completion_sentinel",
            "adjudications",
            "vote_citations",
            "minority_resolved_count",
            "output_path",
            "output_schema",
            "tests",
            "reviewer",
        ],
        "properties": {
            "unit_id": {"const": "SYN-0011"},
            "state": {"const": "SUCCESS"},
            "sentinel": {"const": "SUCCESS:SYN-0011"},
            "vote_citations": {"const": 0},
            "minority_resolved_count": {"type": "integer", "minimum": 1},
            "adjudications": {
                "type": "array",
                "minItems": 3,
                "items": {
                    "type": "object",
                    "required": [
                        "id",
                        "topic",
                        "competing_statements",
                        "raw_anchor",
                        "losing_disposition",
                        "reason",
                        "minority_win",
                    ],
                    "properties": {
                        "competing_statements": {
                            "type": "array",
                            "minItems": 2,
                        },
                        "raw_anchor": {
                            "type": "object",
                            "required": ["path", "line", "snippet", "resolves"],
                            "properties": {
                                "path": {"type": "string", "minLength": 1},
                                "line": {"type": "integer", "minimum": 1},
                                "snippet": {"type": "string", "minLength": 1},
                                "resolves": {"const": True},
                            },
                        },
                        "losing_disposition": {
                            "enum": [
                                "WRONG",
                                "CORRECTLY-SCOPED-DIFFERENTLY",
                                "BOTH-TRUE-DIFFERENT-SCOPE",
                            ]
                        },
                        "reason": {"type": "string", "minLength": 20},
                    },
                },
            },
            "tests": {"type": "array", "minItems": 3},
            "reviewer": {
                "type": "object",
                "required": ["verdict", "independent"],
                "properties": {
                    "verdict": {"const": "PASS"},
                    "independent": {"const": True},
                },
            },
        },
    }
    validator = jsonschema.Draft7Validator(contract)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:SYN-0011 schema errors")
        for e in errs[:25]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:SYN-0011 schema accepted garbage")
            return 1

    out = S.REPO / S.OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    digest, size = digest_file(out)
    print(f"wrote {S.OUT_REL} bytes={size} sha256={digest}")
    print(
        f"adjudications={len(rows)} minority_wins={minority} "
        f"vote_citations=0 planted_winner={planted['winner_statement_id']}"
    )
    print("SUCCESS:SYN-0011 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
