"""Live catalog counts for default-permissive dispatch vs owner gates."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"


def _is_write(perm: str) -> bool:
    p = perm.strip()
    return p == "Write" or p.startswith("Write(") or p == "Edit" or p.startswith("Edit(")


def _is_shell(perm: str) -> bool:
    p = perm.strip()
    return (
        p == "Bash"
        or p.startswith("Bash")
        or p == "PowerShell"
        or p.startswith("PowerShell")
        or p == "Shell"
        or p.startswith("Shell")
    )


def _is_read_only(perm: str) -> bool:
    p = perm.strip()
    return p in {"Read", "Grep", "Glob"} or p.startswith("Read(") or p.startswith("Grep(") or p.startswith("Glob(")


def measure(repo: Path) -> dict[str, Any]:
    path = repo / CATALOG_REL
    data = json.loads(path.read_text(encoding="utf-8"))
    units = [u for u in (data.get("work_units") or []) if isinstance(u, dict)]
    n = len(units)
    owner_gated = 0
    write_n = 0
    shell_n = 0
    write_and_shell = 0
    write_no_owner = 0
    read_only_only = 0
    for u in units:
        perms = [str(p) for p in (u.get("tool_permissions") or [])]
        gated = u.get("owner_approval_required") is True
        if gated:
            owner_gated += 1
        has_w = any(_is_write(p) for p in perms)
        has_s = any(_is_shell(p) for p in perms)
        if has_w:
            write_n += 1
        if has_s:
            shell_n += 1
        if has_w and has_s:
            write_and_shell += 1
        if has_w and not gated:
            write_no_owner += 1
        if perms and all(_is_read_only(p) for p in perms):
            read_only_only += 1
    # Second derivation (set lengths) for the Codex-role recount.
    write_no_owner_ids = [
        str(u.get("id"))
        for u in units
        if any(_is_write(str(p)) for p in (u.get("tool_permissions") or []))
        and u.get("owner_approval_required") is not True
    ]
    gated_ids = [str(u.get("id")) for u in units if u.get("owner_approval_required") is True]
    return {
        "computed_not_asserted": True,
        "catalog_path": CATALOG_REL,
        "unit_count": n,
        "owner_gated": owner_gated,
        "owner_gated_recount": len(gated_ids),
        "write_units": write_n,
        "shell_units": shell_n,
        "write_and_shell": write_and_shell,
        "write_without_owner_gate": write_no_owner,
        "write_without_owner_gate_recount": len(write_no_owner_ids),
        "read_only_permission_only": read_only_only,
        "auto_dispatchable": n - owner_gated,
    }
