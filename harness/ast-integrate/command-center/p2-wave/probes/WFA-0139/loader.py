"""Locate live harness-restore graphs; fall back to the catalog-reconstructed seed."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import seed as S

GRAPH_NAME = "08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json"
MAPS_NAME = "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json"


def candidate_dirs(repo: Path) -> list[Path]:
    home = Path.home()
    return [
        Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806"),
        Path("/c/Users/Prekzursil/.claude/harness-restore-20260806"),
        home / ".claude" / "harness-restore-20260806",
        Path("/home/ubuntu/.claude/harness-restore-20260806"),
        repo / "harness-restore-20260806",
        repo / "command-center" / "harness-restore-20260806",
        repo / "C:" / "Users" / "Prekzursil" / ".claude" / "harness-restore-20260806",
    ]


def _try_load(path: Path) -> dict[str, Any] | None:
    if not path.is_file() or path.stat().st_size <= 0:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def live_probe(repo: Path) -> dict[str, Any]:
    tried: list[dict[str, Any]] = []
    graph = None
    maps = None
    graph_path = None
    maps_path = None
    extra = os.environ.get("WFA0139_HARNESS_DIR")
    dirs = [Path(extra)] if extra else []
    dirs.extend(candidate_dirs(repo))
    for folder in dirs:
        gpath = folder / GRAPH_NAME
        mpath = folder / MAPS_NAME
        tried.append(
            {
                "dir": str(folder),
                "graph_exists": gpath.is_file(),
                "maps_exists": mpath.is_file(),
            }
        )
        if graph is None:
            loaded = _try_load(gpath)
            if loaded is not None:
                graph = loaded
                graph_path = str(gpath)
        if maps is None:
            loaded = _try_load(mpath)
            if loaded is not None:
                maps = loaded
                maps_path = str(mpath)
    return {
        "tried": tried,
        "graph_path": graph_path,
        "maps_path": maps_path,
        "graph": graph,
        "maps": maps,
    }


def extract_live(
    graph: dict[str, Any] | None, maps: dict[str, Any] | None
) -> dict[str, Any] | None:
    if not isinstance(graph, dict) or not isinstance(maps, dict):
        return None
    rules = graph.get("license_classification_rules")
    register = graph.get("license_risk_register")
    units = maps.get("merge_units")
    if not isinstance(rules, list) or len(rules) != 7:
        return None
    if not isinstance(register, list) or len(register) != 45:
        return None
    if not isinstance(units, list) or len(units) != 30:
        return None
    return {"rules": rules, "register": register, "merge_units": units, "kind": "live-graph"}


def load_corpus(repo: Path) -> dict[str, Any]:
    probe = live_probe(repo)
    live = extract_live(probe.get("graph"), probe.get("maps"))
    if live is not None:
        by_id: dict[str, dict[str, Any]] = {}
        for row in live["register"]:
            if isinstance(row, dict) and row.get("id"):
                by_id[str(row["id"])] = row
        return {
            "kind": "live-graph",
            "rules": live["rules"],
            "register": live["register"],
            "register_by_id": by_id,
            "merge_units": live["merge_units"],
            "graph_path": probe["graph_path"],
            "maps_path": probe["maps_path"],
            "tried": probe["tried"],
        }
    register = S.risk_register()
    return {
        "kind": "catalog-reconstructed-fixture",
        "rules": S.classification_rules(),
        "register": register,
        "register_by_id": {row["id"]: row for row in register},
        "merge_units": S.merge_units(),
        "graph_path": None,
        "maps_path": None,
        "tried": probe["tried"],
        "histogram": S.histogram(register),
    }
