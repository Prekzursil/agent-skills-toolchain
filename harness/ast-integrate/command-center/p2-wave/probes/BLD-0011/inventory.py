"""Live + harvest declaration census for BLD-0011."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

SKIP_DIR = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    ".tox",
    "dist",
    "build",
    ".eggs",
}

HARVEST_AUD0029 = REPO / "command-center/p2-wave/probes/AUD-0029/_validate_out.json"
HARVEST_AUD0041 = (
    REPO / "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json"
)

PY_SPEC_RE = re.compile(
    r"(?im)^(?:requires-python|python_requires)\s*=\s*[\"']([^\"']+)[\"']"
)
SETUP_PY_RE = re.compile(r"python_requires\s*=\s*[\"']([^\"']+)[\"']")
CI_PY_RE = re.compile(r"python-version=([0-9.]+)")
CI_NODE_RE = re.compile(r"node-version=([0-9.]+)")
VER_RE = re.compile(r"(\d+\.\d+(?:\.\d+)?)")


def rel(path: Path) -> str:
    try:
        return path.relative_to(REPO).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _iter_named_files(filenames: set[str]) -> list[Path]:
    """Walk the worktree, pruning heavy/irrelevant trees.

    Named probes re-run this census live under a 180s measure cap, so
    ``Path.rglob('*')`` (which still visits skip-dirs) is not viable.
    """
    found: list[Path] = []
    for root, dirs, files in os.walk(REPO, followlinks=False):
        posix = root.replace("\\", "/")
        if "/p2-wave/probes" in posix or posix.endswith("/p2-wave/probes"):
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if d not in SKIP_DIR]
        for name in files:
            if name in filenames:
                found.append(Path(root) / name)
    found.sort()
    return found


def min_from_spec(spec: str) -> str | None:
    match = VER_RE.search(spec)
    return match.group(1) if match else None


def live_python_requires() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    names = {"pyproject.toml", "setup.cfg", "setup.py"}
    for path in _iter_named_files(names):
        text = path.read_text(encoding="utf-8", errors="replace")
        spec = None
        if path.name in {"pyproject.toml", "setup.cfg"}:
            found = PY_SPEC_RE.search(text)
            spec = found.group(1) if found else None
        else:
            found = SETUP_PY_RE.search(text)
            spec = found.group(1) if found else None
        if spec:
            rows.append({"path": rel(path), "spec": spec, "source": "LIVE"})
    rows.sort(key=lambda r: r["path"])
    return rows


def live_engines_node() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in _iter_named_files({"package.json"}):
        doc = load_json(path)
        if not isinstance(doc, dict):
            continue
        engines = doc.get("engines")
        if isinstance(engines, dict) and engines.get("node"):
            rows.append(
                {
                    "path": rel(path),
                    "spec": str(engines["node"]),
                    "source": "LIVE",
                }
            )
    rows.sort(key=lambda r: r["path"])
    return rows


def live_plugin_interpreters() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in _iter_named_files({"plugin.json"}):
        doc = load_json(path)
        if not isinstance(doc, dict):
            continue
        interps = doc.get("interpreters") or doc.get("interpreter")
        if interps:
            rows.append(
                {
                    "path": rel(path),
                    "interpreters": interps,
                    "source": "LIVE",
                }
            )
    return rows


def harvest_aud0029() -> dict[str, Any]:
    doc = load_json(HARVEST_AUD0029)
    if not isinstance(doc, dict):
        return {"present": False, "path": rel(HARVEST_AUD0029)}
    local = doc.get("local_remeasure") or {}
    scope = local.get("scope") or {}
    plugin = local.get("plugin") or {}
    py = scope.get("requires_python") or scope.get("python_requires") or []
    node = scope.get("engines_node") or []
    zip_json = plugin.get("zip_plugin_json") or {}
    return {
        "present": True,
        "path": rel(HARVEST_AUD0029),
        "requires_python": py if isinstance(py, list) else [],
        "engines_node": node if isinstance(node, list) else [],
        "plugin_interpreters": zip_json.get("interpreters") or [],
        "plugin_source_json": plugin.get("source_plugin_json"),
        "zip_exists": bool(plugin.get("zip_exists")),
        "tomllib_hits": scope.get("tomllib_hits") or [],
        "onexc_hits": scope.get("onexc_hits") or [],
        "python_file_count": scope.get("python_files"),
        "js_file_count": scope.get("js_files"),
    }


def ci_versions() -> dict[str, Any]:
    path = HARVEST_AUD0041
    raw = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    return {
        "present": path.is_file(),
        "path": rel(path),
        "python": sorted(set(CI_PY_RE.findall(raw))),
        "node": sorted(set(CI_NODE_RE.findall(raw))),
        "note": (
            "CI versions extracted from AUD-0041 YAML inventory of "
            "actions/setup-python and actions/setup-node pin strings."
        ),
    }


def python_declared_minimum(
    harvest: dict[str, Any], live: list[dict[str, str]]
) -> dict[str, Any]:
    specs: list[dict[str, str]] = list(live)
    for row in harvest.get("requires_python") or []:
        if isinstance(row, dict) and row.get("value"):
            specs.append(
                {
                    "path": str(row.get("path")),
                    "spec": str(row["value"]),
                    "source": "HARVEST-AUD-0029",
                }
            )
    mins: list[tuple[tuple[int, ...], str, dict[str, str]]] = []
    for row in specs:
        parsed = min_from_spec(row["spec"])
        if parsed:
            mins.append((tuple(int(p) for p in parsed.split(".")[:2]), parsed, row))
    for interp in harvest.get("plugin_interpreters") or []:
        if not isinstance(interp, dict):
            continue
        floor = str(interp.get("floor") or interp.get("minimum") or "")
        parsed = min_from_spec(floor)
        if parsed:
            row = {
                "path": "plugin.json#interpreters (HARVEST zip)",
                "spec": f">={floor}",
                "source": "HARVEST-PLUGIN",
            }
            mins.append((tuple(int(p) for p in parsed.split(".")[:2]), parsed, row))
    if not mins:
        return {"version": "3.10", "tuple": [3, 10], "spec_rows": specs, "fallback": True}
    mins.sort(key=lambda x: x[0])
    return {
        "version": mins[0][1],
        "tuple": list(mins[0][0]),
        "witness": mins[0][2],
        "spec_rows": specs,
    }


def node_declared(harvest: dict[str, Any], live: list[dict[str, str]]) -> list[dict[str, str]]:
    rows = list(live)
    for row in harvest.get("engines_node") or []:
        if isinstance(row, dict) and row.get("value"):
            rows.append(
                {
                    "path": str(row.get("path")),
                    "spec": str(row["value"]),
                    "source": "HARVEST-AUD-0029",
                }
            )
    return rows


def census() -> dict[str, Any]:
    harvest = harvest_aud0029()
    live_py = live_python_requires()
    live_node = live_engines_node()
    live_plugin = live_plugin_interpreters()
    return {
        "worktree_sparse": not live_py and not live_node and not live_plugin,
        "live_python_requires": live_py,
        "live_engines_node": live_node,
        "live_plugin_interpreters": live_plugin,
        "harvest": harvest,
        "ci": ci_versions(),
        "python_declared_minimum": python_declared_minimum(harvest, live_py),
        "node_declared": node_declared(harvest, live_node),
        "false_floor_evidence": {
            "tomllib_is_3_11": True,
            "tomllib_hits_n": len(harvest.get("tomllib_hits") or []),
            "onexc_is_3_12": True,
            "onexc_hits": harvest.get("onexc_hits") or [],
            "note": (
                "Plugin zip declares python3 floor 3.10.0 while harvest records "
                "shutil.rmtree(..., onexc=) (3.12) and tomllib (3.11). Declared "
                "3.10 is not demonstrable for those surfaces."
            ),
        },
    }
