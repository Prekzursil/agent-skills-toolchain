"""claude.ai remote-connector census — closes the CLI-only inventory undercount.

``core/inventory.py`` scans only the CLI-side planes (``mcpServers`` in ``~/.claude.json``
and ``.mcp.json``, ``~/.codex/config.toml``, the funnel master). claude.ai remote
connectors are a DIFFERENT class: remote MCP servers configured in the claude.ai web app,
OAuth-authenticated, and injected into the model's tool list server-side. They surface
only as runtime ``mcp__claude_ai_<Name>__*`` tool namespaces and are NEVER persisted to
any config file (``grep -c mcp__claude_ai_ ~/.claude.json`` = 0). A pure-code census is
therefore STRUCTURALLY BLIND to them and reports the CLI-side count alone (measured 68) as
if it were the whole surface (measured true live ~88 = 68 CLI-side + 20 claude.ai).

Two reconciled sources for the claude.ai plane:

  LIVE (authoritative)      -- a manifest an agent writes from its runtime tool inventory
                               (the distinct ``mcp__claude_ai_*`` namespaces this session).
  EVER (durable, code-only) -- ``~/.claude.json`` ``claudeAiMcpEverConnected``: an
                               ever-connected SUPERSET that also LAGS newly-connected
                               connectors, so it is neither sound nor complete as "live".

The report is 3-tier with a reconciliation delta and keeps the CLI-side count and the
claude.ai-side count in SEPARATE fields, so the two classes are never conflated and the
undercount cannot silently return. When the LIVE manifest is absent the census reports the
EVER count explicitly labeled as an over-count -- never a silent zero. Pure reads only.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import TypedDict, cast

from core.inventory import build_inventory

SCHEMA = "mcp-surface-census/v1"
#: statsig feature gate that enables claude.ai connectors for the account.
GATE_KEY = "tengu_claudeai_mcp_connectors"
#: the one durable on-disk breadcrumb: connectors ever connected (a stale superset).
EVER_KEY = "claudeAiMcpEverConnected"
#: runtime namespace prefix of a live claude.ai connector tool.
NAMESPACE_PREFIX = "mcp__claude_ai_"
_MANIFEST_BASIS = "manifest"
_FALLBACK_BASIS = "ever-fallback(overcount)"


class ConnectorCensus(TypedDict):
    """The claude.ai connector plane, reconciled LIVE vs EVER (JSON-able)."""

    gate_enabled: bool
    count_live: int
    count_ever: int
    live: list[str]
    ever: list[str]
    live_missing_on_disk: list[str]
    ever_not_live: list[str]
    reported_count: int
    reported_basis: str


class SurfaceCensus(TypedDict):
    """True MCP surface = CLI-side servers + claude.ai remote connectors (JSON-able)."""

    schema: str
    cli_side_count: int
    claude_ai_live_count: int
    claude_ai_ever_count: int
    claude_ai_reported_count: int
    claude_ai_reported_basis: str
    claude_ai_gate_enabled: bool
    true_live_total: int
    live_missing_on_disk: list[str]
    ever_not_live_count: int
    connectors: ConnectorCensus


def _load_json(path: Path) -> dict[str, object]:
    try:
        return cast("dict[str, object]", json.loads(path.read_text(encoding="utf-8")))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def normalize_display_name(name: str) -> str:
    """Map an on-disk display name to its runtime namespace form.

    ``"claude.ai ChEMBL (2)"`` -> ``"ChEMBL_2"``; ``"claude.ai Synapse.org"`` ->
    ``"Synapse_org"``; ``"claude.ai EDEN by Basecamp Research"`` ->
    ``"EDEN_by_Basecamp_Research"``. A name without the prefix is returned unchanged.
    """
    stripped = re.sub(r"^claude\.ai\s+", "", name).strip()
    return re.sub(r"[^0-9A-Za-z]+", "_", stripped).strip("_")


def _find_gate(obj: object, key: str = GATE_KEY) -> bool:
    """Locate the statsig feature gate (nested in a cache whose location drifts)."""
    stack: list[object] = [obj]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            typed = cast("dict[str, object]", current)
            if key in typed:
                return bool(typed[key])
            stack.extend(typed.values())
        elif isinstance(current, list):
            stack.extend(cast("list[object]", current))
    return False


def _manifest_connectors(live_manifest: Path | None) -> set[str]:
    """Read the authoritative LIVE namespace set from an agent-written manifest."""
    if live_manifest is None:
        return set()
    raw = _load_json(live_manifest).get("connectors")
    if not isinstance(raw, list):
        return set()
    return {item for item in cast("list[object]", raw) if isinstance(item, str)}


def _ever_from_data(data: dict[str, object]) -> set[str]:
    """Read the durable EVER superset from a loaded ``~/.claude.json`` dict."""
    raw = data.get(EVER_KEY)
    if not isinstance(raw, list):
        return set()
    return {
        normalize_display_name(item)
        for item in cast("list[object]", raw)
        if isinstance(item, str)
    }


def claude_ai_connectors(
    claude_json: Path, live_manifest: Path | None
) -> ConnectorCensus:
    """Reconcile the claude.ai connector plane from its LIVE and EVER sources.

    LIVE (manifest) is authoritative; EVER (on-disk) is a durable but stale superset.
    The reported count uses LIVE when the manifest is present, else falls back to EVER
    explicitly labeled as an over-count -- never a silent 0.
    """
    claude_data = _load_json(claude_json)
    live = _manifest_connectors(live_manifest)
    ever = _ever_from_data(claude_data)
    have_live = bool(live)
    if have_live:
        reported_count = len(live)
        reported_basis = _MANIFEST_BASIS
    else:
        reported_count = len(ever)
        reported_basis = _FALLBACK_BASIS
    return {
        "gate_enabled": _find_gate(claude_data),
        "count_live": len(live),
        "count_ever": len(ever),
        "live": sorted(live),
        "ever": sorted(ever),
        "live_missing_on_disk": sorted(live - ever),
        "ever_not_live": sorted(ever - live),
        "reported_count": reported_count,
        "reported_basis": reported_basis,
    }


def default_manifest_path(home: Path) -> Path:
    """The stable, undated per-home manifest the refresh loop overwrites."""
    return home / ".claude" / "mcp-manager" / "claude_ai_connectors.json"


def surface_census(
    home: Path,
    *,
    project_path: str | None = None,
    live_manifest: Path | None = None,
) -> SurfaceCensus:
    """Full MCP-surface census: the CLI-side inventory PLUS the claude.ai plane.

    ``cli_side_count`` is the existing cross-plane CLI census (``mcpServers`` etc.);
    the ``claude_ai_*`` fields are the previously-invisible remote-connector plane.
    ``true_live_total`` is their sum, with each class kept separate so the CLI-only
    undercount (measured 68 reported vs ~88 real) cannot silently recur.
    """
    cli = build_inventory(home, project_path)
    cli_count = cli["server_count"]
    if live_manifest is None:
        manifest = default_manifest_path(home)
    else:
        manifest = live_manifest
    conn = claude_ai_connectors(home / ".claude.json", manifest)
    return {
        "schema": SCHEMA,
        "cli_side_count": cli_count,
        "claude_ai_live_count": conn["count_live"],
        "claude_ai_ever_count": conn["count_ever"],
        "claude_ai_reported_count": conn["reported_count"],
        "claude_ai_reported_basis": conn["reported_basis"],
        "claude_ai_gate_enabled": conn["gate_enabled"],
        "true_live_total": cli_count + conn["reported_count"],
        "live_missing_on_disk": conn["live_missing_on_disk"],
        "ever_not_live_count": len(conn["ever_not_live"]),
        "connectors": conn,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="MCP surface census: CLI-side servers + claude.ai connectors."
    )
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--project", default=None)
    parser.add_argument("--manifest", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    home = cast("Path", args.home)
    manifest = cast("Path | None", args.manifest)
    project_arg = cast("str | None", args.project)
    if project_arg is None:
        project = str(home).replace("\\", "/")
    else:
        project = project_arg
    report = surface_census(home, project_path=project, live_manifest=manifest)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI smoke
    raise SystemExit(main())
