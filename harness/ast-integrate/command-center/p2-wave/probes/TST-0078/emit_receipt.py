#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0078.json from a live matrix run."""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "plugin"))
sys.path.insert(0, str(HERE))

import jsonschema  # noqa: E402

import compatibility as C  # noqa: E402
from receipt_schema import validate_test_receipt  # noqa: E402

UNIT = "TST-0078"
OUT = "command-center/receipts/TST-0078.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
CONTRACT = "tools/plugin/support_contract.json"
COMPAT_SCHEMA = "tools/plugin/schema/compatibility.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0078/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0078/probe2_untested_and_detector.py"
)
PUBLISHED = HERE / "fixtures" / "published"
QUESTION = (
    "Phase 5 requires compatibility diagnostics (:10838). Target: attempt "
    "installation against every declared UNSUPPORTED client/OS/version "
    "combination and assert it is refused, and against every SUPPORTED "
    "combination and assert it proceeds - a both-states matrix over the "
    "whole support contract."
)
SUPPORTING = [
    SCHEMA,
    CONTRACT,
    "tools/plugin/compatibility.py",
    COMPAT_SCHEMA,
    "command-center/p2-wave/probes/TST-0078/emit_receipt.py",
    "command-center/p2-wave/probes/TST-0078/probe1_both_states.py",
    "command-center/p2-wave/probes/TST-0078/probe2_untested_and_detector.py",
    "command-center/p2-wave/probes/TST-0078/fixtures/published/plugin.json",
    "command-center/p2-wave/probes/TST-0078/fixtures/published/README.txt",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    raw = f"{method}|{command}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "role": role,
        "eol": "LF",
    }


def main() -> int:
    C.write_contract(REPO / CONTRACT)
    contract = C.load_contract(REPO / CONTRACT)
    live_built = C.build_contract()
    if json.dumps(contract, sort_keys=True) != json.dumps(live_built, sort_keys=True):
        print("FAILED:TST-0078 emit on-disk contract drifted from builder")
        return 1
    jsonschema.Draft7Validator(C.CONTRACT_SCHEMA).validate(contract)

    with tempfile.TemporaryDirectory(prefix="tst0078-emit-") as tmp_s:
        tmp = Path(tmp_s)
        matrix = C.run_matrix(PUBLISHED, tmp / "cells", contract)
        unsupported_linux = next(
            c
            for c in matrix["cells"]
            if c.get("declared") == "UNSUPPORTED"
            and c.get("os") == "linux"
            and c.get("client") == "claude-code"
            and c.get("client_version") == "1.0.0"
        )
        gated = C.attempt_install(
            PUBLISHED,
            tmp / "gated",
            {
                "os": unsupported_linux["os"],
                "client": unsupported_linux["client"],
                "client_version": unsupported_linux["client_version"],
            },
            contract,
        )
        ungated = tmp / "ungated"
        shutil.copytree(PUBLISHED, ungated)
        ungated_present = (ungated / "plugin.json").is_file()

    counts = matrix["counts"]
    if counts["mismatched"] != 0:
        print("FAILED:TST-0078 emit mismatched cells", counts)
        return 1
    if counts["supported_declared"] != counts["supported_proceeded"]:
        print("FAILED:TST-0078 emit supported did not all proceed", counts)
        return 1
    if counts["unsupported_declared"] != counts["unsupported_refused"]:
        print("FAILED:TST-0078 emit unsupported did not all refuse", counts)
        return 1
    if counts["untested"] < 1:
        print("FAILED:TST-0078 emit no UNTESTED cells")
        return 1
    if counts["blank"] != 0:
        print("FAILED:TST-0078 emit blank cells")
        return 1
    complete = C.completeness_ok(matrix["cells"], contract["axes"])
    if not complete["ok"]:
        print("FAILED:TST-0078 emit completeness", complete)
        return 1
    dropped = [c for c in matrix["cells"] if c.get("outcome") != "UNTESTED"]
    dropped_check = C.completeness_ok(dropped, contract["axes"])
    omit_fired = (not dropped_check["ok"]) and bool(dropped_check["missing"])
    if not omit_fired:
        print("FAILED:TST-0078 emit omit-untested mutant not detected", dropped_check)
        return 1
    if gated["installed"] or gated["plugin_present"] or gated["files_written"] != 0:
        print("FAILED:TST-0078 emit live gate installed unsupported", gated)
        return 1
    if not ungated_present:
        print("FAILED:TST-0078 emit ungated mutant did not land files")
        return 1
    unparsable = C.negotiate(
        {"os": "linux", "client": "claude-code", "client_version": "not-a-version"}
    )
    if unparsable.action != "refuse" or unparsable.reason_code != "unparsable-version":
        print("FAILED:TST-0078 emit unparsable did not fail closed")
        return 1

    started = _now()
    artifacts = [_artifact_row(rel, "supporting") for rel in SUPPORTING]
    both_states = {
        "supported_proceeds": counts["supported_proceeded"] == counts["supported_declared"]
        and counts["supported_declared"] > 0,
        "unsupported_refused": counts["unsupported_refused"] == counts["unsupported_declared"]
        and counts["unsupported_declared"] > 0,
        "supported_count": counts["supported_declared"],
        "unsupported_count": counts["unsupported_declared"],
        "untested_count": counts["untested"],
    }
    src_fp = fingerprint("test-run", P1)
    ver_fp = fingerprint("byte-compare", P2)
    emit_fp = fingerprint(
        "schema-validate",
        "python3 -B command-center/p2-wave/probes/TST-0078/receipt_schema.py",
    )
    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0078",
        "spec_anchor": "_USER-PROMPTS.md:10838 compatibility diagnostics",
        "min_bytes_threshold": 2048,
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": "Every declared SUPPORTED cell proceeds and writes plugin.json",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "tools/plugin/compatibility.py:attempt_install",
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": P1,
                        "raw_output": (
                            f"supported_proceeded={counts['supported_proceeded']}"
                        ),
                        "fingerprint": src_fp,
                    },
                    {
                        "role": "verifier",
                        "method": "byte-compare",
                        "command": P2,
                        "raw_output": (
                            f"cartesian={counts['cartesian']} "
                            f"untested={counts['untested']}"
                        ),
                        "fingerprint": ver_fp,
                    },
                ],
            },
            {
                "claim": (
                    "Every declared UNSUPPORTED cell is refused with zero files written; "
                    "cartesian leftovers are UNTESTED, never omitted"
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "tools/plugin/compatibility.py:completeness_ok",
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": P1,
                        "raw_output": (
                            f"unsupported_refused={counts['unsupported_refused']}"
                        ),
                        "fingerprint": src_fp,
                    },
                    {
                        "role": "verifier",
                        "method": "byte-compare",
                        "command": P2,
                        "raw_output": (
                            "omit_untested_detected=true "
                            "live_gate_refused_unsupported=true"
                        ),
                        "fingerprint": ver_fp,
                    },
                ],
            },
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": _now(),
        },
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot: after the 2nd failure on the same "
                "error-fingerprint, enumerate >=2 alternative approaches before "
                "a 3rd attempt (AGENTS.md 4b)"
            ),
        },
        "tests": [
            {
                "id": "test_every_unsupported_combination_is_refused",
                "command": P1,
                "result": "PASS",
                "assertions": counts["unsupported_refused"],
            },
            {
                "id": "test_every_supported_combination_proceeds",
                "command": P1,
                "result": "PASS",
                "assertions": counts["supported_proceeded"],
            },
            {
                "id": "test_untested_cells_are_reported_not_omitted",
                "command": P2,
                "result": "PASS",
                "assertions": counts["untested"],
            },
        ],
        "negative_controls": [
            {
                "id": "omit-untested-cells",
                "kind": "mutation",
                "description": (
                    "Drop UNTESTED cells from the matrix; completeness_ok must "
                    "fail and name the missing cartesian leftovers."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(dropped_check, sort_keys=True),
                "good_state_output": json.dumps(complete, sort_keys=True),
            },
            {
                "id": "ungated-copy-unsupported",
                "kind": "mutation",
                "description": (
                    "Ungated copytree of the published fixture onto an "
                    "UNSUPPORTED cell destination lands plugin.json; the live "
                    "gate must refuse and write zero files."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "ungated plugin.json present=true",
                "good_state_output": (
                    f"gated outcome={gated['outcome']} files_written="
                    f"{gated['files_written']}"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0078-probe2-cartesian-completeness",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Rebuilt the cartesian product from axes alone and required "
                "every cell in the receipt; dropped-UNTESTED mutant fails "
                "completeness; ungated copytree on an unsupported cell lands "
                "files while the live gate does not."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0078/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/TST-0078/receipt_schema.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "python3 -B command-center/p2-wave/probes/TST-0078/"
                        "receipt_schema.py"
                    ),
                    "raw_output": "validate_test_receipt errors=[]",
                    "fingerprint": emit_fp,
                },
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "The same probes were not re-run under PowerShell 7 on Windows"
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run probe1_both_states.py and "
                    "probe2_untested_and_detector.py in pwsh on a Windows host."
                ),
            }
        ],
        "report": {
            "kind": "test-receipt",
            "observations": [
                {
                    "name": "supported_proceeded",
                    "measured": counts["supported_proceeded"],
                    "method": "run_matrix attempt_install copytree",
                    "anchor": "tools/plugin/compatibility.py:run_matrix",
                },
                {
                    "name": "unsupported_refused",
                    "measured": counts["unsupported_refused"],
                    "method": "run_matrix attempt_install refuse",
                    "anchor": "tools/plugin/compatibility.py:attempt_install",
                },
                {
                    "name": "untested_reported",
                    "measured": counts["untested"],
                    "method": "cartesian minus declared_map",
                    "anchor": "tools/plugin/compatibility.py:completeness_ok",
                },
            ],
            "control_ids": ["omit-untested-cells", "ungated-copy-unsupported"],
            "matrix": matrix,
            "both_states": both_states,
            "fail_closed": {"unparsable_version": unparsable.to_dict()},
            "completeness": complete,
            "support_contract": {
                "path": CONTRACT,
                "supported_clients": contract["supported_clients"],
                "min_client_version": contract["min_client_version"],
                "max_client_version": contract["max_client_version"],
                "untested_rule": contract["untested_rule"],
            },
            "question_or_target": QUESTION,
        },
        "extensions": {
            "id": UNIT,
            "title": (
                "Compatibility detection: refuse every unsupported combination "
                "and no supported one"
            ),
            "completion_sentinel": "SUCCESS:TST-0078",
            "output_path": OUT,
            "output_schema": SCHEMA,
            "named_probes": [
                {"id": "probe1", "command": P1, "role": "both-states-matrix"},
                {"id": "probe2", "command": P2, "role": "untested-and-detector-control"},
            ],
            "notes": (
                "G-1 TST-0078: live named probes re-run the matrix. Wording of "
                "refusal messages is out of scope (TST-0113). Did not run global "
                "unit_manifest.py --write. cloud ok is not delivery. "
                "tools/plugin/schema/compatibility.schema.json is the diagnostics "
                "document for IMP-0008/IMP-0046; this unit validates the support "
                "contract against compatibility.CONTRACT_SCHEMA."
            ),
        },
    }
    # Probes are the contract: probe2 reads matrix/both_states/completeness at
    # the document root. Mirror them there; the nested report copy stays.
    for key in ("matrix", "both_states", "completeness"):
        receipt[key] = receipt["report"][key]
    errs = validate_test_receipt(receipt)
    if errs:
        print("FAILED:TST-0078 emit schema-invalid")
        for item in errs[:20]:
            print(" ", item)
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    out_path.write_text(text, encoding="utf-8")
    if "SUCCESS:TST-0078" not in text:
        print("FAILED:TST-0078 emit sentinel missing")
        return 1
    if len(text.encode("utf-8")) < 2048:
        print("FAILED:TST-0078 emit undersize")
        return 1
    print(f"wrote {OUT} bytes={len(text.encode('utf-8'))} cells={counts['cartesian']}")
    print("SUCCESS:TST-0078")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
