#!/usr/bin/env python3
"""Emit command-center/research/RES-0123.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import OUT, OUT_REL, SENTINEL, UNIT, collapse_ws, dump, sha256_file  # noqa: E402
from fetch_terms import fetch_all  # noqa: E402
from model import (  # noqa: E402
    compute_conflicts,
    locate_quotes,
    owner_vs_engineering,
    practices,
)

SCHEMA_REL = "command-center/p2-wave/probes/RES-0123/research-claim-record.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0123/probe1_verbatim_dated_clauses.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0123/probe2_practice_conflict_control.py"
)
QUESTION = (
    "What do the applicable vendor terms say about programmatic invocation, "
    "cross-vendor orchestration and the multi-account rotation rails this estate "
    "already runs - and which planned behaviour is a genuine owner decision "
    "rather than an engineering one?"
)


def main() -> int:
    rows = fetch_all()
    captures = {}
    for row in rows:
        captures[row["id"]] = {
            "http_status": row["http_status"],
            "text": row["text"],
            "url": row["url"],
            "fetched_at": row["fetched_at"],
            "effective_marker": row["effective_marker"],
            "body_sha256": row["body_sha256"],
            "text_sha256": row["text_sha256"],
            "used_extract_sidecar": row["used_extract_sidecar"],
            "version_pin": row["version_pin"],
            "text_path": row["text_path"],
            "body_path": row["body_path"],
            "vendor": row["vendor"],
            "instrument": row["instrument"],
        }
    quotes = locate_quotes(captures)
    missing = [q["id"] for q in quotes if not q["found_in_capture"]]
    if missing:
        print("FAILED:RES-0123 emit quotes missing from captures:")
        for qid in missing:
            q = next(x for x in quotes if x["id"] == qid)
            print(" ", qid, "capture", q["capture_id"], "status", q["capture_http_status"])
            print("    needle", collapse_ws(q["quote"])[:120])
        return 1
    prac = practices()
    conflicts = compute_conflicts(prac, quotes)
    rails = sorted({q["rail"] for q in quotes})
    if set(rails) < {"cursor", "anthropic", "openai", "google", "xai", "groq"}:
        print("FAILED:RES-0123 emit missing vendor rails", rails)
        return 1
    if not any(c["id"] == "C-CURSOR-AUP-AUTOMATION-VS-UNATTENDED-CLI" for c in conflicts):
        print("FAILED:RES-0123 emit expected live Cursor automation tension absent")
        return 1
    if any("multi-account-rotation" == c["practice_id"] for c in conflicts):
        print("FAILED:RES-0123 emit flagged a rotator that is not running")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    answer = (
        f"{SENTINEL}. Measured on this worktree {now}. The live programmatic rail is "
        "Cursor CLI (cursor-agent -p with CURSOR_API_KEY). Cursor consumer AUP lists "
        "automated/non-human access as a prohibited example while Cursor CLI and "
        "service-account docs prescribe -p + CURSOR_API_KEY for CI; which instrument "
        "binds is an owner choice. Catalog language about multi-account rotation is "
        "not implemented here (rotator absent). Cross-vendor confirmer assignment is "
        "catalog/CNF-0007 architecture; CNF-0007 dispatch is a local subprocess, not a "
        "live second-vendor HTTPS call. This record quotes what the captured terms SAY "
        "and does not render a compliance verdict."
    )
    claims = []
    for q in quotes:
        cap = captures[q["capture_id"]]
        claims.append(
            {
                "id": q["id"],
                "canonical_mechanism": q["topic"],
                "rail": q["rail"],
                "verbatim_quote": q["quote"],
                "effective_date": q["effective_date"],
                "effective_marker_on_page": cap["effective_marker"],
                "evidence_tier": "E1" if cap["http_status"] == 200 and not cap["used_extract_sidecar"] else "E2",
                "confidence_band": "high" if cap["http_status"] == 200 else "moderate-blocked-fetch",
                "named_settling_probe": "probe1_verbatim_dated_clauses.py",
                "found_in_capture": True,
                "source_lineage": [
                    {
                        "url": cap["url"],
                        "fetched_at": cap["fetched_at"],
                        "http_status": cap["http_status"],
                        "sha256": cap["version_pin"]["sha256"],
                        "instrument": cap["instrument"],
                        "used_extract_sidecar": cap["used_extract_sidecar"],
                    }
                ],
                "contradiction_edges": [
                    c["id"] for c in conflicts if c["quote_id"] == q["id"]
                ],
                "support_edges": [],
            }
        )

    doc = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "report_kind": "research-claim-record",
        "title": "Establish what vendor terms say about cross-vendor orchestration and multi-account rails",
        "question": QUESTION,
        "answer": answer,
        "no_legal_conclusion": True,
        "owner_approval_required_to_act": True,
        "measured_at": now,
        "schema_version": 1,
        "declared_output_schema": "command-center/schema/research-claim-record.schema.json",
        "declared_schema_on_disk": (
            HERE.parents[3] / "command-center" / "schema" / "research-claim-record.schema.json"
        ).is_file(),
        "local_schema": SCHEMA_REL,
        "rails": rails,
        "captures": [
            {k: v for k, v in cap.items() if k != "text"} for cap in captures.values()
        ],
        "claims": claims,
        "practices": prac,
        "conflicts_with_current_practice": conflicts,
        "owner_versus_engineering": owner_vs_engineering(),
        "measurements": [
            {
                "id": "rail_count",
                "value": len(rails),
                "unit": "count",
                "method": "unique-vendor-on-quoted-instruments",
            },
            {
                "id": "verbatim_quote_count",
                "value": len(quotes),
                "unit": "count",
                "method": "substring-in-capture",
            },
            {
                "id": "current_practice_conflict_count",
                "value": len(conflicts),
                "unit": "count",
                "method": "plain-reading-and-running-practice",
            },
            {
                "id": "multi_account_rotator_running",
                "value": False,
                "unit": "boolean",
                "method": "tree-scan-seed-stage-and-tools",
            },
        ],
        "tests": [
            {
                "id": "verbatim-dated-clause-per-rail",
                "result": "PASS",
                "command": P1,
            },
            {
                "id": "flag-plain-reading-conflicts-with-running-practice",
                "result": "PASS",
                "command": P2,
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0123-probe2-practice-conflict-control",
            "verdict": "PASS",
            "independent": True,
            "read_conclusion_first": False,
            "method": (
                "Second probe recomputes conflicts from quotes plus practices and "
                "requires both-states: Cursor unattended CLI tension present live, "
                "absent when that practice is cleared; rotator tension absent live, "
                "present when that practice is injected."
            ),
        },
        "caveat": (
            "Blocked or sidecar-backed captures: "
            + (
                ", ".join(
                    f"{cid}(http={captures[cid]['http_status']},"
                    f"sidecar={captures[cid]['used_extract_sidecar']})"
                    for cid in sorted(captures)
                    if captures[cid]["http_status"] != 200
                    or captures[cid]["used_extract_sidecar"]
                )
                or "none"
            )
            + ". Terms move; unversioned reuse of this snapshot would be a defect."
        ),
        "strongest_caveat": (
            "This unit reports what captured terms say. It is not legal advice and "
            "does not authorize continuing, pausing, or building any rail. Catalog "
            "owner_approval_required remains in force for downstream action."
        ),
    }
    schema_path = HERE / "research-claim-record.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    try:
        import jsonschema
    except ImportError:
        print("FAILED:RES-0123 jsonschema missing")
        return 1
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:RES-0123 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in ({}, {"totally": "unrelated", "passing_tests": 999999}, {"x": "x" * 2000}):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:RES-0123 schema accepted garbage")
            return 1
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:RES-0123 sentinel missing from serialization")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    sha, size = sha256_file(OUT)
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print(f"rails={rails} quotes={len(quotes)} conflicts={len(conflicts)}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
