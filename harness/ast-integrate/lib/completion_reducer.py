"""Twelve-condition completion reducer (IMP-0415).

Exit code is never a success predicate. fold_verdict does not read exit_code.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONDITION_IDS = tuple(f"C{i}" for i in range(1, 13))
COMPLETION = frozenset({"SUCCESS", "COMPLETE", "PASS", "DELIVERED"})


def condition_line_table() -> list[dict[str, Any]]:
    src = Path(__file__).read_text(encoding="utf-8").splitlines()
    rows = []
    for cid in CONDITION_IDS:
        needle = f"def _check_{cid.lower()}("
        line = next((i + 1 for i, s in enumerate(src) if needle in s), 0)
        rows.append({"id": cid, "line": line, "gap": line == 0})
    return rows


def _art_path(record: dict[str, Any], root: Path) -> Path | None:
    rel = record.get("artifact_path")
    if not rel:
        arts = record.get("artifacts") or []
        if arts and isinstance(arts[0], dict):
            rel = arts[0].get("path")
    if not rel:
        return None
    return root / str(rel).replace("\\", "/")


def _check_c1(record: dict[str, Any], root: Path) -> tuple[bool, str]:
    state = str(record.get("state") or "").upper()
    return state in COMPLETION, "state is not a completion terminal"


def _check_c2(record: dict[str, Any], root: Path) -> tuple[bool, str]:
    path = _art_path(record, root)
    return bool(path and path.is_file()), "expected artifact does not exist on disk"


def _check_c3(record: dict[str, Any], root: Path) -> tuple[bool, str]:
    path = _art_path(record, root)
    if not path or not path.is_file():
        return False, "artifact empty or missing"
    floor = int(record.get("min_bytes_threshold") or 0)
    return path.stat().st_size >= floor, "artifact below min_bytes_threshold"


def _check_c4(record: dict[str, Any], root: Path) -> tuple[bool, str]:
    path = _art_path(record, root)
    schema_rel = record.get("schema_path")
    if not path or not path.is_file():
        return False, "artifact missing for schema parse"
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, "artifact does not parse"
    if schema_rel:
        schema_path = root / str(schema_rel)
        if schema_path.is_file():
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            required = schema.get("required") or []
            if any(k not in doc for k in required):
                return False, "artifact does not parse against its schema"
    return True, "ok"


def _check_c5(record: dict[str, Any], root: Path) -> tuple[bool, str]:
    needle = str(record.get("sentinel") or "")
    path = _art_path(record, root)
    if not needle or not path or not path.is_file():
        return False, "required sentinel is absent"
    return needle in path.read_text(encoding="utf-8"), "required sentinel is absent"


def _check_c6(record: dict[str, Any], root: Path) -> tuple[bool, str]:
    evidence = record.get("evidence")
    if not isinstance(evidence, list) or len(evidence) < 2:
        return False, "required evidence anchors are missing"
    for item in evidence:
        if not isinstance(item, dict) or not (item.get("anchor") or item.get("path")):
            return False, "required evidence anchors are missing"
    return True, "ok"


def _check_c7(record: dict[str, Any], root: Path) -> tuple[bool, str]:
    tests = record.get("tests")
    if not isinstance(tests, list) or not tests:
        return False, "required tests did not run and pass"
    for row in tests:
        if not isinstance(row, dict) or str(row.get("result") or "").upper() != "PASS":
            return False, "required tests did not run and pass"
    return True, "ok"


def _check_c8(record: dict[str, Any], root: Path) -> tuple[bool, str]:
    controls = record.get("negative_controls")
    if not isinstance(controls, list) or not controls:
        return False, "negative controls did not fail as expected"
    for row in controls:
        if not isinstance(row, dict) or row.get("fired_on_bad_state") is not True:
            return False, "negative controls did not fail as expected"
    return True, "ok"


def _check_c9(record: dict[str, Any], root: Path) -> tuple[bool, str]:
    reviewer = record.get("reviewer")
    if not isinstance(reviewer, dict):
        return False, "independent reviewer status is not PASS"
    if str(reviewer.get("verdict") or "").upper() != "PASS":
        return False, "independent reviewer status is not PASS"
    if reviewer.get("independent") is not True:
        return False, "independent reviewer status is not PASS"
    return True, "ok"


def _check_c10(record: dict[str, Any], root: Path) -> tuple[bool, str]:
    for row in record.get("defects") or []:
        if not isinstance(row, dict):
            continue
        sev = str(row.get("severity") or "").upper()
        status = str(row.get("status") or "open").lower()
        if sev in {"P0", "P1"} and status in {"open", "unresolved", "active", ""}:
            return False, "unresolved P0/P1 defect is attached"
    return True, "ok"


def _check_c11(record: dict[str, Any], root: Path) -> tuple[bool, str]:
    man_rel = (record.get("manifest_registration") or {}).get("manifest_path")
    if not man_rel:
        return False, "output is not registered in the artifact manifest"
    man = root / str(man_rel)
    if not man.is_file():
        return False, "output is not registered in the artifact manifest"
    try:
        doc = json.loads(man.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, "output is not registered in the artifact manifest"
    arts = doc.get("artifacts") or []
    if not arts:
        return False, "output is not registered in the artifact manifest"
    if record.get("manifest_registration", {}).get("registered") is not True:
        return False, "output is not registered in the artifact manifest"
    return True, "ok"


def _check_c12(record: dict[str, Any], root: Path) -> tuple[bool, str]:
    consumers = record.get("downstream_consumers")
    if not isinstance(consumers, list) or not consumers:
        return False, "downstream consumers cannot read it"
    for row in consumers:
        if not isinstance(row, dict):
            return False, "downstream consumers cannot read it"
        if row.get("executed") is not True or row.get("read_ok") is not True:
            return False, "downstream consumers cannot read it"
    return True, "ok"


CHECKS = {
    "C1": _check_c1,
    "C2": _check_c2,
    "C3": _check_c3,
    "C4": _check_c4,
    "C5": _check_c5,
    "C6": _check_c6,
    "C7": _check_c7,
    "C8": _check_c8,
    "C9": _check_c9,
    "C10": _check_c10,
    "C11": _check_c11,
    "C12": _check_c12,
}


def fold_verdict(conditions: list[dict[str, Any]]) -> str:
    if len(conditions) != len(CONDITION_IDS):
        return "INCOMPLETE"
    if any(c.get("result") == "FAIL" for c in conditions):
        return "INCOMPLETE"
    return "COMPLETE"


# --- C3 meaningful-minimum-size API (TST-0007) -----------------------------
# The default floor is CALIBRATED: it is the 0th percentile (observed min) of
# live receipt-class file sizes, measured by probes/TST-0007/calibrate.py.
# It is not a guessed constant (128/512/1024).
MIN_BYTES_DEFAULT = 405


def _min_bytes(record: dict[str, Any]) -> int:
    """Explicit min_bytes/min_bytes_threshold if present, else the calibrated default."""
    for key in ("min_bytes", "min_bytes_threshold"):
        if key in record and record[key] is not None:
            return int(record[key])
    return MIN_BYTES_DEFAULT


def eval_c3_min_size(record: dict[str, Any], root: Path | None = None) -> tuple[str, str]:
    """C3 as a standalone check: artifact size must reach the floor.

    Returns ("PASS"|"FAIL", reason). When the record omits size keys the
    calibrated MIN_BYTES_DEFAULT is exercised.
    """
    base = Path(root) if root is not None else Path(".")
    path = _art_path(record, base)
    floor = _min_bytes(record)
    if not path or not path.is_file():
        return "FAIL", "artifact missing for C3"
    size = path.stat().st_size
    if size <= 0:
        return "FAIL", f"artifact is empty (min={floor})"
    if size < floor:
        return "FAIL", f"bytes={size} below floor (min={floor})"
    return "PASS", f"bytes={size} >= min={floor}"


def reduce_completion(record: dict[str, Any], root: Path | None = None) -> dict[str, Any]:
    root = Path(root) if root is not None else Path(".")
    conditions = []
    for cid in CONDITION_IDS:
        ok, reason = CHECKS[cid](record, root)
        conditions.append(
            {
                "id": cid,
                "result": "PASS" if ok else "FAIL",
                "reason": reason,
            }
        )
    verdict = fold_verdict(conditions)
    return {
        "verdict": verdict,
        "conditions": conditions,
        "exit_code_alone_never_success": True,
    }
