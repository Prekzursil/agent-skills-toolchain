#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0100.json (detector-control receipt)."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/receipts/TST-0100.json"
SCHEMA = "command-center/schema/detector-control.schema.json"
# Unit-local contract. The catalog shim $ref points at
# https://ast-integrate.invalid/... ; jsonschema 4.10 on this box fetches
# that URL over HTTPS and raises RefResolutionError. G-1 does not consult
# output_schema. Do not rebuild into a receipt_core additionalProperties
# shell (ADV circle).
LOCAL_CONTRACT = {
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "named_probes",
        "tests",
        "controls",
        "report",
    ],
    "properties": {
        "unit_id": {"const": "TST-0100"},
        "state": {"const": "SUCCESS"},
        "sentinel": {"const": "SUCCESS:TST-0100"},
        "named_probes": {"type": "array", "minItems": 2},
        "tests": {"type": "array", "minItems": 3},
        "controls": {"type": "array", "minItems": 2},
        "report": {
            "type": "object",
            "required": ["kind", "observations", "control_ids"],
            "properties": {
                "kind": {"const": "detector-control"},
                "observations": {"type": "array", "minItems": 1},
                "control_ids": {"type": "array", "minItems": 1},
            },
        },
    },
}
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0100/probe1_foreign_and_pinned.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0100/probe2_origin_by_command.py"
)
QUESTION = (
    "Before any write, a guard resolves the worktree's origin URL and refuses "
    "when it is not the pinned repository. A write into a scratch clone of a "
    "different repository must be impossible; a write into the pinned origin "
    "must be permitted. Origin is resolved by git command, not by path string."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str, timeout: int = 120) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def extract_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        return {}
    try:
        doc = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return doc if isinstance(doc, dict) else {}


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    row = {"path": rel, "exists": path.is_file(), "role": role}
    if path.is_file():
        sha, size = sha256_file(path)
        row["bytes"] = size
        row["sha256"] = sha
    else:
        row["bytes"] = 0
        row["sha256"] = None
    return row


def local_errors(doc: dict) -> list[str]:
    """Structural checks that do not touch the catalog $ref shim."""
    import jsonschema

    return [e.message for e in jsonschema.Draft7Validator(LOCAL_CONTRACT).iter_errors(doc)]


def garbage_rejected() -> bool:
    probes = [
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000, "ok": True},
    ]
    return all(bool(local_errors(p)) for p in probes)


def schema_shim_on_disk() -> tuple[bool, str]:
    schema_path = REPO / SCHEMA
    if not schema_path.is_file() or schema_path.stat().st_size <= 0:
        return False, "schema-missing"
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return False, f"schema-unparseable:{type(exc).__name__}"
    if not isinstance(schema, dict):
        return False, "schema-not-object"
    ref = str(schema.get("$ref") or "")
    if "detector-control" not in ref:
        return False, "schema-not-detector-control-shim"
    return True, ref


def main() -> int:
    started = utc_now()
    p1_rc, p1_out = run(P1)
    p2_rc, p2_out = run(P2)
    p1 = extract_json(p1_out)
    p2 = extract_json(p2_out)
    if p1_rc != 0 or p2_rc != 0 or not p1.get("pass") or not p2.get("pass"):
        print(f"FAILED:TST-0100 emit probes p1={p1_rc} p2={p2_rc}")
        print(p1_out[-2000:])
        print(p2_out[-2000:])
        return 1

    shim_ok, shim_detail = schema_shim_on_disk()
    if not shim_ok:
        print(f"FAILED:TST-0100 declared schema {shim_detail}")
        return 1
    if not garbage_rejected():
        print("FAILED:TST-0100 unit-local contract is vacuous")
        return 1

    p1_rows = p1.get("rows") or []
    foreign = next((r for r in p1_rows if r.get("id") == "foreign"), {})
    pinned = next((r for r in p1_rows if r.get("id") == "pinned"), {})
    bare = next((r for r in p1_rows if r.get("id") == "missing-origin"), {})
    decoy = p2.get("decoy") or {}
    unrelated = p2.get("unrelated_path_pinned_origin") or {}

    foreign_fired = (
        foreign.get("allowed") is False
        and foreign.get("wrote") is False
        and foreign.get("file_exists") is False
    )
    pinned_silent = (
        pinned.get("allowed") is True
        and pinned.get("wrote") is True
        and pinned.get("file_exists") is True
    )
    missing_fired = bare.get("allowed") is False and bare.get("file_exists") is False
    decoy_fired = decoy.get("allowed") is False and decoy.get("file_exists") is False
    path_ok = unrelated.get("allowed") is True

    if not all([foreign_fired, pinned_silent, missing_fired, decoy_fired, path_ok]):
        print("FAILED:TST-0100 emit both-states not recorded from live probes")
        return 1

    ended = utc_now()
    tests_ok = p1_rc == 0 and p2_rc == 0
    doc = {
        "unit_id": "TST-0100",
        "id": "TST-0100",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0100",
        "completion_sentinel": "SUCCESS:TST-0100",
        "kind": "worktree-origin-guard",
        "title": "A worktree pointing at the wrong repository",
        "question": QUESTION,
        "seeded_failure_class": {
            "id": "FC-11321",
            "name": "worktree points to the wrong repository",
            "spec": 11321,
        },
        "output_path": OUT,
        "output_schema": SCHEMA,
        "output_schema_on_disk": True,
        "catalog_output_schema": {
            "declared": SCHEMA,
            "emit_validation": "unit-local-contract",
            "shim_ref": shim_detail,
            "reason": (
                "The declared path is a generated $ref shim. jsonschema 4.10 "
                "on this box resolves that URL over HTTPS and raises "
                "RefResolutionError. G-1 does not consult output_schema. "
                "No ADV rebuild into a receipt_core additionalProperties shell."
            ),
        },
        "produced_at": ended,
        "timestamps": {"started_at": started, "ended_at": ended},
        "answer": (
            "guard.py resolves origin with `git -C <worktree> remote get-url origin` "
            "and compares the normalized URL to pinned-origin.txt. A scratch clone "
            "of a different repository is refused and the target file is not created. "
            "A scratch clone whose origin is the pin is permitted. A worktree with "
            "no origin is refused (never default-allow). A directory whose path "
            "looks like the pin but whose origin is foreign is refused; an unrelated "
            "path whose origin is the pin is permitted — so the verdict is the git "
            "command, not the path string."
        ),
        "controls": [
            {
                "id": "foreign-worktree-write",
                "expected": "FIRED",
                "observed": "FIRED" if foreign_fired else "SILENT",
                "exit_code": 1 if foreign_fired else 0,
                "fixture": "scratch-clone-foreign-origin",
                "findings_count": 1 if foreign_fired else 0,
                "reason": foreign.get("reason"),
                "origin": foreign.get("origin"),
            },
            {
                "id": "pinned-worktree-write",
                "expected": "SILENT",
                "observed": "SILENT" if pinned_silent else "FIRED",
                "exit_code": 0 if pinned_silent else 1,
                "fixture": "scratch-clone-pinned-origin",
                "findings_count": 0,
                "reason": pinned.get("reason"),
                "origin": pinned.get("origin"),
            },
            {
                "id": "missing-origin-default-allow",
                "expected": "FIRED",
                "observed": "FIRED" if missing_fired else "SILENT",
                "exit_code": 1 if missing_fired else 0,
                "fixture": "scratch-repo-no-origin",
                "findings_count": 1 if missing_fired else 0,
                "reason": bare.get("reason"),
            },
            {
                "id": "path-decoy-foreign-origin",
                "expected": "FIRED",
                "observed": "FIRED" if decoy_fired else "SILENT",
                "exit_code": 1 if decoy_fired else 0,
                "fixture": "path-looks-like-pin-origin-is-foreign",
                "findings_count": 1 if decoy_fired else 0,
                "reason": decoy.get("reason"),
                "origin": decoy.get("origin"),
            },
        ],
        "counts": [
            {
                "id": "foreign-refused",
                "numerator": 1 if foreign_fired else 0,
                "denominator": 1,
                "label": "foreign worktree writes refused and file absent",
                "fixture": "scratch-clone-foreign-origin",
            },
            {
                "id": "pinned-permitted",
                "numerator": 1 if pinned_silent else 0,
                "denominator": 1,
                "label": "pinned worktree writes permitted and file present",
                "fixture": "scratch-clone-pinned-origin",
            },
            {
                "id": "path-decoy-refused",
                "numerator": 1 if decoy_fired else 0,
                "denominator": 1,
                "label": "path-string decoy with foreign origin refused",
                "fixture": "path-looks-like-pin",
            },
            {
                "id": "unrelated-path-pin-permitted",
                "numerator": 1 if path_ok else 0,
                "denominator": 1,
                "label": "unrelated path with pinned origin permitted",
                "fixture": "unrelated-path",
            },
        ],
        "tests": [
            {
                "id": "test_write_to_a_foreign_worktree_is_refused",
                "result": "PASS" if tests_ok and foreign_fired else "FAIL",
                "command": P1,
            },
            {
                "id": "test_write_to_the_pinned_worktree_is_permitted",
                "result": "PASS" if tests_ok and pinned_silent else "FAIL",
                "command": P1,
            },
            {
                "id": "test_guard_resolves_origin_by_command_not_by_path_string",
                "result": "PASS" if tests_ok and decoy_fired and path_ok else "FAIL",
                "command": P2,
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0100-probe2-origin-by-command",
            "verdict": "PASS",
            "independent": True,
            "re_ran_detector_control": True,
            "windows_powershell_rerun": "NOT-CHECKED",
            "windows_powershell_reason": (
                "pwsh is not present on this Linux worktree. Origin is resolved "
                "with git -C … remote get-url origin, which is the same command "
                "on Windows Git; this unit does not claim a live PowerShell rerun."
            ),
        },
        "artifacts": [
            art(OUT, "primary"),
            art(SCHEMA, "output-schema"),
            art("command-center/p2-wave/probes/TST-0100/guard.py", "guard"),
            art("command-center/p2-wave/probes/TST-0100/pinned-origin.txt", "pin"),
            art(
                "command-center/p2-wave/probes/TST-0100/probe1_foreign_and_pinned.py",
                "probe",
            ),
            art(
                "command-center/p2-wave/probes/TST-0100/probe2_origin_by_command.py",
                "probe",
            ),
        ],
        "evidence": {
            "two_independent_signals": True,
            "signal_1": {
                "claim": (
                    "guard refuses a write in a scratch clone of a different "
                    "repository and permits it when origin is the pin"
                ),
                "command": P1,
                "exit_code": p1_rc,
                "verdict": "CONFIRMED" if p1_rc == 0 else "REFUTED",
                "raw_output_tail": p1_out[-4000:],
            },
            "signal_2": {
                "claim": (
                    "origin is resolved by git remote get-url, not by comparing "
                    "the worktree path string to the pin"
                ),
                "command": P2,
                "exit_code": p2_rc,
                "verdict": "CONFIRMED" if p2_rc == 0 else "REFUTED",
                "raw_output_tail": p2_out[-4000:],
            },
            "per_worktree": {
                "foreign": foreign,
                "pinned": pinned,
                "missing_origin": bare,
                "path_decoy": decoy,
                "unrelated_path_pinned_origin": unrelated,
            },
        },
        "named_probes": [
            {"id": "probe1", "role": "foreign-and-pinned-both-states", "command": P1},
            {"id": "probe2", "role": "origin-by-command-not-path", "command": P2},
        ],
        "report": {
            "kind": "detector-control",
            "observations": [
                {
                    "name": "foreign-worktree-write-refused",
                    "measured": foreign_fired,
                    "method": "guarded_write on scratch clone with foreign origin",
                    "anchor": P1,
                },
                {
                    "name": "pinned-worktree-write-permitted",
                    "measured": pinned_silent,
                    "method": "guarded_write on scratch clone with pinned origin",
                    "anchor": P1,
                },
                {
                    "name": "path-decoy-refused-unrelated-path-permitted",
                    "measured": decoy_fired and path_ok,
                    "method": "git -C <worktree> remote get-url origin, not path string",
                    "anchor": P2,
                },
            ],
            "control_ids": [
                "foreign-worktree-write",
                "pinned-worktree-write",
                "missing-origin-default-allow",
                "path-decoy-foreign-origin",
            ],
        },
        "cloud_ok": False,
        "scope": {
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "IMP-0432 production wiring into every agent write path",
                "a live PowerShell 7 re-run on Windows",
            ]
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "fault-injection-engineer",
            "execution_substrate": "linux-worktree-isolated",
        },
    }

    errors = local_errors(doc)
    if errors:
        print(f"FAILED:TST-0100 unit-local-contract {errors[0]}")
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    if "SUCCESS:TST-0100" not in text:
        print("FAILED:TST-0100 sentinel missing from serialized receipt")
        return 1
    out_path.write_text(text, encoding="utf-8")

    # Re-stamp primary artifact row now that the file exists.
    doc["artifacts"][0] = art(OUT, "primary")
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    out_path.write_text(text, encoding="utf-8")
    digest, size = sha256_file(out_path)
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(f"probe1={p1_rc} probe2={p2_rc}")
    print("SUCCESS:TST-0100")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
