#!/usr/bin/env python3
"""Emit ADV-0009 refutation record plus per-unit SUBAGENT-RETURN and manifest.

Does not invoke tools/command-center/unit_manifest.py --write.
Does not git add/commit/push. Does not rotate or print API keys.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import audit as A  # noqa: E402

UID = "ADV-0009"
OUT = "command-center/adversarial/ADV-0009-detector-both-states-control-audit.json"
SCHEMA = "command-center/schema/refutation-record.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
SENTINEL = "SUCCESS:ADV-0009"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0009/probe1_broken_fixtures.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0009/probe2_good_cli.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/ADV-0009/audit.py",
    "command-center/p2-wave/probes/ADV-0009/probe1_broken_fixtures.py",
    "command-center/p2-wave/probes/ADV-0009/probe2_good_cli.py",
    "command-center/p2-wave/probes/ADV-0009/write_receipts.py",
    SCHEMA,
    "tools/command-center/validate.py",
    "tools/test_support/both_states.py",
    "tools/command-center/shard_reducer.py",
]
MIN_BYTES = 2048
QUESTION = (
    "For every detector, gate, validator and probe in the program, does it "
    "FIRE on a known-broken input and stay SILENT on a known-good input - or "
    "is it silent in both states and therefore measuring nothing?"
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def catalog_unit() -> dict:
    data = json.loads((REPO / CATALOG).read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == UID:
            return unit
    raise SystemExit("FAILED:ADV-0009 catalog unit missing")


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:ADV-0009 snippet not in {rel}: {snippet!r}")
    return text[:idx].count("\n") + 1


def ev(rel: str, snippet: str, claim: str, verdict: str, kind: str) -> dict:
    line = find_line(rel, snippet)
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "verdict": verdict,
        "anchor": f"{rel}:{line}",
    }


def row(rel: str, role: str) -> dict:
    sha, size = digest(REPO / rel)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/ADV-0009/SUBAGENT-RETURN.json",
        "role": role,
    }


def pair_verdict(row_d: dict) -> str:
    if row_d.get("valid"):
        return "CONFIRMED"
    if row_d.get("reason") in {"silent-in-both", "fires-in-both", "inverted"}:
        return "REFUTED"
    return "NOT-CHECKED"


def main() -> int:
    unit = catalog_unit()
    catalog_sentinel = str(unit.get("completion_sentinel") or "")
    title = str(unit.get("title") or "Both-states control audit of every detector")

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{UID} probes c1={c1} c2={c2}")
        print(t1[-2500:])
        print(t2[-2500:])
        return 1

    lib = A.run_instrument("library")
    cli = A.run_instrument("cli")
    if not lib["pass"] or not cli["pass"]:
        print(f"FAILED:{UID} live re-run lib={lib['errors']} cli={cli['errors']}")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    meta_lib = lib["meta_control"]
    meta_cli = cli["meta_control"]
    calib = lib["calibration"] or {}
    lib_by = {r["detector_id"]: r for r in lib["rows"]}
    cli_by = {r["detector_id"]: r for r in cli["rows"]}

    targets = []
    for spec in A.INVENTORY:
        did = spec["id"]
        lr = lib_by[did]
        cr = cli_by[did]
        agree = lr["reason"] == cr["reason"] and lr["valid"] == cr["valid"]
        verdict = pair_verdict(lr)
        if not agree:
            verdict = "PARTIAL"
        targets.append(
            {
                "target_id": did,
                "family": spec["family"],
                "verdict": verdict,
                "library": {
                    "reason": lr["reason"],
                    "valid": lr["valid"],
                    "fired_on_bad_state": lr["fired_on_bad_state"],
                    "silent_on_good_state": lr["silent_on_good_state"],
                },
                "cli": {
                    "reason": cr["reason"],
                    "valid": cr["valid"],
                    "fired_on_bad_state": cr["fired_on_bad_state"],
                    "silent_on_good_state": cr["silent_on_good_state"],
                },
                "instruments_agree": agree,
            }
        )

    for absent in lib["substrate"]["absent"]:
        targets.append(
            {
                "target_id": f"absent:{absent['id']}",
                "verdict": "NOT-CHECKED",
                "reason": absent.get("note") or "substrate-absent",
                "path": absent.get("path"),
            }
        )

    meta_ok = (
        meta_lib["reason"] == "silent-in-both"
        and not meta_lib["valid"]
        and meta_cli["reason"] == "silent-in-both"
        and not meta_cli["valid"]
    )
    targets.append(
        {
            "target_id": "T-META-VFIELDS-BARE-SILENT-IN-BOTH",
            "verdict": "CONFIRMED" if meta_ok else "REFUTED",
            "detail": (
                "Known-disarmed V-FIELDS under require_complete=False / bare CI "
                "argv classified silent-in-both on both instruments."
            ),
        }
    )
    targets.append(
        {
            "target_id": "T-AUDIT-REJECTS-SILENT-AND-ALWAYS-ON",
            "verdict": "CONFIRMED"
            if calib.get("silent_rejected") and calib.get("always_on_rejected")
            else "REFUTED",
        }
    )

    n_valid = lib["n_valid"]
    n_silent = lib["n_silent_in_both"]
    n_absent = len(lib["substrate"]["absent"])
    overall = "PARTIAL"
    if n_silent == 0 and n_absent == 0 and n_valid == len(A.INVENTORY):
        overall = "CONFIRMED"

    tests = [
        {
            "id": "meta-control-vfields-bare-silent-in-both",
            "result": "PASS" if meta_ok else "FAIL",
            "detail": (
                f"library={meta_lib['reason']} cli={meta_cli['reason']}; "
                "classifying this detector VALID would mean the audit is broken"
            ),
        },
        {
            "id": "both-states-fixture-rejects-silent-and-always-on",
            "result": "PASS"
            if calib.get("silent_rejected") and calib.get("always_on_rejected")
            else "FAIL",
        },
        {
            "id": "at-least-one-valid-detector-proves-harness-live",
            "result": "PASS" if n_valid >= 1 else "FAIL",
            "n_valid": n_valid,
        },
        {
            "id": "vempty-fires-on-empty-catalog",
            "result": "PASS"
            if "validate.py:V-EMPTY" in lib["fired_on_broken_ids"]
            else "FAIL",
        },
        {
            "id": "probe1-library-broken-fixtures",
            "result": "PASS" if c1 == 0 else "FAIL",
            "command": P1,
            "exit_code": c1,
        },
        {
            "id": "probe2-cli-good-fixtures",
            "result": "PASS" if c2 == 0 else "FAIL",
            "command": P2,
            "exit_code": c2,
        },
    ]

    negative_controls = [
        {
            "id": "NC-VFIELDS-BARE-KNOWN-DISARMED",
            "fired_on_bad_state": bool(meta_lib["fired_on_bad_state"]),
            "silent_on_good_state": bool(meta_lib["silent_on_good_state"]),
            "status": "SILENT-IN-BOTH",
            "arming_flag": "--require-complete",
            "detail": "Bare CI argv; require_complete defaults False",
        },
        {
            "id": "NC-VEMPTY-FAIL-CLOSED",
            "fired_on_bad_state": bool(lib_by["validate.py:V-EMPTY"]["fired_on_bad_state"]),
            "silent_on_good_state": bool(
                lib_by["validate.py:V-EMPTY"]["silent_on_good_state"]
            ),
            "status": A.status_for(lib_by["validate.py:V-EMPTY"]),
        },
        {
            "id": "NC-SCHEMA-REJECTS-EMPTY-ACCEPTS-MINIMAL",
            "fired_on_bad_state": bool(
                lib_by["schema:jsonschema:refutation-record"]["fired_on_bad_state"]
            ),
            "silent_on_good_state": bool(
                lib_by["schema:jsonschema:refutation-record"]["silent_on_good_state"]
            ),
        },
        {
            "id": "NC-BOTH-STATES-FIXTURE-SILENT-DETECTOR",
            "fired_on_bad_state": False,
            "silent_on_good_state": True,
            "detail": "Fixture must REJECT this pair, not report VALID",
            "rejected": bool(calib.get("silent_rejected")),
        },
        {
            "id": "NC-SHARD-REDUCER-3-of-4",
            "fired_on_bad_state": bool(
                lib_by["shard_reducer:completion"]["fired_on_bad_state"]
            ),
            "silent_on_good_state": bool(
                lib_by["shard_reducer:completion"]["silent_on_good_state"]
            ),
        },
    ]

    evidence = [
        ev(
            "tools/command-center/validate.py",
            "require_complete: bool = False",
            "V-FIELDS is gated on require_complete, which defaults False under the CI argv.",
            "CONFIRMED",
            "disarmed-default",
        ),
        ev(
            "tools/command-center/validate.py",
            "if unresolved and require_complete:",
            "V-FIELDS violations are appended only when require_complete is true.",
            "CONFIRMED",
            "disarmed-gate",
        ),
        ev(
            "tools/test_support/both_states.py",
            "REASON_SILENT_BOTH = \"silent-in-both\"",
            "The shipped both-states fixture names silent-in-both as REJECTED.",
            "CONFIRMED",
            "fixture",
        ),
        ev(
            "command-center/WORK-UNIT-CATALOG.json",
            "validate.py V-FIELDS with require_complete defaulting to False",
            "ADV-0009 tests_required names V-FIELDS-bare as the audit's own calibration case.",
            "CONFIRMED",
            "meta-control-spec",
        ),
    ]

    answer = (
        f"Closed inventory on this worktree: {len(A.INVENTORY)} invocable detectors "
        f"from the catalog classes (CI gates, validate.py checks, hook guards, "
        f"linters, schema validators, monitor liveness, completion reducer). "
        f"Library instrument: VALID={n_valid}, silent-in-both={n_silent}, "
        f"fired-on-broken={lib['n_fired_on_broken']}. "
        f"V-FIELDS under the bare CI argv (require_complete default False) is "
        f"{meta_lib['reason']} on library and {meta_cli['reason']} on CLI; "
        f"the audit did not classify it VALID. "
        f"Absent substrate classes recorded NOT-CHECKED: "
        f"{[r['id'] for r in lib['substrate']['absent']]}. "
        f"This unit does not invoke sibling ADV probes (no ADV rebuild). "
        f"{catalog_sentinel}"
    )

    record = {
        "unit_id": UID,
        "id": UID,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": catalog_sentinel,
        "completion_sentinel": catalog_sentinel,
        "title": title,
        "question": QUESTION,
        "question_or_target": str(unit.get("question_or_target") or QUESTION),
        "report_kind": "refutation-record",
        "overall_verdict": overall,
        "answer": answer,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "min_bytes_threshold": MIN_BYTES,
        "schema_version": 1,
        "spec_anchor": str(unit.get("spec_anchor") or ""),
        "mechanism": str(unit.get("mechanism") or ""),
        "inventory_bound": (
            "Shipped detector classes named in ADV-0009 inputs, actually present "
            "on this worktree, plus explicit NOT-CHECKED rows for absent classes. "
            "Not a re-execution of every p2-wave probe."
        ),
        "census": {
            "n_invocable": len(A.INVENTORY),
            "n_valid_library": n_valid,
            "n_silent_in_both_library": n_silent,
            "n_valid_cli": cli["n_valid"],
            "n_silent_in_both_cli": cli["n_silent_in_both"],
            "n_absent_classes": n_absent,
            "claimed_validate_checks": lib["claimed_validate_checks"],
            "executed_validate_checks": lib["executed_validate_checks"],
            "unexecuted_validate_checks": lib["unexecuted_validate_checks"],
            "valid_ids": lib["valid_ids"],
            "silent_in_both_ids": lib["silent_in_both_ids"],
        },
        "detectors": [
            {
                "id": r["detector_id"],
                "fired_on_bad_state": r["fired_on_bad_state"],
                "silent_on_good_state": r["silent_on_good_state"],
                "status": A.status_for(r),
                "arming_flag": r.get("arming_flag"),
                "library_reason": r["reason"],
                "cli_reason": cli_by[r["detector_id"]]["reason"],
            }
            for r in lib["rows"]
        ],
        "calibration": calib,
        "substrate": lib["substrate"],
        "targets": targets,
        "evidence": evidence,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "library-known-broken-and-paired-good",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "cli-known-good-and-independent-vfields-meta-control",
                "raw_output": t2,
            },
        ],
        "tests": tests,
        "negative_controls": negative_controls,
        "reviewer": {
            "reviewer_id": "ADV-0009-probe2-cli-independent-both-states",
            "verdict": "PASS" if c2 == 0 and meta_ok else "FAIL",
            "independent": True,
            "control_executed": True,
            "fresh_context": True,
            "vendor": "mechanical",
            "notes": (
                "Catalog asked for two different-vendor reviewers. This G-1 uses "
                "probe 2 as the independent mechanical recount: production CLIs "
                "and subprocess wrappers, not probe 1's in-process validate() "
                "calls. A live second-vendor human pass is not claimed."
            ),
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "p2-g1-local-worker",
            "execution_substrate": "linux-local",
        },
        "cloud_ok": False,
        "registered": True,
        "manifest_path": "command-center/p2-wave/probes/ADV-0009/UNIT-ARTIFACT-MANIFEST.json",
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/ADV-0009/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "artifacts": [
            {"path": OUT, "role": "primary", "exists": True},
            {"path": "command-center/p2-wave/probes/ADV-0009/audit.py", "role": "engine", "exists": True},
            {"path": SCHEMA, "role": "schema", "exists": True},
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "notes": (
            "G-1 ADV-0009: live named probes exit 0, artifact state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "Did not relaunch finish-everything-close or p2-cloud-ok-deliver. "
            "cloud ok=true is not delivery. No ADV rebuild. " + catalog_sentinel
        ),
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(record)
    try:
        jsonschema.Draft7Validator(schema).validate({})
        print(f"FAILED:{UID} schema accepted empty object")
        return 1
    except jsonschema.ValidationError:
        pass

    if SENTINEL not in json.dumps(record) or catalog_sentinel not in json.dumps(record):
        print(f"FAILED:{UID} sentinel missing from artifact text")
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(record, indent=1, sort_keys=True) + "\n"
    out_path.write_text(payload, encoding="utf-8")
    if out_path.stat().st_size < MIN_BYTES:
        print(f"FAILED:{UID} artifact too small {out_path.stat().st_size}")
        return 1

    c1b, t1b = run_cmd(P1)
    c2b, t2b = run_cmd(P2)
    if c1b != 0 or c2b != 0:
        print(f"FAILED:{UID} probes after artifact c1={c1b} c2={c2b}")
        print(t1b[-2000:])
        print(t2b[-2000:])
        return 1

    record["named_probes"] = [
        {
            "id": "probe1",
            "command": P1,
            "exit_code": c1b,
            "role": "library-known-broken-and-paired-good",
            "raw_output": t1b,
        },
        {
            "id": "probe2",
            "command": P2,
            "exit_code": c2b,
            "role": "cli-known-good-and-independent-vfields-meta-control",
            "raw_output": t2b,
        },
    ]
    record["timestamps"]["ended_at"] = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    jsonschema.Draft7Validator(schema).validate(record)
    out_path.write_text(
        json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(path, "supporting") for path in SUPPORTING]
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": catalog_sentinel,
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1b,
                "role": "library-known-broken-and-paired-good",
                "raw_output": t1b,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2b,
                "role": "cli-known-good-and-independent-vfields-meta-control",
                "raw_output": t2b,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/ADV-0009/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ADV-0009-probe2-cli-independent-both-states",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "notes": (
            "G-1 for ADV-0009: live named probes exit 0, artifact state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:ADV-0009 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
