"""Live declared-versus-observed matrix for CNF-0111.

Product layer: NullGate (this worktree has no IMP-0059 interceptor).
Detector-control layer: Gate enabled, same actions, grant present vs absent.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from actions import (
    CRED_ENV,
    OUTSIDE_NAME,
    WRITE_NAME,
    credential_presence,
    fs_write,
    fs_write_outside,
    network_connect,
    prepare_credential_marker,
    process_spawn,
    side_effect_occurred,
)
from enforcement import PERMISSIONS, Gate, NullGate
from product_scan import scan as product_scan

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
MANIFEST = HERE / "fixtures" / "package.manifest.json"

CELL_KEYS = (
    "permission",
    "action",
    "declared",
    "granted",
    "observed",
    "enforcement_outcome",
    "side_effect",
    "evidence",
    "layer",
)


def load_declared() -> list[str]:
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    perms = list(doc["permissions"])
    if perms != list(PERMISSIONS):
        raise RuntimeError(f"manifest permissions {perms} != {list(PERMISSIONS)}")
    return perms


def empty_cells(matrix: list[dict]) -> list[str]:
    bad: list[str] = []
    for i, cell in enumerate(matrix):
        for key in CELL_KEYS:
            val = cell.get(key)
            if val is None or val == "" or val == []:
                bad.append(f"{i}:{key}")
        se = cell.get("side_effect")
        if not isinstance(se, dict) or "occurred" not in se:
            bad.append(f"{i}:side_effect.occurred")
    return bad


def _outcome(granted: bool, observed: str) -> str:
    if granted and observed == "succeeded":
        return "granted-control-succeeded"
    if (not granted) and observed == "blocked":
        return "blocked-at-runtime"
    if (not granted) and observed == "succeeded":
        return "permission-not-enforced"
    if granted and observed == "blocked":
        return "control-blocked-unexpected"
    return "error-indistinguishable"


def _run_one(
    permission: str,
    gate: Gate,
    sandbox: Path,
    marker: Path,
    *,
    granted: bool,
    layer: str,
) -> dict[str, Any]:
    write_path = sandbox / "package-root" / WRITE_NAME
    outside_path = sandbox / OUTSIDE_NAME
    if write_path.exists():
        write_path.unlink()
    if outside_path.exists():
        outside_path.unlink()

    if permission == "filesystem":
        action = "write-inside-root"
        result = fs_write(gate, write_path)
        occurred = side_effect_occurred(write_path, result["observed"])
        census = f"write_path_exists={write_path.exists()}"
        if write_path.exists():
            write_path.unlink()
    elif permission == "network":
        action = "loopback-connect"
        result = network_connect(gate)
        occurred = result["observed"] == "succeeded"
        census = f"connect={result['observed']}"
    elif permission == "process-spawn":
        action = "subprocess-python"
        result = process_spawn(gate)
        occurred = result["observed"] == "succeeded"
        census = f"spawn={result['observed']}"
    elif permission == "credential-read":
        action = "presence-only"
        result = credential_presence(gate, marker)
        occurred = result["observed"] == "succeeded"
        census = (
            "presence-check "
            f"blocked={result['observed']=='blocked'} "
            f"value_read={result.get('value_read')} "
            f"value_printed={result.get('value_printed')}"
        )
        if result.get("value_read") or result.get("value_printed"):
            raise RuntimeError("credential value was read or printed")
    else:
        raise ValueError(permission)

    observed = result["observed"]
    cell = {
        "permission": permission,
        "action": action,
        "declared": permission in gate.declared,
        "granted": granted,
        "observed": observed,
        "enforcement_outcome": _outcome(granted, observed),
        "side_effect": {
            "occurred": occurred,
            "census": census,
            "deny_code": result.get("code"),
        },
        "evidence": (
            f"layer={layer} grant={granted} observed={observed} {census}"
        ),
        "layer": layer,
        "distinguishable_error": result.get("code"),
    }
    return cell


def run_layer(layer: str, declared_full: list[str], sandbox: Path, marker: Path) -> list[dict]:
    cells: list[dict] = []
    for perm in PERMISSIONS:
        for granted in (True, False):
            grant_set = list(declared_full) if granted else [p for p in declared_full if p != perm]
            gate: Gate
            if layer == "product":
                gate = NullGate(grant_set)
            else:
                gate = Gate(grant_set, enabled=True, enforce_containment=True)
            cells.append(
                _run_one(
                    perm,
                    gate,
                    sandbox,
                    marker,
                    granted=granted,
                    layer=layer,
                )
            )
    return cells


def run_outside_root(layer: str, declared_full: list[str], sandbox: Path) -> dict:
    dest = sandbox / OUTSIDE_NAME
    if dest.exists():
        dest.unlink()
    grant = list(declared_full)
    gate: Gate = (
        NullGate(grant)
        if layer == "product"
        else Gate(grant, enabled=True, enforce_containment=True)
    )
    result = fs_write_outside(gate, dest)
    occurred = dest.is_file()
    if dest.exists():
        dest.unlink()
    observed = result["observed"]
    granted = True
    # Declared filesystem does not include write-outside-root.
    outcome = (
        "undeclared-action-succeeded"
        if observed == "succeeded"
        else "blocked-at-runtime"
    )
    return {
        "permission": "filesystem",
        "action": "write-outside-root",
        "declared": False,
        "granted": granted,
        "observed": observed,
        "enforcement_outcome": outcome,
        "side_effect": {
            "occurred": occurred,
            "census": f"outside_exists_after={occurred}",
            "deny_code": result.get("code"),
        },
        "evidence": (
            f"layer={layer} outside-root observed={observed} occurred={occurred}"
        ),
        "layer": layer,
        "distinguishable_error": result.get("code"),
    }


def findings_from(matrix: list[dict]) -> list[dict]:
    out: list[dict] = []
    for cell in matrix:
        if cell["enforcement_outcome"] == "permission-not-enforced":
            out.append(
                {
                    "classification": "permission-not-enforced",
                    "locus": f"{cell['layer']}:{cell['permission']}:{cell['action']}",
                    "detail": (
                        f"Action {cell['action']} succeeded while {cell['permission']} "
                        "was absent from the grant set."
                    ),
                }
            )
        if cell["enforcement_outcome"] == "undeclared-action-succeeded":
            kind = (
                "undeclared-action"
                if cell["action"] == "write-outside-root"
                else "excessive-permission"
            )
            # Catalog: undeclared success is an excessive-permission finding even when benign.
            out.append(
                {
                    "classification": "excessive-permission"
                    if kind == "excessive-permission"
                    else "undeclared-action",
                    "locus": f"{cell['layer']}:{cell['permission']}:{cell['action']}",
                    "detail": (
                        f"Undeclared {cell['action']} succeeded (benign probe). "
                        "Catalog treats this as excessive-permission even when benign."
                    ),
                    "classification_note": kind,
                }
            )
            if cell["action"] == "write-outside-root":
                out[-1]["classification"] = "undeclared-action"
                out[-1]["detail"] = (
                    "Write outside the package root succeeded. That path is not "
                    "in the declared permission set."
                )
    return out


def fingerprint(matrix: list[dict]) -> list[tuple]:
    rows = []
    for cell in matrix:
        rows.append(
            (
                cell["layer"],
                cell["permission"],
                cell["action"],
                bool(cell["granted"]),
                cell["observed"],
                cell["enforcement_outcome"],
            )
        )
    return sorted(rows)


def measure() -> dict[str, Any]:
    declared = load_declared()
    product = product_scan(REPO)
    prev = os.environ.get(CRED_ENV)
    os.environ[CRED_ENV] = "1"
    try:
        with tempfile.TemporaryDirectory(prefix="cnf0111-") as tmp:
            sandbox = Path(tmp)
            pkg = sandbox / "package-root"
            pkg.mkdir()
            marker = prepare_credential_marker(pkg)
            product_cells = run_layer("product", declared, sandbox, marker)
            detector_cells = run_layer("detector-control", declared, sandbox, marker)
            product_cells.append(run_outside_root("product", declared, sandbox))
            detector_cells.append(run_outside_root("detector-control", declared, sandbox))
    finally:
        if prev is None:
            os.environ.pop(CRED_ENV, None)
        else:
            os.environ[CRED_ENV] = prev

    empty_p = empty_cells(product_cells)
    empty_d = empty_cells(detector_cells)
    if empty_p or empty_d:
        raise RuntimeError(f"empty cells product={empty_p} detector={empty_d}")

    granted_ok = all(
        c["observed"] == "succeeded"
        for c in product_cells + detector_cells
        if c["granted"] and c["action"] != "write-outside-root"
    )
    detector_absent_blocked = all(
        c["observed"] == "blocked"
        for c in detector_cells
        if (not c["granted"]) or c["action"] == "write-outside-root"
    )
    product_absent_open = all(
        c["observed"] == "succeeded"
        for c in product_cells
        if (not c["granted"]) or c["action"] == "write-outside-root"
    )
    isolates = granted_ok and detector_absent_blocked and product_absent_open

    cred_ok = True
    for cell in product_cells + detector_cells:
        if cell["permission"] != "credential-read":
            continue
        if "value_read=True" in cell["evidence"] or "value_printed=True" in cell["evidence"]:
            cred_ok = False

    findings = findings_from(product_cells)
    if not product["enforcement_module_present"]:
        findings.insert(
            0,
            {
                "classification": "permission-not-enforced",
                "locus": "product-worktree",
                "detail": (
                    "IMP-0059 runtime paths are absent on this worktree; package "
                    "permission declarations have no call-time interceptor."
                ),
            },
        )

    return {
        "declared": declared,
        "product_runtime": product,
        "matrix": product_cells,
        "detector_control": detector_cells,
        "findings": findings,
        "empty_cells": 0,
        "control": {
            "granted_actions_succeeded": granted_ok,
            "detector_absent_blocked": detector_absent_blocked,
            "product_absent_open": product_absent_open,
            "isolates_enforcement": isolates,
        },
        "credential_probe": {
            "mode": "presence-only",
            "value_read": False,
            "value_printed": False,
            "env_name": CRED_ENV,
            "checked_ok": cred_ok,
        },
        "fingerprint_product": fingerprint(product_cells),
        "fingerprint_detector": fingerprint(detector_cells),
    }
