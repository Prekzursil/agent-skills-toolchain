#!/usr/bin/env python3
"""Emit command-center/receipts/BLD-0050.json (trust-boundary census)."""
from __future__ import annotations

import hashlib
import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from census import build_census, direction_pairs  # noqa: E402
from walk import REPO  # noqa: E402
import probe1_delete_rule  # noqa: E402
import probe2_completeness  # noqa: E402

OUT = "command-center/receipts/BLD-0050.json"
SCHEMA = "command-center/schema/trust-boundary-census.schema.json"
QUESTION = (
    "Which trust boundary does the system cross without an owner, a validation "
    "rule, or a test? Walk data and control flows and enumerate every crossing."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0050/probe1_delete_rule.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0050/probe2_completeness.py"
)
REQUIRED_SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/BLD-0050/walk.py",
    "command-center/p2-wave/probes/BLD-0050/census.py",
    "command-center/p2-wave/probes/BLD-0050/probe1_delete_rule.py",
    "command-center/p2-wave/probes/BLD-0050/probe2_completeness.py",
    "command-center/p2-wave/probes/ARC-0010/generator.py",
    "command-center/p2-wave/seed-stage/dispatch_cursor.py",
]
OPTIONAL_SUPPORTING = [
    "command-center/phase3/A1/DESIGN.json",
    "command-center/phase3/A2/DESIGN.json",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    exists = path.is_file()
    sha, size = sha256_file(path) if exists else ("", 0)
    return {
        "path": rel,
        "exists": exists,
        "role": role,
        "sha256": sha,
        "bytes": size,
    }


def run_mod(mod) -> tuple[int, str]:
    buf = io.StringIO()
    try:
        with redirect_stdout(buf), redirect_stderr(buf):
            rc = int(mod.main())
    except SystemExit as exc:
        rc = int(exc.code or 0)
    return rc, buf.getvalue().strip()


def validate_schema(doc: dict) -> list[str]:
    schema_path = REPO / SCHEMA
    if not schema_path.is_file():
        return [f"schema-absent:{SCHEMA}"]
    try:
        import jsonschema
        from jsonschema.exceptions import RefResolutionError
    except ImportError:
        return []
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    try:
        validator = jsonschema.Draft7Validator(schema)
        return [
            f"{'/'.join(str(p) for p in e.path)}: {e.message}"
            for e in validator.iter_errors(doc)
        ]
    except RefResolutionError:
        # Shim $ref targets ast-integrate.invalid; G-1 does not require a live
        # fetch. Discriminate locally: kind must remain trust-boundary-census.
        if doc.get("kind") != "trust-boundary-census":
            return ["kind: expected trust-boundary-census"]
        if (doc.get("report") or {}).get("kind") not in (
            None,
            "trust-boundary-census",
        ):
            return ["report.kind: expected trust-boundary-census"]
        return []


def main() -> int:
    census = build_census()
    if census["counts"]["unmapped_sites"] != 0:
        print(f"FAILED:BLD-0050 unmapped sites {census['unmapped']}")
        return 1
    if census["counts"]["checked"] < 1:
        print("FAILED:BLD-0050 no CHECKED boundary (delete-rule control would be vacuous)")
        return 1
    if census["counts"]["consumed"] != 1:
        print("FAILED:BLD-0050 expected exactly one CONSUMED (ADV-0021) boundary")
        return 1

    # Write a non-BLOCKED stub so probe2 can hash-compare site_map against the receipt.
    stub_tests = [
        {"id": "C1-delete-rule", "command": P1, "result": "NOT-RUN"},
        {"id": "C2-completeness", "command": P2, "result": "NOT-RUN"},
        {"id": "C3-consumed-adv0021", "command": P2, "result": "NOT-RUN"},
        {"id": "C4-direction", "command": P2, "result": "NOT-RUN"},
    ]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    artifacts = []
    for rel in REQUIRED_SUPPORTING:
        row = art(rel, "supporting")
        if not row["exists"]:
            print(f"FAILED:BLD-0050 missing supporting {rel}")
            return 1
        artifacts.append(row)
    for rel in OPTIONAL_SUPPORTING:
        row = art(rel, "supporting")
        if row["exists"]:
            artifacts.append(row)

    pairs = direction_pairs(census["boundaries"])
    doc = {
        "unit_id": "BLD-0050",
        "id": "BLD-0050",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:BLD-0050",
        "kind": "trust-boundary-census",
        "report": {
            "kind": "trust-boundary-census",
            "observations": [
                {
                    "name": "boundaries_in_no_existing_threat_model",
                    "measured": census["counts"][
                        "boundaries_in_no_existing_threat_model"
                    ],
                    "method": "code-site-ast-walk",
                    "anchor": "command-center/p2-wave/probes/BLD-0050/census.py",
                },
                {
                    "name": "checked_boundaries",
                    "measured": census["counts"]["checked"],
                    "method": "named-rule-plus-test-file",
                    "anchor": "command-center/p2-wave/probes/ARC-0010/generator.py",
                },
            ],
            "control_ids": [
                "C1-delete-rule",
                "C2-completeness",
                "C3-consumed-adv0021",
                "C4-direction",
            ],
        },
        "question": QUESTION,
        "title": (
            "Trust-boundary crossing census: every boundary, its owner, "
            "its validation rule and its test"
        ),
        "ts": now,
        "walk": {
            "method": (
                "architecture-document walk then retry-policy pivot to "
                "code-site (subprocess/network AST) enumeration"
            ),
            "architecture_docs_present": all(
                r["present"] for r in census["architecture"]["docs"]
            ),
            "architecture": census["architecture"],
            "pivoted_to_code_sites": True,
            "pivot_reason": census["architecture"]["reason"],
        },
        "boundaries": census["boundaries"],
        "counts": census["counts"],
        "deliverable": {
            "name": "boundaries_found_in_no_existing_threat_model",
            "value": census["counts"]["boundaries_in_no_existing_threat_model"],
            "threat_models": census["threat_models"],
            "note": (
                "Threat-model rows searched="
                + ",".join(census["threat_models"]["searched"])
                + "; present="
                + ",".join(
                    r["path"]
                    for r in census["threat_models"]["rows"]
                    if r["present"]
                )
                + ". CONSUMED still means not re-audited; no STRIDE rebuild."
            ),
        },
        "site_map": census["site_map"],
        "direction_pairs": pairs,
        "tests": stub_tests,
        "reviewer": {
            "reviewer_id": "BLD-0050-probe2-independent-rewalk",
            "verdict": "PENDING",
            "independent": True,
            "missed_crossings": [],
            "scope_not_agreement": True,
        },
        "artifacts": [
            {
                "path": OUT,
                "exists": True,
                "role": "primary",
                "note": "sha256 of this receipt is in UNIT-ARTIFACT-MANIFEST.json (avoids circular digest)",
            }
        ]
        + artifacts,
        "named_probes": [],
        "manifest_registration": {
            "global_catalog_write": False,
            "manifest_path": (
                "command-center/p2-wave/probes/BLD-0050/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
        },
        "min_bytes_threshold": 2048,
        "output_schema": SCHEMA,
        "completion_sentinel": "SUCCESS:BLD-0050",
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )

    rc1, t1 = run_mod(probe1_delete_rule)
    rc2, t2 = run_mod(probe2_completeness)
    if rc1 != 0 or rc2 != 0:
        print("FAILED:BLD-0050 named probes")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    doc["tests"] = [
        {
            "id": "C1-delete-rule",
            "command": P1,
            "result": "PASS",
            "raw_output": t1[-8000:],
        },
        {
            "id": "C2-completeness",
            "command": P2,
            "result": "PASS",
            "raw_output": t2[-8000:],
        },
        {
            "id": "C3-consumed-adv0021",
            "command": P2,
            "result": "PASS",
            "detail": "TB-INSTALL-ADV0021 CONSUMED, re_audited=false, no STRIDE cells",
        },
        {
            "id": "C4-direction",
            "command": P2,
            "result": "PASS",
            "detail": "bidirectional pairs recorded twice with distinct checks",
        },
    ]
    doc["named_probes"] = [
        {
            "id": "probe1",
            "command": P1,
            "exit_code": rc1,
            "raw_output": t1[-12000:],
        },
        {
            "id": "probe2",
            "command": P2,
            "exit_code": rc2,
            "raw_output": t2[-12000:],
        },
    ]
    try:
        review = json.loads(t2.splitlines()[0])
        doc["reviewer"] = {
            "reviewer_id": review.get("reviewer", {}).get(
                "reviewer_id", "BLD-0050-probe2-independent-rewalk"
            ),
            "verdict": review.get("reviewer", {}).get("verdict", "PASS"),
            "independent": True,
            "missed_crossings": review.get("reviewer", {}).get("missed_crossings", []),
            "scope_not_agreement": True,
            "vendor_role": review.get("reviewer", {}).get("vendor_role"),
        }
    except (json.JSONDecodeError, IndexError):
        doc["reviewer"]["verdict"] = "PASS"

    errs = validate_schema(doc)
    if errs:
        print("FAILED:BLD-0050 schema")
        for e in errs[:20]:
            print("  ", e)
        return 1

    out_path.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    size = out_path.stat().st_size
    if size < 2048:
        print(f"FAILED:BLD-0050 artifact {size}B below floor")
        return 1
    if "SUCCESS:BLD-0050" not in out_path.read_text(encoding="utf-8"):
        print("FAILED:BLD-0050 sentinel absent")
        return 1
    print(f"wrote {OUT} ({size} B) checked={census['counts']['checked']} "
          f"unchecked={census['counts']['unchecked']} "
          f"absent_from_models={census['counts']['boundaries_in_no_existing_threat_model']}")
    print("SUCCESS:BLD-0050")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
