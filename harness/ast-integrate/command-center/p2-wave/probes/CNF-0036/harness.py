"""Run repeat-application, create-if-missing, and detector-control measurements."""
from __future__ import annotations

import tempfile
from pathlib import Path

from census import hash_bytes, record
from lifecycle import (
    PAIRS,
    apply_named,
    create_if_missing,
    force_create_truncate,
    non_idempotent_append,
)
from scenario import USER_NOTES, USER_NOTES_BODY, build_snapshot


def second_exit_ok(code: int, message: str) -> bool:
    if code == 0:
        return True
    return "already-applied" in (message or "").lower()


def _apply_record(root: Path, name: str) -> dict:
    code, message = apply_named(root, name)
    return record(root, code, message)


def measure_direction(forward: str, reverse: str, direction: str) -> dict:
    with tempfile.TemporaryDirectory(prefix=f"cnf36-{forward}-{direction}-") as tmp:
        root = build_snapshot(Path(tmp))
        op_name = forward if direction == "forward" else reverse
        if direction == "reverse":
            prep = apply_named(root, forward)
            if prep[0] != 0:
                rec = record(root, prep[0], prep[1])
                return {
                    "name": forward,
                    "direction": direction,
                    "reverse_name": reverse,
                    "apply1": rec,
                    "apply2": rec,
                    "hash_sets_equal": False,
                    "second_exit_ok": False,
                    "safe_to_run_twice": False,
                }
        apply1 = _apply_record(root, op_name)
        apply2 = _apply_record(root, op_name)
        equal = apply1["tree_sha256"] == apply2["tree_sha256"]
        exit2_ok = second_exit_ok(apply2["exit_code"], apply2["message"])
        return {
            "name": forward,
            "direction": direction,
            "reverse_name": reverse,
            "apply1": apply1,
            "apply2": apply2,
            "hash_sets_equal": equal,
            "second_exit_ok": exit2_ok,
            "safe_to_run_twice": bool(equal and exit2_ok and apply1["exit_code"] == 0),
        }


def measure_all_operations() -> list[dict]:
    rows: list[dict] = []
    for forward, reverse in PAIRS:
        rows.append(measure_direction(forward, reverse, "forward"))
        rows.append(measure_direction(forward, reverse, "reverse"))
    return rows


def measure_create_if_missing() -> dict:
    with tempfile.TemporaryDirectory(prefix="cnf36-cim-") as tmp:
        root = build_snapshot(Path(tmp))
        path = root / USER_NOTES
        before = path.read_bytes()
        result = create_if_missing(path, b"I-SHOULD-NOT-LAND\n")
        after = path.read_bytes()
        before_sha, _ = hash_bytes(before)
        after_sha, _ = hash_bytes(after)
        truncated = after != before
        return {
            "probed": True,
            "path": USER_NOTES,
            "existing_non_empty": len(before) > 0,
            "wrote": bool(result["wrote"]),
            "truncated": truncated,
            "byte_identical": after == before,
            "pass": after == before and not result["wrote"] and not truncated,
            "before_sha256": before_sha,
            "after_sha256": after_sha,
            "message": str(result["message"]),
        }


def measure_control() -> dict:
    with tempfile.TemporaryDirectory(prefix="cnf36-ctl-") as tmp:
        root = build_snapshot(Path(tmp))
        path = root / "target" / "control.log"
        code1, msg1 = non_idempotent_append(path)
        apply1 = record(root, code1, msg1)
        code2, msg2 = non_idempotent_append(path)
        apply2 = record(root, code2, msg2)
        equal = apply1["tree_sha256"] == apply2["tree_sha256"]
        return {
            "name": "append-only-log",
            "detected": not equal,
            "hash_sets_equal": equal,
            "pass": not equal,
            "apply1": apply1,
            "apply2": apply2,
        }


def measure_force_create_hazard() -> dict:
    with tempfile.TemporaryDirectory(prefix="cnf36-force-") as tmp:
        root = build_snapshot(Path(tmp))
        path = root / USER_NOTES
        before = path.read_bytes()
        force_create_truncate(path, b"")
        after = path.read_bytes()
        before_sha, _ = hash_bytes(before)
        after_sha, _ = hash_bytes(after)
        truncated = after != before
        path.write_text(USER_NOTES_BODY, encoding="utf-8", newline="\n")
        return {
            "anchor": "rules/common/windows-shell.md section 4 (force-create truncates an existing file)",
            "truncated_existing": truncated,
            "pass_as_data_loss_probe": truncated and before_sha != after_sha,
            "before_sha256": before_sha,
            "after_sha256": after_sha,
        }


def report_payload(doc: dict) -> dict:
    """Domain fields live under report (receipt additionalProperties=false)."""
    report = doc.get("report")
    if isinstance(report, dict):
        merged = dict(report)
        for key in ("operations", "control", "create_if_missing"):
            if key not in merged and key in doc:
                merged[key] = doc[key]
        return merged
    return doc


def run_suite() -> dict:
    operations = measure_all_operations()
    create = measure_create_if_missing()
    control = measure_control()
    force = measure_force_create_hazard()
    names = {(row["name"], row["direction"]) for row in operations}
    expected = {(fwd, d) for fwd, _ in PAIRS for d in ("forward", "reverse")}
    hashes_ok = all(row["hash_sets_equal"] for row in operations)
    exits_ok = all(row["second_exit_ok"] for row in operations)
    return {
        "operations": operations,
        "create_if_missing": create,
        "control": control,
        "force_create_hazard": force,
        "coverage_complete": names == expected,
        "all_ops_safe": hashes_ok and exits_ok and all(row["safe_to_run_twice"] for row in operations),
        "tests": {
            "hash_sets_equal_both_directions": {
                "pass": hashes_ok and names == expected,
                "pairs": len(operations),
            },
            "create_if_missing_no_truncate": {
                "pass": bool(create["pass"]),
                "truncated": create["truncated"],
            },
            "second_exit_already_applied_or_zero": {"pass": exits_ok},
            "non_idempotent_control_detected": {
                "pass": bool(control["pass"] and control["detected"]),
                "name": control["name"],
            },
        },
    }
