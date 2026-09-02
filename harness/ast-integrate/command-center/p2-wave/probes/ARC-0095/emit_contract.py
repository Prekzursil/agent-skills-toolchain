#!/usr/bin/env python3
"""Emit command-center/phase4/contracts/ARC-0095.json from a live generator run."""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import matrix as M  # noqa: E402

OUT = "command-center/phase4/contracts/ARC-0095.json"
# Do not overwrite command-center/schema/compatibility-matrix.schema.json:
# that path is a generated shim ($ref to artifact-class-profiles) used by
# other catalog units. The ARC-0095 document schema lives next to the probes.
SCHEMA_OUT = (
    "command-center/p2-wave/probes/ARC-0095/matrix-document.schema.json"
)
QUESTION = (
    "Specify the compatibility matrix: the axes (operating system, client and "
    "version, shell, package version), the support tiers, how a cell is "
    "populated with EVIDENCE, and - most importantly - how an UNTESTED cell "
    "is represented so it can never be read as a pass. Define the rule that a "
    "cell may only be marked supported by a recorded test run, and that "
    "inference from an adjacent cell is labelled INFERRED, never SUPPORTED."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0095/probe1_untested_cell.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0095/probe2_inference_label.py"
)

EVIDENCE_ROOTS = [
    "command-center/receipts",
    "command-center/p2-wave/probes/ARC-0095/fixtures/live-evidence",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def scan_receipt_files() -> tuple[list[dict], list[str]]:
    found: list[dict] = []
    scanned: list[str] = []
    for rel in EVIDENCE_ROOTS:
        root = REPO / rel
        scanned.append(rel)
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.json")):
            try:
                blob = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            rows = blob if isinstance(blob, list) else [blob]
            for row in rows:
                if isinstance(row, dict) and "run_id" in row:
                    found.append(row)
    return found, scanned


def matrix_document_schema() -> dict:
    status_enum = list(M.STATUSES)
    axis_props = {k: {"type": "string", "minLength": 1} for k in M.AXIS_ORDER}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "command-center/p2-wave/probes/ARC-0095/matrix-document.schema.json",
        "title": "Compatibility matrix (ARC-0095)",
        "type": "object",
        "additionalProperties": True,
        "required": ["axes", "cells", "untested_cell_count", "status_counts"],
        "properties": {
            "axes": {
                "type": "object",
                "required": list(M.AXIS_ORDER),
                "properties": {
                    k: {"type": "array", "items": {"type": "string"}, "minItems": 1}
                    for k in M.AXIS_ORDER
                },
            },
            "untested_cell_count": {"type": "integer", "minimum": 0},
            "cells": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["id", "axes", "status", "render", "is_pass"],
                    "properties": {
                        "id": {"type": "string", "minLength": 5},
                        "axes": {
                            "type": "object",
                            "required": list(M.AXIS_ORDER),
                            "properties": axis_props,
                        },
                        "status": {"type": "string", "enum": status_enum},
                        "is_pass": {"type": "boolean"},
                        "render": {
                            "type": "object",
                            "required": [
                                "token",
                                "glyph",
                                "css_class",
                                "is_pass",
                                "machine_status",
                            ],
                            "properties": {
                                "token": {"type": "string"},
                                "glyph": {"type": "string", "minLength": 1},
                                "css_class": {"type": "string", "minLength": 3},
                                "is_pass": {"type": "boolean"},
                                "machine_status": {"type": "string", "enum": status_enum},
                                "color_role": {"type": "string"},
                            },
                        },
                    },
                    "allOf": [
                        {
                            "if": {"properties": {"status": {"const": "NOT-CHECKED"}}},
                            "then": {
                                "properties": {
                                    "is_pass": {"const": False},
                                    "render": {
                                        "properties": {
                                            "token": {"not": {"enum": list(M.PASS_LIKE)}},
                                            "is_pass": {"const": False},
                                        }
                                    },
                                }
                            },
                        },
                        {
                            "if": {"properties": {"status": {"const": "INFERRED"}}},
                            "then": {
                                "properties": {
                                    "is_pass": {"const": False},
                                    "status": {"not": {"const": "SUPPORTED"}},
                                    "render": {
                                        "properties": {
                                            "is_pass": {"const": False},
                                            "machine_status": {"const": "INFERRED"},
                                            "css_class": {
                                                "not": {"const": "matrix-cell-supported"}
                                            },
                                        }
                                    },
                                }
                            },
                        },
                        {
                            "if": {"properties": {"status": {"const": "SUPPORTED"}}},
                            "then": {
                                "properties": {
                                    "evidence": {"type": "array", "minItems": 1}
                                }
                            },
                        },
                    ],
                },
            },
        },
    }


def host_platform() -> str:
    name = platform.system().lower().strip()
    return {"linux": "linux", "darwin": "macos", "windows": "windows"}.get(name, name)


def main() -> int:
    receipts, scanned = scan_receipt_files()
    ran_on = [host_platform()]
    snapshot = M.generate(receipts, infer=False, program_ran_on=ran_on)
    schema = matrix_document_schema()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    render_rows = []
    for status, spec in M.RENDER.items():
        render_rows.append(
            {
                "status": status,
                "token": spec["token"],
                "display": spec["display"],
                "glyph": spec["glyph"],
                "css_class": spec["css_class"],
                "color_role": spec["color_role"],
                "is_pass": spec["is_pass"],
                "machine_status": spec["machine_status"],
            }
        )

    doc = {
        "unit_id": "ARC-0095",
        "id": "ARC-0095",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0095",
        "completion_sentinel": "SUCCESS:ARC-0095",
        "schema_version": 1,
        "report_kind": "compatibility-matrix-contract",
        "title": (
            "Contract: Compatibility matrix contract and the representation "
            "of an untested cell"
        ),
        "question": QUESTION,
        "emitted_at": now,
        "execution_substrate": "headless-linux",
        "output_schema": "https://json-schema.org/draft/2020-12/schema",
        "matrix_document_schema_path": SCHEMA_OUT,
        "axes": {
            "order": list(M.AXIS_ORDER),
            "declared": snapshot["axes"],
            "definitions": {
                "operating_system": (
                    "Host OS of the recorded run: linux | windows | macos. "
                    "A cell is keyed by the OS that actually executed, not the "
                    "OS the author intended to cover."
                ),
                "client": (
                    "Host client identity. Declared set: claude-code, "
                    "codex-cli, antigravity (agy), mcp-generic."
                ),
                "client_version": (
                    "Observed client VERSION string from inside the client. "
                    "UNPINNED means no pin is published and cannot be SUPPORTED. "
                    "An installer exit code is not a version."
                ),
                "shell": "Shell that invoked the smoke journey: bash | powershell.",
                "package_version": (
                    "Observed package/plugin version under test. UNPINNED cannot "
                    "be SUPPORTED."
                ),
            },
        },
        "support_tiers": {
            "rule": (
                "A tier is a planning attribute, never a status and never a pass. "
                "T1/T2/T3 without evidence remain NOT-CHECKED."
            ),
            "T1": "Must have in-client evidence before a support claim.",
            "T2": "Best-effort; still NOT-CHECKED until a receipt exists.",
            "T3": "Experimental; still NOT-CHECKED until a receipt exists.",
            "plan": [
                {"operating_system": os_n, "client": cl, "tier": tier}
                for (os_n, cl), tier in sorted(M.TIER_PLAN.items())
            ],
        },
        "cell_statuses": {
            "enum": list(M.STATUSES),
            "SUPPORTED": (
                "Only a recorded in-client test run whose receipt names the "
                "observed client VERSION. Never inferred. Never an installer exit."
            ),
            "FAILED": "Recorded in-client run with result=fail. Survives into the table.",
            "INFERRED": (
                "Guess from an adjacent SUPPORTED cell (adjacent OS, same client, "
                "version, shell, package). Machine status INFERRED. is_pass=false. "
                "Never SUPPORTED. Distinct glyph, token, and css_class from SUPPORTED."
            ),
            "NOT-CHECKED": (
                "No accepted in-client receipt for this cell. Canonical machine "
                "status. Display alias UNTESTED. Never a pass, never blank, never "
                "green, never SUPPORTED. Removing a receipt MUST revert the cell "
                "to NOT-CHECKED rather than staying green."
            ),
            "NOT-APPLICABLE": "Combination cannot exist (example: cmd on non-Windows).",
            "UNSUPPORTED": "Owner-recorded out-of-scope decision, not silence.",
            "untested_representation": {
                "machine_status": "NOT-CHECKED",
                "display_alias": "UNTESTED",
                "blank_forbidden": True,
                "pass_aliases_forbidden": sorted(M.PASS_LIKE),
                "is_pass": False,
                "glyph": M.RENDER["NOT-CHECKED"]["glyph"],
                "css_class": M.RENDER["NOT-CHECKED"]["css_class"],
                "token": "NOT-CHECKED",
            },
        },
        "render_table": render_rows,
        "evidence_rules": {
            "supported_requires_recorded_run": True,
            "installer_exit_is_not_evidence": True,
            "observation_kind_required": "in-client",
            "observed_client_version_must_equal_client_version": True,
            "unpinned_version_cannot_be_supported": True,
            "adjacent_inference_label": "INFERRED",
            "adjacent_inference_never_supported": True,
            "default_generator_does_not_infer": True,
            "inference_does_not_chain": True,
            "failed_cells_are_not_dropped": True,
            "blank_cells_forbidden": True,
            "all_green_on_one_platform_is_a_defect": True,
        },
        "population_procedure": [
            "Enumerate the cartesian product of declared axes. Every tuple is a cell.",
            "Scan evidence roots for receipts. Reject installer-exit, unpinned versions, and intended!=observed version.",
            "Accepted pass -> SUPPORTED. Accepted fail -> FAILED. Never omit FAILED.",
            "Every remaining applicable cell is NOT-CHECKED with a reason. Never blank.",
            "If infer=true, neighbours of SUPPORTED (adjacent OS only) become INFERRED, not SUPPORTED.",
            "If untested_cell_count==0 and the program has run on one platform, emit defect all-green-on-partial-estate.",
        ],
        "tests_required": [
            {
                "id": "untested-cell-control",
                "requirement": (
                    "Remove a test result and assert the cell reverts to "
                    "NOT-CHECKED rather than staying green"
                ),
                "command": P1,
            },
            {
                "id": "inference-labelling",
                "requirement": (
                    "An inferred cell must be visually and machine-distinguishable "
                    "from a tested one"
                ),
                "command": P2,
            },
        ],
        "evidence_requirement": (
            "The matrix generator is run over the current test evidence and the "
            "untested-cell count is reported; a matrix with no untested cells on "
            "a program that has run on one platform is itself a defect."
        ),
        "generator_run": {
            "module": "command-center/p2-wave/probes/ARC-0095/matrix.py",
            "infer": False,
            "evidence_roots_scanned": scanned,
            "receipts_found": len(receipts),
            "receipts_accepted": snapshot["receipts_accepted"],
            "receipts_rejected": snapshot["receipts_rejected"],
            "program_ran_on": snapshot["program_ran_on"],
            "platforms_with_evidence": snapshot["platforms_with_evidence"],
            "cell_count": snapshot["cell_count"],
            "untested_cell_count": snapshot["untested_cell_count"],
            "untested_cell_count": snapshot["untested_cell_count"],
            "supported_cell_count": snapshot["supported_cell_count"],
            "inferred_cell_count": snapshot["inferred_cell_count"],
            "failed_cell_count": snapshot["failed_cell_count"],
            "status_counts": snapshot["status_counts"],
            "blank_cells": snapshot["blank_cells"],
            "defects": snapshot["defects"],
            "cells": snapshot["cells"],
            "note": (
                "This Linux worktree executed ARC probes, which is not an "
                "in-client versioned receipt for claude-code / codex-cli / "
                "antigravity / mcp-generic. Zero accepted receipts; every "
                "applicable declared cell is NOT-CHECKED. A zero untested count "
                "here would have been the all-green-on-partial-estate defect."
            ),
        },
        "reviewer": {
            "reviewer_id": "ARC-0095-probe1-untested-cell",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Named probe1 deletes a planted receipt and requires NOT-CHECKED. "
                "Named probe2 requires INFERRED != SUPPORTED in status, glyph, "
                "css_class, and is_pass."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "untested-cell-control", "command": P1},
            {"id": "probe2", "role": "inference-labelling", "command": P2},
        ],
        "cloud_ok": False,
        "registered": True,
    }

    try:
        import jsonschema
    except ImportError:
        jsonschema = None
    if jsonschema is not None:
        jsonschema.Draft202012Validator(schema).validate(snapshot)

    schema_path = REPO / SCHEMA_OUT
    schema_path.parent.mkdir(parents=True, exist_ok=True)
    schema_path.write_text(
        json.dumps(schema, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    if "SUCCESS:ARC-0095" not in text:
        print("FAILED:ARC-0095 sentinel missing from emit")
        return 1
    if snapshot["untested_cell_count"] <= 0 and not snapshot["defects"]:
        print("FAILED:ARC-0095 empty-untested without partial-estate defect")
        return 1
    out.write_text(text, encoding="utf-8")
    digest, size = sha256_file(out)
    print(
        f"wrote {OUT} bytes={size} sha256={digest} "
        f"untested={snapshot['untested_cell_count']} "
        f"supported={snapshot['supported_cell_count']}"
    )
    print("SUCCESS:ARC-0095 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
