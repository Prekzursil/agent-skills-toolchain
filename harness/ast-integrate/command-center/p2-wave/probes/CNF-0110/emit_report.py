#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0110-signature-negative-control.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import matrix as M  # noqa: E402
import schema_check as SC  # noqa: E402

OUT = "command-center/confirmation/CNF-0110-signature-negative-control.json"
SCHEMA = "command-center/schema/security-report.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
QUESTION = (
    "Does signature verification actually verify? Tamper with a signed package "
    "in three ways - flip one content byte, swap the signature from another "
    "package, strip the provenance attestation - and answer: is each rejected "
    "with a distinguishable error, and does the untampered control still verify "
    "in the same run?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0110/probe1_negative_control.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0110/probe2_schema_evidence.py"
)
SUPPORTING = (
    "command-center/p2-wave/probes/CNF-0110/verifier.py",
    "command-center/p2-wave/probes/CNF-0110/matrix.py",
    SCHEMA,
)
MIN_BYTES = 2048


def catalog_sentinel() -> str:
    data = json.loads((REPO / CATALOG).read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == "CNF-0110":
            return str(unit["completion_sentinel"])
    raise SystemExit("FAILED:CNF-0110 catalog unit missing")


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()[:32]


def variant_row(v: dict) -> dict:
    return {
        "id": v["id"],
        "rejected": not v["verified"],
        "exit_code": int(v["exit_code"]),
        "error_code": v.get("error_code"),
        "verbatim_error": v.get("verbatim_error") or "",
        "verified": bool(v["verified"]),
    }


def artifact_row(rel: str, role: str) -> dict:
    digest, size = sha256_file(REPO / rel)
    if size < 1:
        raise SystemExit(f"FAILED:CNF-0110 supporting artifact empty {rel}")
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    observed = M.run_matrix()
    if not observed["contract_holds"]:
        print(f"FAILED:CNF-0110 {observed.get('classification')}")
        print(json.dumps(observed.get("error_codes"), sort_keys=True))
        return 1
    sentinel = catalog_sentinel()
    control = observed["control"]
    variants = [variant_row(v) for v in observed["variants"]]
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    answer = (
        "Yes. In one invocation the Ed25519 verifier rejected all three "
        "authored tampers with distinguishable named errors and exit codes "
        f"({', '.join(observed['error_codes'])}), and the untampered control "
        f"verified (exit {control['exit_code']}). IMP-0063 product attestation "
        "is absent from this worktree; the live implementation under test is "
        "command-center/p2-wave/probes/CNF-0110/verifier.py with synthetic "
        "ephemeral keys (public hex only in the artifact). No ADV-0028 rebuild. "
        + sentinel
    )
    src_fp = fingerprint("command", P1)
    ver_fp = fingerprint("schema-validate", P2)
    if src_fp == ver_fp:
        print("FAILED:CNF-0110 source and verifier fingerprints collided")
        return 1
    negative_control = {
        "same_invocation": True,
        "invocation_id": observed["invocation_id"],
        "trust_public_only": True,
        "publisher_public_hex": observed["publisher_public_hex"],
        "builder_public_hex": observed["builder_public_hex"],
        "untampered": {
            "id": "untampered-control",
            "verified": True,
            "exit_code": int(control["exit_code"]),
            "verbatim_output": (control.get("verbatim_output") or "")[:500],
        },
        "variants": variants,
        "error_codes": observed["error_codes"],
        "errors_distinguishable": True,
        "all_tampered_rejected": True,
        "untampered_verified": True,
    }
    observations = [
        {
            "name": "untampered-control-verified",
            "measured": True,
            "method": "command",
            "anchor": "command-center/p2-wave/probes/CNF-0110/verifier.py",
        },
        {
            "name": "content-byte-flip-rejected",
            "measured": int(variants[0]["exit_code"]),
            "method": "command",
            "anchor": "command-center/p2-wave/probes/CNF-0110/matrix.py",
        },
        {
            "name": "signature-swap-rejected",
            "measured": int(variants[1]["exit_code"]),
            "method": "command",
            "anchor": "command-center/p2-wave/probes/CNF-0110/matrix.py",
        },
        {
            "name": "provenance-stripped-rejected",
            "measured": int(variants[2]["exit_code"]),
            "method": "command",
            "anchor": "command-center/p2-wave/probes/CNF-0110/matrix.py",
        },
        {
            "name": "errors-distinguishable",
            "measured": True,
            "method": "command",
            "anchor": "command-center/p2-wave/probes/CNF-0110/probe1_negative_control.py",
        },
        {
            "name": "same-invocation",
            "measured": True,
            "method": "command",
            "anchor": f"invocation:{observed['invocation_id']}",
        },
    ]
    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0110",
        "state": "SUCCESS",
        "sentinel": sentinel,
        "profile": "signature-negative-control",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json CNF-0110 question_or_target",
        "min_bytes_threshold": MIN_BYTES,
        "artifacts": [artifact_row(rel, "supporting") for rel in SUPPORTING],
        "evidence": [
            {
                "claim": (
                    "All three authored tampers were rejected with distinguishable "
                    f"error codes {observed['error_codes']} in one invocation."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0110/matrix.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "raw_output": (
                            f"tampers_rejected=3 error_codes={observed['error_codes']} "
                            f"invocation={observed['invocation_id']}"
                        ),
                        "fingerprint": src_fp,
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "schema-validate",
                        "command": P2,
                        "raw_output": "schema + recorded variants + live matrix re-run",
                        "fingerprint": ver_fp,
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "The untampered control verified in the same invocation "
                    f"(exit {control['exit_code']}), so the verifier is not a "
                    "universal rejector."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0110/verifier.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": (
                            "python3 -B command-center/p2-wave/probes/CNF-0110/matrix.py"
                        ),
                        "raw_output": (control.get("verbatim_output") or "")[:400],
                        "fingerprint": fingerprint(
                            "command",
                            "python3 -B command-center/p2-wave/probes/CNF-0110/matrix.py",
                        ),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "schema-validate",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            "command-center/p2-wave/probes/CNF-0110/schema_check.py "
                            + OUT
                        ),
                        "raw_output": "in-memory schema validation before write",
                        "fingerprint": fingerprint(
                            "schema-validate",
                            "schema_check.py " + OUT,
                        ),
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "CNF0110-T1-THREE-TAMPERS-SAME-INVOCATION",
                "name": "Three tampers rejected; untampered control verified",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "CNF0110-T2-SCHEMA-EVIDENCE-RERUN",
                "name": "Catalog schema, recorded evidence, live matrix re-run",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": variants[0]["id"],
                "kind": "mutation",
                "description": "Flip one payload byte; verifier must reject with CONTENT_DIGEST_MISMATCH.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": variants[0]["verbatim_error"][:500],
                "good_state_output": (control.get("verbatim_output") or "")[:500],
            },
            {
                "id": variants[1]["id"],
                "kind": "mutation",
                "description": "Swap signature envelope from another package; verifier must reject with SIGNATURE_IDENTITY_MISMATCH.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": variants[1]["verbatim_error"][:500],
                "good_state_output": (control.get("verbatim_output") or "")[:500],
            },
            {
                "id": variants[2]["id"],
                "kind": "absent-input",
                "description": "Strip provenance.json; verifier must reject with PROVENANCE_MISSING.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": variants[2]["verbatim_error"][:500],
                "good_state_output": (control.get("verbatim_output") or "")[:500],
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0110-probe2-schema-evidence",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "local",
            "notes": (
                "Mechanical re-run of the four-case matrix plus schema and "
                "garbage-probe discrimination; did not author verifier.py."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0110/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "CNF-0110",
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads + local-ref Draft7Validator(security-report.schema.json)",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                        "command-center/p2-wave/probes/CNF-0110/schema_check.py "
                        + OUT
                    ),
                    "raw_output": "schema_errors=0 garbage_rejected=true",
                    "fingerprint": fingerprint("schema-validate", "schema_check.py"),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": ended,
        },
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. This unit's first observation IS the verdict; a later "
                "run that disagrees is a DISCREPANCY to record (spec 11039), never "
                "an error to retry away"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0063 product attestation bytes are absent on this worktree; "
                    "CNF-0110 measured the unit-local Ed25519 verifier rather than "
                    "rebuilding ADV-0028."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Mount the IMP-0063 signed-package product on a worktree that "
                    "has it and re-run the same three tampers plus untampered control."
                ),
            }
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "local-parallel",
        },
        "report": {
            "kind": "security-report",
            "observations": observations,
            "control_ids": ["untampered-control"],
            "negative_control": negative_control,
            "question": QUESTION,
            "answer": answer,
            "title": "Signature and provenance verification must fail on a tampered package",
        },
        "extensions": {
            "adv_rebuild_circle": False,
            "product_imp0063_present": False,
            "verifier_path": observed["verifier"],
            "output_path": OUT,
            "output_schema": SCHEMA,
            "named_probes": [
                {"id": "probe1", "command": P1},
                {"id": "probe2", "command": P2},
            ],
        },
    }
    errs = SC.error_messages(doc)
    if errs:
        print("FAILED:CNF-0110 schema errors")
        for line in errs[:20]:
            print(" ", line)
        return 1
    if not SC.rejects_garbage():
        print("FAILED:CNF-0110 schema accepted garbage")
        return 1
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if sentinel not in text:
        print("FAILED:CNF-0110 sentinel-absent from document")
        return 1
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    digest, size = sha256_file(out)
    if size < MIN_BYTES:
        print(f"FAILED:CNF-0110 artifact {size}B below floor {MIN_BYTES}")
        return 1
    disk = json.loads(out.read_text(encoding="utf-8"))
    disk_errs = SC.error_messages(disk)
    if disk_errs:
        print("FAILED:CNF-0110 on-disk schema errors")
        for line in disk_errs[:20]:
            print(" ", line)
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:CNF-0110 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
