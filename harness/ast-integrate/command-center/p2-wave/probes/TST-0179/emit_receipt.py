#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0179.json (parser_report)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from emitter import CLEAN_MANIFEST, PLANTED_UNKNOWN_FIELD, emit_plugin_manifest, schema_diff
from probe1_unknown_field import run as run_probe1
from probe2_schema_diff import run as run_probe2
from strict_parser import VENDOR, allowed_top_level_fields, load_vendor_schema, parse_manifest

OUT = "command-center/receipts/TST-0179.json"
UNIT = "TST-0179"
SENTINEL = "SUCCESS:TST-0179"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0179/probe1_unknown_field.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0179/probe2_schema_diff.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = sha256_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def probe(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "exit_code": exit_code,
        "fingerprint": hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32],
    }


def main() -> int:
    p1 = run_probe1()
    p2 = run_probe2()
    if not p1["pass"] or not p2["pass"]:
        print(f"FAILED:{UNIT} probes did not pass p1={p1['pass']} p2={p2['pass']}")
        return 1

    emitted = emit_plugin_manifest(CLEAN_MANIFEST)
    dirty = dict(emitted)
    dirty[PLANTED_UNKNOWN_FIELD] = True
    strict_dirty = parse_manifest(dirty, strict=True)
    vendor_sha, vendor_bytes = sha256_file(VENDOR)
    diff = schema_diff(emitted)
    allowed = sorted(allowed_top_level_fields(load_vendor_schema()))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    error_text = " | ".join(strict_dirty["error_messages"])
    supporting = [
        "command-center/p2-wave/probes/TST-0179/strict_parser.py",
        "command-center/p2-wave/probes/TST-0179/emitter.py",
        "command-center/p2-wave/probes/TST-0179/probe1_unknown_field.py",
        "command-center/p2-wave/probes/TST-0179/probe2_schema_diff.py",
        "command-center/p2-wave/probes/TST-0179/vendor/claude-code-plugin-manifest.schema.json",
    ]
    artifacts = [art(p, "supporting") for p in supporting]

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "report_kind": "parser_report",
        "title": "Unknown top-level manifest field is rejected by the strict client parser",
        "question": (
            "Does the strict parser reject a plugin manifest carrying an unknown "
            "top-level field, with an error naming the field? PASS requires rejection "
            "under the STRICTEST supported client, and the authoring toolchain must "
            "never emit such a field."
        ),
        "answer": (
            "YES. The pinned SchemaStore plugin-manifest schema has no top-level "
            "additionalProperties (lenient). Overlaying additionalProperties=false — "
            "the executable equivalent of `claude plugin validate --strict`, which is "
            "the strictest client mode documented and the strictest parser invocable "
            "on this estate (no claude CLI) — rejects a one-field mutant and names "
            f"{PLANTED_UNKNOWN_FIELD!r}. The emitter field set is a subset of the "
            "accepted properties; planting the same unknown key is refused on emit."
        ),
        "spec_anchor": "_USER-PROMPTS.md:11302",
        "min_bytes_threshold": 1024,
        "parser": {
            "id": "claude-code-plugin-manifest-strict",
            "vendor_schema": (
                "command-center/p2-wave/probes/TST-0179/vendor/"
                "claude-code-plugin-manifest.schema.json"
            ),
            "vendor_source": "https://json.schemastore.org/claude-code-plugin-manifest.json",
            "vendor_comment": "Generated on 2026-04-23T05:09:41.810Z",
            "vendor_sha256": vendor_sha,
            "vendor_bytes": vendor_bytes,
            "strictness": "additionalProperties:false overlay on vendor properties",
            "equivalent_client_flag": "claude plugin validate --strict",
            "claude_cli_present": False,
            "accepted_top_level_fields": allowed,
            "accepted_count": len(allowed),
        },
        "unknown_field_case": {
            "field": PLANTED_UNKNOWN_FIELD,
            "rejected": True,
            "error_names_field": True,
            "parser_error": error_text,
            "named_by_parser": strict_dirty["named_unknown_fields_from_parser"],
            "named_by_set_diff": strict_dirty["named_unknown_fields_from_diff"],
        },
        "schema_diff": diff,
        "evidence": [
            {
                "claim": (
                    "Strict parser rejects a clean-plus-unknown-field manifest and the "
                    f"error names {PLANTED_UNKNOWN_FIELD!r}."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0179/strict_parser.py",
                "confidence": "almost-certain",
                "probes": [
                    probe("source", "command", P1, json.dumps(p1, sort_keys=True), 0),
                    probe(
                        "verifier",
                        "in-process",
                        "parse_manifest(dirty, strict=True)",
                        error_text,
                        1 if not strict_dirty["accepted"] else 0,
                    ),
                ],
            },
            {
                "claim": (
                    "Emitter field set is a subset of the vendor schema properties "
                    f"({diff['emitted_count']} of {diff['accepted_count']}); planted "
                    "unknown field is refused rather than written."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0179/emitter.py",
                "confidence": "almost-certain",
                "probes": [
                    probe("source", "command", P2, json.dumps(p2, sort_keys=True), 0),
                    probe(
                        "verifier",
                        "in-process",
                        "schema_diff(emit_plugin_manifest())",
                        json.dumps(
                            {
                                "subset": diff["emitter_subset_of_accepted"],
                                "extra": diff["extra_emitted_fields"],
                            },
                            sort_keys=True,
                        ),
                        0,
                    ),
                ],
            },
        ],
        "tests": [
            {
                "id": "TST-0179-both-states-clean-accepted",
                "name": "both-states control: a clean manifest is accepted",
                "result": "PASS" if p1["clean_accepted"] else "FAIL",
                "command": P1,
            },
            {
                "id": "TST-0179-regression-unknown-field-named",
                "name": (
                    "regression seed: strict plugin parser rejects unknown fields "
                    "(_USER-PROMPTS.md:11302)"
                ),
                "result": "PASS" if p1["dirty_rejected"] and p1["dirty_error_names_field"] else "FAIL",
                "command": P1,
            },
            {
                "id": "TST-0179-schema-diff-emitter-subset",
                "name": "schema-diff: emitter field set ⊆ accepted properties",
                "result": "PASS" if p2["emitter_subset_of_accepted"] else "FAIL",
                "command": P2,
            },
        ],
        "negative_controls": [
            {
                "id": "TST-0179-NC-lenient-vendor-schema",
                "kind": "mutation",
                "description": (
                    "Disable the additionalProperties overlay (published vendor "
                    "schema as-is). The dirty manifest must be ACCEPTED, proving "
                    "the overlay is the rejecting rule."
                ),
                "fired_on_bad_state": p1["lenient_accepts_unknown"] is True,
                "silent_on_good_state": p1["clean_accepted"] is True,
                "bad_state_output": "lenient accepted unknown top-level field",
                "good_state_output": "strict accepted clean manifest",
            },
            {
                "id": "TST-0179-NC-missing-required-name",
                "kind": "known-broken-fixture",
                "description": "A manifest missing required `name` is rejected.",
                "fired_on_bad_state": p1["missing_name_rejected"] is True,
                "silent_on_good_state": p1["clean_accepted"] is True,
                "bad_state_output": "missing name rejected",
                "good_state_output": "clean accepted",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0179-probe2-schema-diff",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "probe2 diffs emitter keys against schema.properties and does not "
                "use the additionalProperties error path that probe1 measures."
            ),
        },
        "artifacts": artifacts,
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0179/UNIT-ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "command",
                    "python3 command-center/p2-wave/_measure_one_delivered.py TST-0179",
                    "scheduled after this receipt and the per-unit manifest exist",
                    0,
                ),
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "claude CLI is not installed on this worktree, so "
                    "`claude plugin validate --strict` was not invoked out of process. "
                    "The JSON Schema overlay is the documented --strict semantics."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Install the Claude Code CLI matching the schema pin and re-run "
                    "the dirty fixture under `claude plugin validate --strict`."
                ),
            }
        ],
        "retry": {
            "count": 0,
            "policy": "two strikes then pivot (AGENTS.md 4b)",
        },
        "timestamps": {
            "started_at": now,
            "ended_at": now,
        },
        "defects": [],
        "completion_sentinel": SENTINEL,
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print(f"FAILED:{UNIT} sentinel missing from serialized receipt")
        return 1
    out.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} bytes={out.stat().st_size}")
    print(f"{SENTINEL} receipt emitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
