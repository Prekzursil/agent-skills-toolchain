#!/usr/bin/env python3
"""Evidence-quality gate for a host-client × conformance coverage matrix.

A cell may read RUN only when a client VERSION is present and evidence
includes an observation from INSIDE the client (hook_fired / command_resolved).
Installer exit codes are not inside-client evidence. An absent client is
NOT-CHECKED (never PASS, never NOT-APPLICABLE) and must name the install
step. A RUN claim missing a version is NEVER-RUN.
"""
from __future__ import annotations

from typing import Any, Iterable

CELL_STATUSES = frozenset(
    {"RUN", "NEVER-RUN", "NOT-APPLICABLE", "NOT-CHECKED"}
)
INSIDE_KINDS = frozenset(
    {"hook_fired", "command_resolved", "hook_fired", "command_resolved"}
)
INSTALLER_KINDS = frozenset({"installer_exit", "installer_exit"})
FORBIDDEN_ABSENT = frozenset({"PASS", "NOT-APPLICABLE", "RUN", "NEVER-RUN"})


def _kinds(cell: dict[str, Any]) -> set[str]:
    ev = cell.get("evidence") if isinstance(cell.get("evidence"), dict) else {}
    raw = (
        ev.get("observation_kinds")
        or ev.get("observation_kinds")
        or cell.get("observation_kinds")
        or cell.get("observation_kinds")
        or []
    )
    if isinstance(raw, str):
        raw = [raw]
    return {str(k) for k in raw if k}


def _version(cell: dict[str, Any]) -> str:
    ev = cell.get("evidence") if isinstance(cell.get("evidence"), dict) else {}
    for key in ("client_version", "version"):
        val = cell.get(key) or ev.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def client_present(cell: dict[str, Any]) -> bool | None:
    ev = cell.get("evidence") if isinstance(cell.get("evidence"), dict) else {}
    for src in (cell, ev):
        if not isinstance(src, dict):
            continue
        for key in ("client_present", "client_present"):
            if key in src:
                return bool(src[key])
    return None


def has_inside_observation(cell: dict[str, Any]) -> bool:
    return bool(_kinds(cell) & INSIDE_KINDS)


def installer_only(cell: dict[str, Any]) -> bool:
    kinds = _kinds(cell)
    return bool(kinds & INSTALLER_KINDS) and not (kinds & INSIDE_KINDS)


def install_step(cell: dict[str, Any]) -> str:
    ev = cell.get("evidence") if isinstance(cell.get("evidence"), dict) else {}
    for key in ("install_step", "install_step", "enable_step"):
        val = cell.get(key) or ev.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def classify(cell: dict[str, Any]) -> str:
    present = client_present(cell)
    if present is False:
        return "NOT-CHECKED"
    if cell.get("not_applicable") is True or cell.get("not_applicable") is True:
        return "NOT-APPLICABLE"
    if _version(cell) and has_inside_observation(cell):
        return "RUN"
    if present is True:
        return "NEVER-RUN"
    claimed = str(cell.get("status") or "")
    if claimed == "NOT-APPLICABLE":
        return "NOT-APPLICABLE"
    return "NOT-CHECKED"


def downgrade_run_without_version(cell: dict[str, Any]) -> str:
    status = str(cell.get("status") or "")
    if status == "RUN" and not _version(cell):
        return "NEVER-RUN"
    return status


def validate_cell(cell: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    status = str(cell.get("status") or "")
    present = client_present(cell)

    if status == "PASS":
        errors.append("PASS-is-not-a-cell-status")

    if present is False:
        if status != "NOT-CHECKED":
            errors.append("absent-client-must-be-NOT-CHECKED")
        if status in FORBIDDEN_ABSENT:
            errors.append(f"absent-client-must-not-be-{status}")
        if not install_step(cell):
            errors.append("absent-client-needs-install-step")

    if status == "NOT-APPLICABLE" and present is False:
        errors.append("absent-client-is-not-NOT-APPLICABLE")

    if status == "RUN":
        if not _version(cell):
            errors.append("RUN-without-version")
        if not has_inside_observation(cell):
            errors.append("RUN-without-inside-client-observation")
        if installer_only(cell):
            errors.append("installer-exit-only-cannot-be-RUN")
        if not run_bound_to_qualifying_suite(cell):
            errors.append("RUN-evidence-not-bound-to-TST-0049")

    if status and status not in CELL_STATUSES and status != "PASS":
        errors.append(f"unknown-status:{status}")
    return errors


def validate_matrix(cells: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    findings = []
    for i, cell in enumerate(cells):
        errs = validate_cell(cell)
        if errs:
            findings.append(
                {"index": i, "id": cell.get("id"), "errors": errs}
            )
    return findings


validate_cell = validate_cell
downgrade_run_without_version = downgrade_run_without_version
validate_matrix = validate_matrix
installer_only = installer_only

validate_cell = validate_cell
validate_matrix = validate_matrix
installer_only = installer_only


# ---------------------------------------------------------------------------
# D04 closure (2026-10-24): the refutation receipt recorded that this gate
# accepted a forged RUN tied to an unrelated receipt and never enforced the
# declared client set. RUN evidence must now bind to the qualifying suite
# (TST-0049), and matrix completeness is checkable against the declared set.
QUALIFYING_SUITE = "TST-0049"


def _suite_binding(cell: dict[str, Any]) -> str:
    sid = str(cell.get("suite_id") or "").strip()
    if sid:
        return sid
    ev = cell.get("evidence") if isinstance(cell.get("evidence"), dict) else {}
    rec = str(ev.get("receipt") or cell.get("receipt_path") or "")
    if QUALIFYING_SUITE in rec:
        return QUALIFYING_SUITE
    return ""


def run_bound_to_qualifying_suite(cell: dict[str, Any]) -> bool:
    return _suite_binding(cell) == QUALIFYING_SUITE


def cell_client_id(cell: dict[str, Any]) -> str:
    cid = str(cell.get("client_id") or "").strip()
    if cid:
        return cid
    raw = str(cell.get("id") or "")
    if " x " in raw:
        return raw.split(" x ", 1)[0].strip()
    return ""


def check_declared_coverage(
    cells: Iterable[dict[str, Any]], declared_client_ids: Iterable[str]
) -> list[str]:
    seen = {cell_client_id(c) for c in cells}
    seen.discard("")
    return [
        f"declared-client-absent-from-matrix:{c}"
        for c in declared_client_ids
        if c not in seen
    ]


def _main(argv: list[str]) -> int:
    """MATRIX-GATE: structurally and semantically validate a matrix file."""
    import json as _json
    import sys as _sys
    from pathlib import Path as _Path

    if len(argv) < 2:
        print("FAILED:coverage-gate usage coverage_gate.py <matrix.json>")
        return 2
    path = _Path(argv[1])
    if not path.is_file():
        print(f"FAILED:coverage-gate missing {argv[1]}")
        return 1
    doc = _json.loads(path.read_text(encoding="utf-8"))
    cells = doc.get("cells") if isinstance(doc, dict) else doc
    if not isinstance(cells, list):
        print("FAILED:coverage-gate no cells array")
        return 1
    findings = validate_matrix(cells)
    declared = doc.get("declared_client_ids") or []
    if isinstance(doc, dict) and declared:
        missing = check_declared_coverage(cells, declared)
        if missing:
            findings += [{"id": None, "errors": missing}]
    if findings:
        print("FAILED:coverage-gate findings")
        print(_json.dumps(findings[:8], indent=2))
        return 1
    print(f"SUCCESS:coverage-gate cells={len(cells)} declared={len(declared)}")
    return 0


if __name__ == "__main__":
    import sys as _sys

    raise SystemExit(_main(_sys.argv))
