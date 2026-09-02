#!/usr/bin/env python3
"""ARC-0095 compatibility-matrix generator and untested-cell rules.

SUPPORTED requires a recorded in-client run that names the observed client
VERSION. Adjacent-cell guesses are INFERRED, never SUPPORTED. Absence is
NOT-CHECKED (display alias UNTESTED): never a pass, never blank.
"""
from __future__ import annotations

from copy import deepcopy
from itertools import product
from typing import Any

STATUSES = (
    "SUPPORTED",
    "FAILED",
    "INFERRED",
    "NOT-CHECKED",
    "NOT-APPLICABLE",
    "UNSUPPORTED",
)
STATUSES = STATUSES

PASS_LIKE = frozenset(
    {"SUPPORTED", "PASS", "OK", "GREEN", "RUN", "TRUE", "YES", "CHECKED"}
)
PASS_LIKE = PASS_LIKE
FORBIDDEN_UNTESTED_TOKENS = PASS_LIKE | frozenset({""})

RENDER = {
    "SUPPORTED": {
        "token": "SUPPORTED",
        "display": "SUPPORTED",
        "glyph": "\u25cf",
        "css_class": "matrix-cell-supported",
        "color_role": "pass",
        "is_pass": True,
        "machine_status": "SUPPORTED",
    },
    "FAILED": {
        "token": "FAILED",
        "display": "FAILED",
        "glyph": "\u2716",
        "css_class": "matrix-cell-failed",
        "color_role": "fail",
        "is_pass": False,
        "machine_status": "FAILED",
    },
    "INFERRED": {
        "token": "INFERRED",
        "display": "INFERRED",
        "glyph": "\u25c7",
        "css_class": "matrix-cell-inferred",
        "color_role": "inferred",
        "is_pass": False,
        "machine_status": "INFERRED",
    },
    "NOT-CHECKED": {
        "token": "NOT-CHECKED",
        "display": "UNTESTED",
        "glyph": "\u25cb",
        "css_class": "matrix-cell-not-checked",
        "color_role": "unknown",
        "is_pass": False,
        "machine_status": "NOT-CHECKED",
        "aliases": ["UNTESTED", "NEVER-RUN"],
    },
    "NOT-APPLICABLE": {
        "token": "NOT-APPLICABLE",
        "display": "NOT-APPLICABLE",
        "glyph": "\u2013",
        "css_class": "matrix-cell-na",
        "color_role": "na",
        "is_pass": False,
        "machine_status": "NOT-APPLICABLE",
    },
    "UNSUPPORTED": {
        "token": "UNSUPPORTED",
        "display": "UNSUPPORTED",
        "glyph": "\u25a0",
        "css_class": "matrix-cell-unsupported",
        "color_role": "out",
        "is_pass": False,
        "machine_status": "UNSUPPORTED",
    },
}

AXIS_ORDER = (
    "operating_system",
    "client",
    "client_version",
    "shell",
    "package_version",
)
AXIS_ORDER = AXIS_ORDER

# UNPINNED = no published pin. That slot cannot become SUPPORTED.
DEFAULT_AXES = {
    "operating_system": ["linux", "windows", "macos"],
    "client": ["claude-code", "codex-cli", "antigravity", "mcp-generic"],
    "client_version": ["UNPINNED"],
    "shell": ["bash", "powershell"],
    "package_version": ["UNPINNED"],
}

TIER_PLAN = {
    ("linux", "claude-code"): "T1",
    ("linux", "codex-cli"): "T1",
    ("linux", "antigravity"): "T3",
    ("linux", "mcp-generic"): "T3",
    ("windows", "claude-code"): "T2",
    ("windows", "codex-cli"): "T2",
    ("windows", "antigravity"): "T3",
    ("windows", "mcp-generic"): "T3",
    ("macos", "claude-code"): "T2",
    ("macos", "codex-cli"): "T2",
    ("macos", "antigravity"): "T3",
    ("macos", "mcp-generic"): "T3",
}
TIER_PLAN = TIER_PLAN

UNPINNED = frozenset({"UNPINNED", "UNDECLARED", "*", "", None})

RECEIPT_REQUIRED = (
    "operating_system",
    "client",
    "client_version",
    "shell",
    "package_version",
    "run_id",
    "observed_at",
    "result",
    "observation_kind",
    "observed_client_version",
)


def cell_id(coord: dict[str, str]) -> str:
    return "|".join(str(coord[k]) for k in AXIS_ORDER)


def parse_cell_id(cid: str) -> dict[str, str]:
    parts = cid.split("|")
    if len(parts) != 5:
        raise ValueError(f"bad cell id {cid!r}")
    return dict(zip(AXIS_ORDER, parts))


def support_tier(os_name: str, client: str) -> str:
    return TIER_PLAN.get((os_name, client), "T3")


def render_for(status: str) -> dict[str, Any]:
    if status not in RENDER:
        raise ValueError(f"unknown status {status!r}")
    return deepcopy(RENDER[status])


def declared_axes(override: dict | None = None) -> dict[str, list[str]]:
    axes = {k: list(v) for k, v in DEFAULT_AXES.items()}
    if override:
        for key in AXIS_ORDER:
            if key in override:
                axes[key] = list(override[key])
    return axes


def cartesian(axes: dict[str, list[str]]) -> list[dict[str, str]]:
    keys = list(AXIS_ORDER)
    out = []
    for combo in product(*[axes[k] for k in keys]):
        out.append(dict(zip(keys, combo)))
    return out


def not_applicable_reason(coord: dict[str, str]) -> str | None:
    if coord.get("shell") == "cmd" and coord.get("operating_system") != "windows":
        return "cmd exists only on Windows"
    return None


def empty_cell(coord: dict[str, str]) -> dict[str, Any]:
    status = "NOT-CHECKED"
    na = not_applicable_reason(coord)
    if na:
        status = "NOT-APPLICABLE"
    return {
        "id": cell_id(coord),
        "axes": dict(coord),
        "support_tier": support_tier(coord["operating_system"], coord["client"]),
        "status": status,
        "render": render_for(status),
        "evidence": [],
        "inference": None,
        "reason": na or "no recorded in-client run names this cell",
        "is_pass": False,
    }


def validate_receipt(rec: Any) -> tuple[bool, str]:
    if not isinstance(rec, dict):
        return False, "receipt-not-object"
    for key in RECEIPT_REQUIRED:
        if key not in rec or rec[key] in (None, ""):
            return False, f"missing:{key}"
    if rec["observation_kind"] != "in-client":
        return False, "observation_kind-not-in-client"
    if rec["client_version"] in UNPINNED:
        return False, "client_version-unpinned"
    if rec["package_version"] in UNPINNED:
        return False, "package_version-unpinned"
    if rec["observed_client_version"] != rec["client_version"]:
        return False, "intended-version-ne-observed-version"
    if rec["result"] not in {"pass", "fail"}:
        return False, "result-not-pass-or-fail"
    for key in AXIS_ORDER:
        if not isinstance(rec[key], str):
            return False, f"axis-not-string:{key}"
    return True, "ok"


def load_receipts(blobs: list[Any]) -> tuple[list[dict], list[dict]]:
    accepted: list[dict] = []
    rejected: list[dict] = []
    for rec in blobs:
        ok, reason = validate_receipt(rec)
        if ok:
            accepted.append(rec)
        else:
            rejected.append({"receipt": rec, "reason": reason})
    return accepted, rejected


def apply_receipts(cells: dict[str, dict], receipts: list[dict]) -> None:
    for rec in receipts:
        coord = {k: rec[k] for k in AXIS_ORDER}
        cid = cell_id(coord)
        if cid not in cells:
            cells[cid] = empty_cell(coord)
        cell = cells[cid]
        if cell["status"] == "NOT-APPLICABLE":
            cell["reason"] = "receipt ignored: combination is NOT-APPLICABLE"
            continue
        cell["evidence"].append(
            {
                "run_id": rec["run_id"],
                "observed_at": rec["observed_at"],
                "observed_client_version": rec["observed_client_version"],
                "observation_kind": rec["observation_kind"],
                "result": rec["result"],
            }
        )
        if rec["result"] == "fail":
            cell["status"] = "FAILED"
            cell["reason"] = "in-client run recorded fail"
        else:
            cell["status"] = "SUPPORTED"
            cell["reason"] = "in-client run recorded pass with observed version"
        cell["render"] = render_for(cell["status"])
        cell["is_pass"] = cell["status"] == "SUPPORTED"
        cell["inference"] = None


def _adjacent_os_ids(cid: str, os_values: list[str]) -> list[str]:
    coord = parse_cell_id(cid)
    out = []
    for os_name in os_values:
        if os_name == coord["operating_system"]:
            continue
        neigh = dict(coord)
        neigh["operating_system"] = os_name
        out.append(cell_id(neigh))
    return out


def infer_from_adjacent(cells: dict[str, dict], os_values: list[str]) -> None:
    """Label empty neighbours of a SUPPORTED cell INFERRED. Never SUPPORTED."""
    supported_ids = [cid for cid, c in cells.items() if c["status"] == "SUPPORTED"]
    for src in supported_ids:
        for nid in _adjacent_os_ids(src, os_values):
            if nid not in cells:
                cells[nid] = empty_cell(parse_cell_id(nid))
            cell = cells[nid]
            if cell["status"] in {
                "SUPPORTED",
                "FAILED",
                "NOT-APPLICABLE",
                "UNSUPPORTED",
                "INFERRED",
            }:
                continue
            cell["status"] = "INFERRED"
            cell["inference"] = {
                "from_cell_id": src,
                "rule": "adjacent-operating_system",
                "note": "Guess from a neighbour. Not a recorded run. Not SUPPORTED.",
            }
            cell["reason"] = f"inferred from {src}; labelled INFERRED never SUPPORTED"
            cell["render"] = render_for("INFERRED")
            cell["is_pass"] = False


def status_counts(cells: dict[str, dict]) -> dict[str, int]:
    tallies = {s: 0 for s in STATUSES}
    for c in cells.values():
        st = c["status"]
        tallies[st] = tallies.get(st, 0) + 1
    return tallies


def platforms_with_evidence(cells: dict[str, dict]) -> list[str]:
    found = set()
    for c in cells.values():
        if c["status"] in {"SUPPORTED", "FAILED"} and c.get("evidence"):
            found.add(c["axes"]["operating_system"])
    return sorted(found)


def partial_estate_defect(
    cells: dict[str, dict],
    declared_os: list[str],
    program_ran_on: list[str],
) -> dict[str, Any] | None:
    n_untested = status_counts(cells)["NOT-CHECKED"]
    ran = sorted(set(program_ran_on))
    evidenced = platforms_with_evidence(cells)
    if n_untested == 0 and (len(ran) <= 1 or len(evidenced) <= 1):
        return {
            "id": "all-green-on-partial-estate",
            "severity": "P1",
            "status": "open",
            "summary": (
                "Zero NOT-CHECKED cells while the program has run on "
                f"{ran or evidenced or ['unknown']} but declared OS "
                f"{list(declared_os)}. A full-green matrix on a partial estate "
                "is itself a defect."
            ),
            "untested_cell_count": n_untested,
            "program_ran_on": ran,
            "platforms_with_evidence": evidenced,
        }
    return None


def assert_honest(cells: dict[str, dict]) -> list[str]:
    errors: list[str] = []
    css = {RENDER[s]["css_class"] for s in STATUSES}
    if len(css) != len(STATUSES):
        errors.append("render-css-collision")
    glyphs = {RENDER[s]["glyph"] for s in STATUSES}
    if len(glyphs) != len(STATUSES):
        errors.append("render-glyph-collision")
    for c in cells.values():
        st = c["status"]
        cid = c["id"]
        if st not in STATUSES:
            errors.append(f"illegal-status:{cid}:{st}")
            continue
        if st == "INFERRED" and (c.get("is_pass") or c["render"].get("is_pass")):
            errors.append(f"inferred-reads-as-pass:{cid}")
        if st == "NOT-CHECKED":
            token = c["render"]["token"]
            if token in FORBIDDEN_UNTESTED_TOKENS:
                errors.append(f"untested-reads-as-pass:{cid}:{token}")
            if c.get("is_pass") or c["render"].get("is_pass"):
                errors.append(f"untested-is_pass:{cid}")
            if not str(c.get("reason") or "").strip():
                errors.append(f"untested-blank-reason:{cid}")
        if c["render"]["machine_status"] != st:
            errors.append(f"render-status-mismatch:{cid}")
        if st == "SUPPORTED" and not c.get("evidence"):
            errors.append(f"supported-without-evidence:{cid}")
        if st == "INFERRED" and c["render"]["css_class"] == RENDER["SUPPORTED"]["css_class"]:
            errors.append(f"inferred-css-collision:{cid}")
        if st == "INFERRED" and c["render"]["glyph"] == RENDER["SUPPORTED"]["glyph"]:
            errors.append(f"inferred-glyph-collision:{cid}")
    return errors


def generate(
    receipts: list[dict] | None = None,
    *,
    axes: dict[str, list[str]] | None = None,
    infer: bool = False,
    program_ran_on: list[str] | None = None,
    expand_versions_from_receipts: bool = True,
) -> dict[str, Any]:
    """Build a matrix. Missing evidence -> NOT-CHECKED. infer labels INFERRED."""
    axes_u = declared_axes(axes)
    accepted, rejected = load_receipts(list(receipts or []))
    if expand_versions_from_receipts:
        for rec in accepted:
            if rec["client_version"] not in axes_u["client_version"]:
                axes_u["client_version"].append(rec["client_version"])
            if rec["package_version"] not in axes_u["package_version"]:
                axes_u["package_version"].append(rec["package_version"])
    coords = cartesian(axes_u)
    cells = {cell_id(c): empty_cell(c) for c in coords}
    apply_receipts(cells, accepted)
    if infer:
        infer_from_adjacent(cells, axes_u["operating_system"])
    honesty = assert_honest(cells)
    if honesty:
        raise RuntimeError("matrix honesty failed: " + "; ".join(honesty))
    defect = partial_estate_defect(
        cells, axes_u["operating_system"], program_ran_on or []
    )
    declared_ids = {cell_id(c) for c in coords}
    ordered = [cells[cell_id(c)] for c in coords]
    extra = [c for cid, c in cells.items() if cid not in declared_ids]
    all_cells = ordered + extra
    counts = status_counts(cells)
    untested = counts["NOT-CHECKED"]
    return {
        "axes": axes_u,
        "axis_order": list(AXIS_ORDER),
        "infer": infer,
        "cells": all_cells,
        "cell_count": len(all_cells),
        "status_counts": counts,
        "status_counts": counts,
        "untested_cell_count": untested,
        "untested_cell_count": untested,
        "supported_cell_count": counts["SUPPORTED"],
        "inferred_cell_count": counts["INFERRED"],
        "failed_cell_count": counts["FAILED"],
        "platforms_with_evidence": platforms_with_evidence(cells),
        "program_ran_on": list(program_ran_on or []),
        "receipts_accepted": len(accepted),
        "receipts_rejected": rejected,
        "blank_cells": 0,
        "defects": [defect] if defect else [],
        "honesty": honesty,
    }


def ascii_row(cell: dict[str, Any]) -> str:
    r = cell["render"]
    ax = cell["axes"]
    return (
        f"{r['glyph']} {r['token']:14} "
        f"{ax['operating_system']:7} {ax['client']:13} "
        f"{ax['client_version']:12} {ax['shell']:11} {ax['package_version']}"
    )


def ascii_table(matrix: dict[str, Any]) -> str:
    return "\n".join(ascii_row(c) for c in matrix["cells"])


def cell_by_id(matrix: dict[str, Any], cid: str) -> dict[str, Any] | None:
    for c in matrix["cells"]:
        if c["id"] == cid:
            return c
    return None


def make_receipt(
    *,
    operating_system: str,
    client: str,
    client_version: str,
    shell: str,
    package_version: str,
    run_id: str,
    result: str = "pass",
    observation_kind: str = "in-client",
    observed_client_version: str | None = None,
    observed_at: str = "2026-08-24T00:00:00Z",
) -> dict[str, Any]:
    return {
        "operating_system": operating_system,
        "client": client,
        "client_version": client_version,
        "shell": shell,
        "package_version": package_version,
        "run_id": run_id,
        "observed_at": observed_at,
        "result": result,
        "observation_kind": observation_kind,
        "observed_client_version": (
            client_version if observed_client_version is None else observed_client_version
        ),
    }


ascii_table = ascii_table
