"""Support-contract compatibility matrix (TST-0078)."""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CONTRACT_PATH = HERE / "support_contract.json"

CONTRACT_SCHEMA = {
    "type": "object",
    "required": ["axes", "declared"],
    "properties": {
        "axes": {"type": "object"},
        "declared": {"type": "array"},
    },
}


def cell_id(os_name: str, client: str, client_version: str) -> str:
    return f"{os_name}|{client}|{client_version}"


def cartesian(axes: dict[str, list[str]]) -> list[dict[str, str]]:
    cells = [{}]
    for axis, values in axes.items():
        nxt = []
        for cell in cells:
            for val in values:
                row = dict(cell)
                row[axis] = val
                nxt.append(row)
        cells = nxt
    return cells


def build_contract() -> dict[str, Any]:
    axes = {
        "os": ["linux", "windows", "macos"],
        "client": ["claude-code", "cursor", "codex"],
        "client_version": ["1.0.0", "2.0.0"],
    }
    declared = []
    for cell in cartesian(axes):
        key = (cell["os"], cell["client"], cell["client_version"])
        if key == ("linux", "claude-code", "1.0.0"):
            declared.append({**cell, "status": "UNSUPPORTED"})
        elif cell["client"] == "codex" and cell["client_version"] == "2.0.0":
            continue  # undeclared -> UNTESTED
        elif cell["os"] == "macos" and cell["client"] == "cursor":
            continue
        else:
            declared.append({**cell, "status": "SUPPORTED"})
    return {"axes": axes, "declared": declared, "artifact": "compatibility"}


def write_contract(path: Path | None = None) -> dict[str, Any]:
    path = Path(path or CONTRACT_PATH)
    doc = build_contract()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


def load_contract(path: Path | None = None) -> dict[str, Any]:
    path = Path(path or CONTRACT_PATH)
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return write_contract(path)


def declared_map(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out = {}
    for row in contract.get("declared") or []:
        out[cell_id(row["os"], row["client"], row["client_version"])] = row
    return out


def completeness_ok(cells: list[dict[str, Any]], axes: dict[str, list[str]]) -> dict[str, Any]:
    expected = {cell_id(c["os"], c["client"], c["client_version"]) for c in cartesian(axes)}
    got = {cell_id(c["os"], c["client"], c["client_version"]) for c in cells}
    missing = sorted(expected - got)
    extra = sorted(got - expected)
    return {"ok": not missing and not extra, "missing": missing, "extra": extra}


@dataclass
class NegotiateResult:
    action: str
    reason_code: str | None = None
    status: str | None = None


def negotiate(cell: dict[str, Any], contract: dict[str, Any] | None = None) -> NegotiateResult:
    ver = str(cell.get("client_version") or "")
    if not ver or not all(p.isdigit() for p in ver.split(".") if p):
        return NegotiateResult(action="refuse", reason_code="unparsable-version")
    contract = contract or load_contract()
    row = declared_map(contract).get(
        cell_id(cell["os"], cell["client"], cell["client_version"])
    )
    if row is None:
        return NegotiateResult(action="skip", reason_code="undeclared", status="UNTESTED")
    if row.get("status") == "UNSUPPORTED":
        return NegotiateResult(action="refuse", reason_code="unsupported", status="UNSUPPORTED")
    return NegotiateResult(action="allow", status="SUPPORTED")


def attempt_install(
    source: Path,
    dest: Path,
    cell: dict[str, Any] | None = None,
    contract: dict[str, Any] | None = None,
    supported=None,
) -> dict[str, Any]:
    if cell is None and supported is None:
        # legacy copy
        src = Path(source)
        dst = Path(dest)
        if src.is_dir():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            files = [p.relative_to(dst).as_posix() for p in dst.rglob("*") if p.is_file()]
            return {
                "installed": True,
                "outcome": "PROCEEDED",
                "plugin_present": True,
                "files_written": len(files),
            }
    decision = negotiate(cell or {}, contract)
    if decision.action != "allow":
        return {
            "installed": False,
            "outcome": "REFUSED",
            "plugin_present": False,
            "files_written": 0,
            "reason_code": decision.reason_code,
        }
    src = Path(source)
    dst = Path(dest)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    files = [p.relative_to(dst).as_posix() for p in dst.rglob("*") if p.is_file()]
    return {
        "installed": True,
        "outcome": "PROCEEDED",
        "plugin_present": (dst / "plugin.json").is_file(),
        "files_written": len(files),
        "reason_code": None,
    }


def run_matrix(published: Path, cells_dir: Path, contract: dict[str, Any]) -> dict[str, Any]:
    axes = contract["axes"]
    lookup = declared_map(contract)
    cells = []
    counts = {
        "supported_declared": 0,
        "supported_proceeded": 0,
        "unsupported_declared": 0,
        "unsupported_refused": 0,
        "untested": 0,
        "mismatched": 0,
        "blank": 0,
    }
    cells_dir.mkdir(parents=True, exist_ok=True)
    for axis_cell in cartesian(axes):
        key = cell_id(axis_cell["os"], axis_cell["client"], axis_cell["client_version"])
        declared = lookup.get(key)
        dest = cells_dir / key.replace("|", "_")
        if declared is None:
            row = {
                **axis_cell,
                "declared": "UNTESTED",
                "outcome": "UNTESTED",
                "installed": False,
                "plugin_present": False,
                "files_written": 0,
                "attempted": False,
                "match": True,
            }
            counts["untested"] += 1
        elif declared.get("status") == "UNSUPPORTED":
            inst = attempt_install(published, dest, axis_cell, contract)
            match = inst["outcome"] == "REFUSED" and not inst["installed"]
            row = {
                **axis_cell,
                "declared": "UNSUPPORTED",
                "outcome": inst["outcome"],
                "installed": inst["installed"],
                "plugin_present": inst["plugin_present"],
                "files_written": inst["files_written"],
                "attempted": True,
                "match": match,
            }
            counts["unsupported_declared"] += 1
            if match:
                counts["unsupported_refused"] += 1
            else:
                counts["mismatched"] += 1
        else:
            inst = attempt_install(published, dest, axis_cell, contract)
            match = (
                inst["outcome"] == "PROCEEDED"
                and inst["installed"]
                and inst["plugin_present"]
                and inst["files_written"] > 0
            )
            row = {
                **axis_cell,
                "declared": "SUPPORTED",
                "outcome": inst["outcome"],
                "installed": inst["installed"],
                "plugin_present": inst["plugin_present"],
                "files_written": inst["files_written"],
                "attempted": True,
                "match": match,
            }
            counts["supported_declared"] += 1
            if match:
                counts["supported_proceeded"] += 1
            else:
                counts["mismatched"] += 1
        cells.append(row)
    return {"cells": cells, "counts": counts}
