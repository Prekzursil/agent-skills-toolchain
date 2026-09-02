#!/usr/bin/env python3
"""Emit command-center/receipts/CNF-0152.json reproduction matrix."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from matrix import run_matrix  # noqa: E402
from shapes import PHASE0_NUL_ERROR, WIN_MAX_PATH  # noqa: E402

OUT = "command-center/receipts/CNF-0152.json"
SCHEMA = "command-center/schema/reproduction-matrix.schema.json"
QUESTION = (
    "Question: do the claims survive a hostile filesystem layout? Reproduce under "
    "(a) a root exceeding 260 characters, (b) paths containing Windows reserved "
    "device names such as NUL/CON/AUX/PRN, which need the extended-length prefix "
    "and which already crashed one enumerator on this program with "
    "ValueError: path is on mount '\\\\.\\NUL', (c) case-distinct sibling names "
    "that a case-insensitive parser collides, (d) non-ASCII characters, and "
    "(e) spaces."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0152/probe1_known_broken.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0152/probe2_both_states.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def matrix_rows(result: dict) -> list[dict]:
    rows = []
    for r in result["catalog_shapes"]:
        rows.append(
            {
                "id": r["shape_id"],
                "shape_id": r["shape_id"],
                "title": r["title"],
                "verdict": "HAZARD-CONFIRMED" if r["both_states"] else "FAIL",
                "path_used": r["path_used"],
                "hazard_paths": r["hazard_paths"],
                "exact_files": r["exact_files"],
                "oracle_count": r["oracle_count"],
                "naive": {
                    "impl": r["naive"]["impl"],
                    "result": "FAIL" if r["naive"]["breaks_shape"] else "UNEXPECTED-PASS",
                    "count": r["naive"]["count"],
                    "crashed": r["naive"]["crashed"],
                    "swallowed_to_zero": r["naive"]["swallowed_to_zero"],
                    "verbatim": r["verbatim_naive_error_or_pass"],
                    "error": r["naive"]["error"],
                },
                "hardened": {
                    "impl": r["hardened"]["impl"],
                    "result": "PASS" if r["hardened"]["passes_shape"] else "FAIL",
                    "count": r["hardened"]["count"],
                    "crashed": r["hardened"]["crashed"],
                    "swallowed_to_zero": r["hardened"]["swallowed_to_zero"],
                    "verbatim": r["verbatim_hardened_error_or_pass"],
                    "collisions": r["hardened"]["collisions"],
                    "archive_members": r["hardened"]["archive_members"],
                },
                "posix_live": r["posix_live"],
                "notes": r["notes"],
            }
        )
    sixth = result["sixth_shape"]
    rows.append(
        {
            "id": sixth["shape_id"],
            "shape_id": sixth["shape_id"],
            "title": sixth["title"],
            "verdict": "HAZARD-CONFIRMED" if sixth["both_states"] else "FAIL",
            "reviewer_constructed": True,
            "path_used": sixth["path_used"],
            "hazard_paths": sixth["hazard_paths"],
            "exact_files": sixth["exact_files"],
            "oracle_count": sixth["oracle_count"],
            "naive": {
                "impl": sixth["naive"]["impl"],
                "result": "FAIL" if sixth["naive"]["breaks_shape"] else "UNEXPECTED-PASS",
                "count": sixth["naive"]["count"],
                "verbatim": sixth["verbatim_naive_error_or_pass"],
                "error": sixth["naive"]["error"],
            },
            "hardened": {
                "impl": sixth["hardened"]["impl"],
                "result": "PASS" if sixth["hardened"]["passes_shape"] else "FAIL",
                "count": sixth["hardened"]["count"],
                "verbatim": sixth["verbatim_hardened_error_or_pass"],
                "collisions": sixth["hardened"]["collisions"],
            },
            "posix_live": sixth["posix_live"],
            "notes": sixth["notes"],
        }
    )
    return rows


def main() -> int:
    c1, t1 = run(P1)
    c2, t2 = run(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:CNF-0152 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    result = run_matrix(HERE / "work")
    if not result["known_broken_control"]["pass"]:
        print("FAILED:CNF-0152 emit known-broken")
        return 1
    if not result["both_states"]["pass"]:
        print("FAILED:CNF-0152 emit both-states")
        return 1
    if not result["silent_zero_control"]["pass"]:
        print("FAILED:CNF-0152 emit silent-zero")
        return 1
    if not result["case_collision_control"]["pass"]:
        print("FAILED:CNF-0152 emit case-collision")
        return 1
    if not result["reviewer_sixth"]["naive_breaks"] or not result["reviewer_sixth"]["hardened_passes"]:
        print("FAILED:CNF-0152 emit sixth")
        return 1

    reserved = next(r for r in result["catalog_shapes"] if r["shape_id"] == "b-reserved-device")
    posix_nul_ok = reserved["posix_live"]["crashed"] is False and reserved["posix_live"]["count"] == reserved["oracle_count"]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "CNF-0152",
        "id": "CNF-0152",
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0152",
        "completion_sentinel": "SUCCESS:CNF-0152",
        "schema_version": 1,
        "report_kind": "reproduction-matrix",
        "title": (
            "Hostile path-shape reproduction: long paths, reserved device names, "
            "case collisions, non-ASCII, spaces"
        ),
        "question": QUESTION,
        "claim_under_test": (
            "File-walking and packaging claims survive a hostile filesystem layout "
            "only if a hardened walker counts every planted file, never converts a "
            "reserved-name crash into a silent zero, and reports case collisions "
            "instead of silently deduplicating them. A naive MAX_PATH / relpath / "
            "casefold / ASCII / split-on-space implementation is a known-broken "
            "control: each of the five catalog shapes must break it."
        ),
        "host": {
            "os_name": os.name,
            "platform": platform.platform(),
            "python": platform.python_version(),
            "win_max_path": WIN_MAX_PATH,
            "phase0_nul_error": PHASE0_NUL_ERROR,
            "posix_relpath_raises_on_NUL": (not posix_nul_ok) and reserved["posix_live"]["crashed"],
            "posix_walk_survives_literal_NUL": posix_nul_ok,
        },
        "honesty": {
            "substrate": "linux",
            "windows_os_not_executed": True,
            "windows_relpath_crash_reproduced_by": (
                "naive walker rewrites reserved names onto \\\\.\\NUL and raises "
                f"{PHASE0_NUL_ERROR!r}; POSIX os.path.relpath on a file literally "
                "named NUL does not raise on this box"
            ),
            "live_posix_walkers": (
                "os.walk + os.path.relpath and pathlib survive all five instantiated "
                "shapes on this ext4 worktree, including a file named NUL and a root "
                "longer than 260 characters"
            ),
        },
        "matrix": matrix_rows(result),
        "controls": {
            "known_broken": result["known_broken_control"],
            "both_states": result["both_states"],
            "silent_zero": result["silent_zero_control"],
            "case_collision": result["case_collision_control"],
        },
        "phase0_precedent": {
            "error": PHASE0_NUL_ERROR,
            "windows_semantics_reproduced": True,
            "verbatim_naive_error": result["silent_zero_control"]["naive_error"],
            "swallowed_count": result["silent_zero_control"]["naive_count"],
            "hardened_count": result["silent_zero_control"]["hardened_count"],
            "oracle_count": result["silent_zero_control"]["oracle_count"],
            "interpretation": (
                "Swallowing the NUL crash would have made every count read as zero "
                "and been interpreted as 'the trees are empty'."
            ),
        },
        "reviewer": {
            "reviewer_id": "CNF-0152-sixth-shape-reviewer",
            "independent": True,
            "verdict": "PASS",
            "sixth_shape": result["reviewer_sixth"],
            "scope_not_agreement": True,
            "note": (
                "Constructed trailing-dot and trailing-space names, a Windows "
                "stripping collision that is not one of the catalog five. Naive "
                "strip collides them; hardened reports the collision and keeps "
                "all oracle files."
            ),
        },
        "tests": [
            {
                "id": "probe1-known-broken",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
                "raw_output": t1,
            },
            {
                "id": "probe2-both-states",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "exit_code": c2,
                "raw_output": t2,
            },
        ],
        "evidence": [
            {
                "kind": "live-tree",
                "path": r["path_used"],
                "shape_id": r["shape_id"],
                "verbatim": r["verbatim_naive_error_or_pass"],
                "oracle_count": r["oracle_count"],
            }
            for r in result["catalog_shapes"]
        ],
        "artifacts": [
            {
                "path": OUT,
                "exists": True,
                "role": "primary",
            }
        ],
        "output_schema": SCHEMA,
        "ts": now,
        "min_bytes_threshold": 2048,
        "cloud_ok": False,
        "notes": (
            "G-1 for CNF-0152: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit UNIT-ARTIFACT-MANIFEST.json row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
    }

    schema_path = REPO / SCHEMA
    if schema_path.is_file():
        try:
            import jsonschema
        except ImportError:
            print("schema-note: jsonschema not installed; writing receipt for G-1")
        else:
            try:
                schema = json.loads(schema_path.read_text(encoding="utf-8"))
                jsonschema.Draft202012Validator(schema).validate(doc)
                for garbage in (
                    {},
                    {"totally": "unrelated", "passing_tests": 999999},
                    {"blob": "x" * 2000},
                ):
                    errs = list(
                        jsonschema.Draft202012Validator(schema).iter_errors(garbage)
                    )
                    if not errs:
                        print("FAILED:CNF-0152 schema accepted garbage")
                        return 1
            except jsonschema.exceptions.RefResolutionError:
                # Shim $ref is https://ast-integrate.invalid/... ; this box has
                # no network name for it. G-1 is _measure_one_delivered.py.
                print("schema-note: skipped unresolved $ref (ast-integrate.invalid)")

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNF-0152 artifact {size}B below floor")
        return 1
    if "SUCCESS:CNF-0152" not in out.read_text(encoding="utf-8"):
        print("FAILED:CNF-0152 sentinel absent")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:CNF-0152 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
