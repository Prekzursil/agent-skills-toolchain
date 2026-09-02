"""Index + install fixtures and the catalog both-states control.

State A: capability remains in the index and on disk; router does not select it.
State B: capability is removed from the index; install file stays.
The three-bit signal must emit different codes. A collapsed unavailable bit
must be identical in both states (the silent-equivalence we reject).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from avail import classify, collapsed_unavailable

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
ALPHA = "skill.alpha"
ALPHA_REL = "command-center/p2-wave/probes/ARC-0026/fixtures/install/skills/skill.alpha.json"

INDEX = {
    "schema_version": 1,
    "capabilities": [
        {
            "id": "skill.alpha",
            "kind": "skill",
            "install": "install/skills/skill.alpha.json",
        },
        {
            "id": "skill.beta",
            "kind": "skill",
            "install": "install/skills/skill.beta.json",
        },
        {
            "id": "mcp.stdio.echo",
            "kind": "mcp",
            "install": "install/mcp/mcp.stdio.echo.json",
        },
    ],
}

MCP = {
    "mcpServers": {
        "echo": {"command": "python3", "args": ["-c", "print('echo')"]},
        "files": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
        },
        "git": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-git"],
        },
        "remote-docs": {"url": "https://example.invalid/mcp"},
    }
}


def _write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def ensure_fixtures() -> Path:
    _write(FIX / "index.json", INDEX)
    _write(FIX / "mcp.json", MCP)
    _write(
        FIX / "install" / "skills" / "skill.alpha.json",
        {
            "id": "skill.alpha",
            "kind": "skill",
            "name": "alpha",
            "description": "Installed skill used by the both-states control.",
        },
    )
    _write(
        FIX / "install" / "skills" / "skill.beta.json",
        {"id": "skill.beta", "kind": "skill", "name": "beta"},
    )
    _write(
        FIX / "install" / "mcp" / "mcp.stdio.echo.json",
        {
            "id": "mcp.stdio.echo",
            "kind": "mcp",
            "transport": "stdio",
            "command": "python3",
        },
    )
    residual = FIX / "state" / "skill.alpha.session.json"
    _write(residual, {"capability_id": ALPHA, "leftover": True, "turn": 3})
    return FIX


def _ids(index: dict[str, Any]) -> set[str]:
    return {str(row["id"]) for row in index.get("capabilities") or []}


def installed(cap_id: str) -> bool:
    mapping = {
        "skill.alpha": FIX / "install" / "skills" / "skill.alpha.json",
        "skill.beta": FIX / "install" / "skills" / "skill.beta.json",
        "mcp.stdio.echo": FIX / "install" / "mcp" / "mcp.stdio.echo.json",
        "skill.ghost": FIX / "install" / "skills" / "skill.ghost.json",
    }
    path = mapping.get(cap_id)
    return bool(path and path.is_file() and path.stat().st_size > 0)


def drop_from_index(index: dict[str, Any], cap_id: str) -> dict[str, Any]:
    rows = [r for r in index["capabilities"] if r.get("id") != cap_id]
    return {"schema_version": 1, "capabilities": rows}


def both_states() -> dict[str, Any]:
    """Catalog test: remove from index, leave installed; codes must differ."""
    ensure_fixtures()
    full = json.loads((FIX / "index.json").read_text(encoding="utf-8"))
    in_index = ALPHA in _ids(full)
    on_disk = installed(ALPHA)
    # State A: indexed, installed, not selected.
    a = classify(
        indexed=in_index,
        installed=on_disk,
        selected=False,
        activation="never",
    )
    a_coll = collapsed_unavailable(selected=False)
    # State B: index row deleted, install file untouched.
    reduced = drop_from_index(full, ALPHA)
    b = classify(
        indexed=ALPHA in _ids(reduced),
        installed=installed(ALPHA),
        selected=False,
        activation="never",
    )
    b_coll = collapsed_unavailable(selected=False)
    missing = classify(
        indexed=False,
        installed=False,
        selected=False,
        activation="never",
    )
    stale = classify(
        indexed=True,
        installed=False,
        selected=False,
        activation="never",
    )
    midtask = classify(
        indexed=True,
        installed=True,
        selected=True,
        activation="failed",
    )
    residual = classify(
        indexed=True,
        installed=True,
        selected=False,
        activation="deactivated",
        residual_state=True,
    )
    ok = (
        in_index
        and on_disk
        and a["code"] == "NOT_SELECTED"
        and b["code"] == "INDEX_MISS_INSTALLED"
        and a["code"] != b["code"]
        and a_coll == b_coll == "UNAVAILABLE"
        and missing["code"] == "NOT_INSTALLED"
        and missing["code"] != a["code"]
        and missing["code"] != b["code"]
        and stale["code"] == "STALE_INDEX"
        and midtask["code"] == "ACTIVATION_FAILED"
        and residual["code"] == "DEACTIVATED_RESIDUAL"
        and installed(ALPHA) is True
    )
    return {
        "pass": ok,
        "capability_id": ALPHA,
        "silent_loss_file": ALPHA_REL,
        "state_a_indexed_installed_not_selected": a,
        "state_b_index_removed_still_installed": b,
        "not_selected_code": a["code"],
        "index_miss_installed_code": b["code"],
        "codes_differ": a["code"] != b["code"],
        "collapsed_state_a": a_coll,
        "collapsed_state_b": b_coll,
        "collapsed_same_in_both_states": a_coll == b_coll,
        "truly_not_installed": missing,
        "stale_index": stale,
        "activation_failed_midtask": midtask,
        "deactivated_residual": residual,
        "install_file_survived_index_edit": installed(ALPHA),
    }
