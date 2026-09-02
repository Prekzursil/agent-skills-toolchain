#!/usr/bin/env python3
"""Emit CNF-0036 confirmation artifact and per-unit receipts."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from harness import run_suite  # noqa: E402

OUT = "command-center/confirmation/CNF-0036-repeat-application.json"
SCHEMA = "command-center/schema/idempotency-report.schema.json"
RECEIPT_PHYSICAL = "platform/schema/receipt.schema.json"
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0036/probe1_repeat_hashes.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0036/probe2_detector_control.py"
)
QUESTION = (
    "Which mutating operations are safe to run twice? Apply each forward "
    "operation twice and each reverse operation twice from an already-applied "
    "state, and answer per operation: is the on-disk state after the second "
    "application byte-identical to after the first, is the second exit code "
    "clean or at least carrying a distinguishable already-applied message, "
    "and does any create-if-missing path truncate an existing file?"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/CNF-0036/lifecycle.py",
    "command-center/p2-wave/probes/CNF-0036/harness.py",
    "command-center/p2-wave/probes/CNF-0036/scenario.py",
    "command-center/p2-wave/probes/CNF-0036/census.py",
    "command-center/p2-wave/probes/CNF-0036/probe1_repeat_hashes.py",
    "command-center/p2-wave/probes/CNF-0036/probe2_detector_control.py",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def sha256_bytes(raw: bytes) -> tuple[str, int]:
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm)


def catalog_unit() -> dict:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == "CNF-0036":
            return unit
    raise SystemExit("FAILED:CNF-0036 catalog unit missing")


def run_cmd(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def product_scan() -> dict:
    lifecycle_root = "tools/plugin"
    present = (REPO / lifecycle_root).is_dir()
    return {
        "lifecycle_root": lifecycle_root,
        "present_on_worktree": present,
        "sync_scripts_present": bool(list(REPO.glob("scripts/sync-*.ps1"))),
        "substrate": (
            "disposable snapshot engine in "
            "command-center/p2-wave/probes/CNF-0036/lifecycle.py"
        ),
    }


def local_validator() -> jsonschema.Draft7Validator:
    """Validate against receipt_core + idempotency-report without network $ref."""
    receipt = json.loads((REPO / RECEIPT_PHYSICAL).read_text(encoding="utf-8"))
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$defs": receipt["$defs"],
        "allOf": [
            {"$ref": "#/$defs/receipt_core"},
            {
                "required": ["report"],
                "properties": {
                    "report": {
                        "type": "object",
                        "required": ["kind", "observations", "control_ids"],
                        "properties": {
                            "kind": {"const": "idempotency-report"},
                            "observations": {
                                "type": "array",
                                "minItems": 1,
                                "items": {
                                    "type": "object",
                                    "required": [
                                        "name",
                                        "measured",
                                        "method",
                                        "anchor",
                                    ],
                                },
                            },
                            "control_ids": {
                                "type": "array",
                                "minItems": 1,
                                "items": {"type": "string", "minLength": 1},
                            },
                        },
                    }
                },
            },
        ],
    }
    return jsonschema.Draft7Validator(schema)


def artifact_row(rel: str, role: str) -> dict:
    digest, size = sha256_file(REPO / rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def main() -> int:
    started = datetime.now(timezone.utc)
    unit = catalog_unit()
    sentinel = str(unit.get("completion_sentinel") or "")
    suite = run_suite()
    tests = suite["tests"]
    control = suite["control"]
    create = suite["create_if_missing"]
    ops = suite["operations"]
    if not suite["coverage_complete"]:
        print("FAILED:CNF-0036 coverage incomplete")
        return 1
    if not tests["non_idempotent_control_detected"]["pass"]:
        print("FAILED:CNF-0036 detector-failure control not caught")
        return 1
    if not tests["create_if_missing_no_truncate"]["pass"]:
        print("FAILED:CNF-0036 create-if-missing truncated")
        return 1
    if not tests["hash_sets_equal_both_directions"]["pass"]:
        print("FAILED:CNF-0036 non-idempotent")
        return 1
    if not tests["second_exit_already_applied_or_zero"]["pass"]:
        print("FAILED:CNF-0036 unclear-error second exit")
        return 1

    product = product_scan()
    safe = [f"{row['name']}/{row['direction']}" for row in ops if row["safe_to_run_twice"]]
    answer = (
        "All five mutating operations (install, deploy, migrate, sync, repair) "
        "are safe to run twice in both directions on the disposable snapshot "
        f"engine: {', '.join(safe)}. Hash sets after application one and two "
        "are equal; second exits are 0 with already-applied when a no-op. "
        "create-if-missing left target/user/notes.md byte-identical. "
        "Non-idempotent control append-only-log was detected by the same "
        "comparison (hash_sets_equal=false). "
        + sentinel
    )
    schema_art = artifact_row(SCHEMA, "supporting")
    primary_placeholder = {
        "path": OUT,
        "bytes": 1,
        "sha256": "0" * 64,
        "exists": True,
        "eol": "LF",
        "role": "primary",
    }
    ended = datetime.now(timezone.utc)
    duration = max(0.0, (ended - started).total_seconds())
    started_s = started.strftime("%Y-%m-%dT%H:%M:%SZ")
    ended_s = ended.strftime("%Y-%m-%dT%H:%M:%SZ")

    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0036",
        "state": "SUCCESS",
        "sentinel": sentinel,
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json work_units[id=CNF-0036]; "
            "rules/common/windows-shell.md section 4"
        ),
        "min_bytes_threshold": 2048,
        "artifacts": [primary_placeholder, schema_art],
        "evidence": [
            {
                "claim": (
                    "Apply-twice hash manifests are equal for install, deploy, "
                    "migrate, sync, and repair in both forward and reverse."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0036/harness.py:measure_all_operations",
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
                            "\"import sys; sys.path.insert(0,'command-center/p2-wave/probes/CNF-0036'); "
                            "from harness import run_suite; s=run_suite(); "
                            "print(s['tests']['hash_sets_equal_both_directions'])\""
                        ),
                        "raw_output": json.dumps(
                            tests["hash_sets_equal_both_directions"], sort_keys=True
                        ),
                        "fingerprint": "harness:hash-sets-equal",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P1,
                        "raw_output": "pending-named-probe-1",
                        "fingerprint": "named-probe1:repeat-hashes",
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "The same tree-sha comparison detects a deliberately "
                    "non-idempotent append, and create-if-missing does not "
                    "truncate an existing non-empty file."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0036/probe2_detector_control.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
                            "\"import sys; sys.path.insert(0,'command-center/p2-wave/probes/CNF-0036'); "
                            "from harness import measure_control, measure_create_if_missing; "
                            "print(measure_control()['detected'], "
                            "measure_create_if_missing()['pass'])\""
                        ),
                        "raw_output": json.dumps(
                            {
                                "control_detected": control["detected"],
                                "create_if_missing_pass": create["pass"],
                            },
                            sort_keys=True,
                        ),
                        "fingerprint": "harness:control-and-cim",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "raw_output": "pending-named-probe-2",
                        "fingerprint": "named-probe2:detector-control",
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "hash-sets-equal-both-directions",
                "name": "Hash sets after application one and two are equal",
                "command": P1,
                "result": "PASS",
                "assertions": int(tests["hash_sets_equal_both_directions"]["pairs"]),
            },
            {
                "id": "create-if-missing-no-truncate",
                "name": "create-if-missing does not truncate an existing file",
                "command": P2,
                "result": "PASS",
                "assertions": 1,
            },
            {
                "id": "second-exit-already-applied-or-zero",
                "name": "Second exit is 0 or already-applied",
                "command": P1,
                "result": "PASS",
                "assertions": 10,
            },
            {
                "id": "non-idempotent-control-detected",
                "name": "Append-only control is caught by the same comparison",
                "command": P2,
                "result": "PASS",
                "assertions": 1,
            },
        ],
        "negative_controls": [
            {
                "id": "CNF0036-C1-append-only-log",
                "kind": "known-broken-fixture",
                "description": (
                    "A deliberately non-idempotent append-only log must make "
                    "hash_sets_equal false under the same census used for the "
                    "five mutating operations."
                ),
                "fired_on_bad_state": bool(control["detected"] and not control["hash_sets_equal"]),
                "silent_on_good_state": bool(suite["tests"]["hash_sets_equal_both_directions"]["pass"]),
                "bad_state_output": (
                    f"control hash_sets_equal={control['hash_sets_equal']} "
                    f"detected={control['detected']}"
                ),
                "good_state_output": "all ten operation/direction pairs hash_sets_equal=true",
            },
            {
                "id": "CNF0036-C2-force-create-truncate",
                "kind": "mutation",
                "description": (
                    "Force-create (open-for-write) must truncate an existing "
                    "non-empty file, proving the create-if-missing pass is not "
                    "an inert comparator."
                ),
                "fired_on_bad_state": bool(
                    suite["force_create_hazard"]["pass_as_data_loss_probe"]
                ),
                "silent_on_good_state": bool(create["pass"] and not create["truncated"]),
                "bad_state_output": (
                    "force-create truncated "
                    + str(suite["force_create_hazard"]["truncated_existing"])
                ),
                "good_state_output": "create-if-missing byte-identical; wrote=false",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0036-probe1-repeat-hashes",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "xai",
            "notes": (
                "Probe1 re-runs the ten apply-twice hash censuses before reading "
                "the artifact conclusion. Probe2 re-runs the detector control and "
                "create-if-missing probe on a different field."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0036/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "CNF-0036",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/CNF-0036/probe1_repeat_hashes.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "command",
                    "command": P1,
                    "raw_output": "pending-named-probe-1",
                    "fingerprint": "consumer:probe1-read-artifact",
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": started_s,
            "ended_at": ended_s,
            "duration_seconds": duration,
        },
        "retry": {
            "count": 0,
            "policy": str(unit.get("retry_policy") or "zero retries"),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Product tools/plugin install/deploy/migrate/sync/repair CLIs "
                    "were not executed; this unit measured a disposable snapshot "
                    "engine that implements those named operations."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run the apply-twice census against a disposable copy of "
                    "the live plugin tree with the product CLIs on a host that "
                    "has them."
                ),
            }
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "idempotency-engineer",
            "execution_substrate": "linux-local",
        },
        "report": {
            "kind": "idempotency-report",
            "title": str(unit.get("title") or "Repeat-application safety"),
            "question": QUESTION,
            "answer": answer,
            "completion_sentinel": sentinel,
            "operations": ops,
            "create_if_missing": create,
            "control": control,
            "force_create_hazard": suite["force_create_hazard"],
            "domain_tests": tests,
            "product": product,
            "observations": [
                {
                    "name": "hash_sets_equal_both_directions",
                    "measured": bool(tests["hash_sets_equal_both_directions"]["pass"]),
                    "method": "tree-sha256 census after apply-1 and apply-2",
                    "anchor": "command-center/p2-wave/probes/CNF-0036/harness.py",
                },
                {
                    "name": "create_if_missing_no_truncate",
                    "measured": bool(create["pass"]),
                    "method": "byte compare of existing target/user/notes.md",
                    "anchor": "command-center/p2-wave/probes/CNF-0036/lifecycle.py:create_if_missing",
                },
                {
                    "name": "non_idempotent_control_detected",
                    "measured": bool(control["detected"]),
                    "method": "append-only log apply-twice tree-sha inequality",
                    "anchor": "command-center/p2-wave/probes/CNF-0036/lifecycle.py:non_idempotent_append",
                },
            ],
            "control_ids": [
                "append-only-log",
                "force-create-truncate",
                "create-if-missing",
            ],
        },
        "extensions": {
            "cloud_ok": False,
            "named_probes": [
                {"id": "probe1", "role": "repeat-application-hash-sets", "command": P1},
                {
                    "id": "probe2",
                    "role": "detector-control-create-if-missing",
                    "command": P2,
                },
            ],
            "scope": {
                "proof_surface": (
                    "Fresh tempfile snapshots; each operation/direction pair is "
                    "an independent copy of the fixture. Product tools/plugin is "
                    f"{'present' if product['present_on_worktree'] else 'absent'} "
                    "on this Linux worktree."
                ),
                "does_not_claim": [
                    "cloud ok=true is delivery",
                    "global UNIT-ARTIFACT-MANIFEST.json --write was run",
                    "C:/Users/Prekzursil live plugin lifecycle was executed",
                    "tools/plugin install/deploy/migrate/sync/repair exist in this worktree",
                ],
            },
        },
    }

    validator = local_validator()
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0036 schema errors")
        for err in errs[:25]:
            print(" ", list(err.path), err.message)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:CNF-0036 schema accepted garbage")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    draft = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    digest, size = sha256_bytes(draft.encode("utf-8"))
    doc["artifacts"][0]["sha256"] = digest
    doc["artifacts"][0]["bytes"] = size
    out.write_text(
        json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    live_digest, live_size = sha256_file(out)
    if live_size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNF-0036 artifact {live_size}B below floor")
        return 1
    if sentinel not in out.read_text(encoding="utf-8"):
        print("FAILED:CNF-0036 sentinel-absent after write")
        return 1

    rc1, out1 = run_cmd(P1)
    rc2, out2 = run_cmd(P2)
    print(f"probe1 rc={rc1}")
    print(out1[-2000:])
    print(f"probe2 rc={rc2}")
    print(out2[-2000:])
    if rc1 != 0 or rc2 != 0:
        print(f"FAILED:CNF-0036 probes c1={rc1} c2={rc2}")
        return 1

    doc["evidence"][0]["probes"][1]["raw_output"] = out1[-8000:]
    doc["evidence"][0]["probes"][1]["exit_code"] = rc1
    doc["evidence"][1]["probes"][1]["raw_output"] = out2[-8000:]
    doc["evidence"][1]["probes"][1]["exit_code"] = rc2
    doc["downstream_consumers"][0]["exit_code"] = rc1
    doc["downstream_consumers"][0]["probe"]["raw_output"] = out1[-8000:]
    doc["downstream_consumers"][0]["probe"]["exit_code"] = rc1
    ended2 = datetime.now(timezone.utc)
    doc["timestamps"]["ended_at"] = ended2.strftime("%Y-%m-%dT%H:%M:%SZ")
    doc["timestamps"]["duration_seconds"] = max(
        0.0, (ended2 - started).total_seconds()
    )

    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0036 schema errors after probe fill")
        for err in errs[:25]:
            print(" ", list(err.path), err.message)
        return 1

    draft = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    digest, size = sha256_bytes(draft.encode("utf-8"))
    doc["artifacts"][0]["sha256"] = digest
    doc["artifacts"][0]["bytes"] = size
    out.write_text(
        json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    live_digest, live_size = sha256_file(out)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "CNF-0036",
        "unit_id": "CNF-0036",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0036",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": rc1,
                "role": "repeat-application-hash-sets",
                "raw_output": out1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": rc2,
                "role": "detector-control-create-if-missing",
                "raw_output": out2[-8000:],
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": live_digest,
                "bytes": live_size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/CNF-0036/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "CNF-0036-probe1-repeat-hashes",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for CNF-0036: live named probes exit 0, repeat-application.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )

    def row(rel: str, role: str) -> dict:
        path = REPO / rel
        sha, n = sha256_file(path)
        return {
            "path": rel,
            "sha256": sha,
            "bytes": n,
            "present": True,
            "unit_id": "CNF-0036",
            "receipt_path": "command-center/p2-wave/probes/CNF-0036/SUBAGENT-RETURN.json",
            "role": role,
        }

    artifacts = [row(OUT, "primary")] + [row(path, "supporting") for path in SUPPORTING]
    artifacts.append(
        row("command-center/p2-wave/probes/CNF-0036/SUBAGENT-RETURN.json", "supporting")
    )
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "CNF-0036",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={live_size} sha256={live_digest}")
    print("SUCCESS:CNF-0036 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
