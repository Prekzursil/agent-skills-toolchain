#!/usr/bin/env python3
"""Mechanical capability-path enumerator for ARC-0045.

Order:
  1. Prove the detector on a known-present live path.
  2. Enumerate @capability_entry design wrappers (must call the choke).
  3. Enumerate current-tree invocation entries by AST.
  4. Optionally include a planted bypass using the same side-effect detector.
"""
from __future__ import annotations

import ast
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

# Calibrated on a path that exists on THIS Linux worktree. The Windows
# plugin/marketplace/foundry trees named in an earlier receipt are absent here
# (tools/plugin is schema-only; tools/marketplace, tools/council, tools/foundry
# are missing). Sweeping those roots would make the detector miss a known-present
# path and fail closed.
KNOWN_PRESENT_REL = "tools/mcp/cloud-hub/hub.py"
KNOWN_PRESENT_QUAL = "HubServer.dispatch"
DESIGN_REL = "command-center/p2-wave/probes/ARC-0045/dispatch.py"
PLANT_REL = "command-center/p2-wave/probes/ARC-0045/fixtures/planted_bypass.py"

ENTRY_NAMES = frozenset(
    {
        "dispatch",
        "dispatch_url",
        "call",
        "ensure_server",
        "invoke",
        "execute",
        "install",
        "activate",
        "_spawn",
        "_spawn_stdio",
        "_spawn_http",
        "default_spawn",
        "run_live",
        "call_tool",
        "run_scout",
        "run_forge",
        "run_tournament",
        "search_marketplace",
        "run_via_runtime",
    }
)
SIDE_EFFECT_ATTRS = frozenset({"Popen", "run", "system", "urlopen", "urlretrieve"})
CHOKE_NAMES = frozenset({"evaluate", "require_grant", "_run"})
SWEEP_ROOTS = (
    "tools/mcp/cloud-hub",
    "tools/mcp/search-hub",
    "tools/mcp/social-hub",
    "tools/mcp/mcp-http-host",
    "tools/mcpapply",
    "tools/crcp/crcp",
    "tools/agentrail/agentrail",
    "tools/marketplace",
    "tools/plugin",
    "tools/council",
    "tools/foundry",
)
SKIP_DIR_NAMES = frozenset({"__pycache__", "tests", "testdata", "fixtures"})
FAMILY_RULES: tuple[tuple[str, str], ...] = (
    ("tools/mcp/cloud-hub/", "mcp.cloud_hub"),
    ("tools/mcp/search-hub/", "mcp.search_hub"),
    ("tools/mcp/social-hub/", "mcp.social_hub"),
    ("tools/mcp/mcp-http-host/", "mcp.http_host"),
    ("tools/mcpapply/", "mcp.apply"),
    ("tools/crcp/", "crcp.dispatch"),
    ("tools/agentrail/", "agentrail.dispatch"),
    ("tools/marketplace/gates.py", "marketplace.install"),
    ("tools/marketplace/api.py", "marketplace.dispatch"),
    ("tools/marketplace/", "marketplace.dispatch"),
    ("tools/plugin/registration_reconciler.py", "plugin.register"),
    ("tools/plugin/", "plugin.activate"),
    ("tools/council/", "council.invoke"),
    ("tools/foundry/runtime.py", "workflow.execute"),
    ("tools/foundry/scout.py", "foundry.scout"),
    ("tools/foundry/forge.py", "foundry.forge"),
    ("tools/foundry/tournament.py", "foundry.tournament"),
    ("tools/foundry/", "workflow.execute"),
)


@dataclass(frozen=True)
class PathRow:
    rel: str
    qual: str
    family: str
    source: str
    calls_choke: bool
    has_side_effect: bool
    crosses: bool
    shortfall_reason: str


def _qual(stack: list[str], name: str) -> str:
    return ".".join([*stack, name])


def _calls_name(node: ast.AST, names: frozenset[str]) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Name) and func.id in names:
                return True
            if isinstance(func, ast.Attribute) and func.attr in names:
                return True
    return False


def _has_side_effect(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        func = child.func
        if isinstance(func, ast.Attribute) and func.attr in SIDE_EFFECT_ATTRS:
            return True
        if isinstance(func, ast.Name) and func.id in {"Popen", "urlopen"}:
            return True
    return False


def _decorator_family(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    for dec in node.decorator_list:
        if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name):
            if dec.func.id == "capability_entry" and dec.args:
                arg0 = dec.args[0]
                if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                    return arg0.value
    return None


def _family_for(rel: str, qual: str) -> str:
    posix = rel.replace("\\", "/")
    if posix.endswith("mcp_activation.py") and "_spawn_" in qual:
        return "plugin.activate"
    if posix.endswith("mcp_activation.py"):
        return "plugin.mcp_call"
    for prefix, family in FAMILY_RULES:
        if posix == prefix or posix.startswith(prefix):
            return family
    return "unclassified"


def iter_py(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    files: list[Path] = []
    for path in sorted(root.rglob("*.py")):
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        files.append(path)
    return files


def parse_functions(path: Path, rel: str) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
    except (OSError, SyntaxError, UnicodeDecodeError):
        return []
    rows: list[dict[str, Any]] = []

    def visit(nodes: Iterable[ast.stmt], stack: list[str]) -> None:
        for node in nodes:
            if isinstance(node, ast.ClassDef):
                visit(node.body, [*stack, node.name])
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("__") and node.name.endswith("__"):
                    continue
                rows.append(
                    {
                        "rel": rel,
                        "qual": _qual(stack, node.name),
                        "name": node.name,
                        "calls_choke": _calls_name(node, CHOKE_NAMES),
                        "has_side_effect": _has_side_effect(node),
                        "decorator_family": _decorator_family(node),
                    }
                )
                visit(node.body, [*stack, node.name])

    visit(tree.body, [])
    return rows


def is_live_entry(row: dict[str, Any]) -> bool:
    name = str(row["name"])
    if name in ENTRY_NAMES:
        return True
    # mcp-http-host mints the child in StdioChild._ensure / start, not via a
    # name in ENTRY_NAMES. Do not treat every start() in the tree as an entry.
    rel = str(row["rel"]).replace("\\", "/")
    if rel.endswith("mcp_http_host.py") and name in {"start", "_ensure"}:
        return True
    return False


def to_path_row(row: dict[str, Any], source: str) -> PathRow:
    family = row.get("decorator_family") or row.get("family") or _family_for(row["rel"], row["qual"])
    calls = bool(row["calls_choke"])
    if source == "design":
        crosses = calls and bool(row.get("decorator_family"))
        reason = "" if crosses else "design-wrapper-misses-choke"
    elif source == "planted":
        crosses = False
        reason = "planted-bypass"
    else:
        crosses = calls
        reason = "" if crosses else "live-unwired-migration-debt"
    return PathRow(
        rel=row["rel"],
        qual=row["qual"],
        family=str(family),
        source=source,
        calls_choke=calls,
        has_side_effect=bool(row["has_side_effect"]),
        crosses=crosses,
        shortfall_reason=reason,
    )


def find_known_present(live_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    want = KNOWN_PRESENT_REL.replace("\\", "/")
    for row in live_rows:
        if row["rel"].replace("\\", "/") == want and row["qual"] == KNOWN_PRESENT_QUAL:
            return row
    return None


def sweep(*, include_plant: bool = False, mutant_blind: bool = False) -> dict[str, Any]:
    design_fns = parse_functions(HERE / "dispatch.py", DESIGN_REL)
    design_entries = [r for r in design_fns if r.get("decorator_family")]
    design_rows = [to_path_row(r, "design") for r in design_entries]

    live_fns: list[dict[str, Any]] = []
    for root_rel in SWEEP_ROOTS:
        for path in iter_py(REPO / root_rel):
            rel = path.relative_to(REPO).as_posix()
            live_fns.extend(parse_functions(path, rel))
    known = find_known_present(live_fns)
    calibration_ok = known is not None and is_live_entry(known)
    live_entries = [r for r in live_fns if is_live_entry(r)]
    live_rows = [to_path_row(r, "current-tree") for r in live_entries]

    plant_rows: list[PathRow] = []
    if include_plant:
        plant_fns = parse_functions(HERE / "fixtures" / "planted_bypass.py", PLANT_REL)
        for row in plant_fns:
            if mutant_blind:
                continue
            if row["has_side_effect"] and not row["calls_choke"]:
                row["family"] = "planted.bypass"
                plant_rows.append(to_path_row(row, "planted"))

    families_live = sorted({p.family for p in live_rows})
    families_design = sorted({p.family for p in design_rows})
    families_missing_wrapper = [f for f in families_live if f not in set(families_design)]

    enumerated = [*design_rows, *live_rows, *plant_rows]
    crossing = [p for p in enumerated if p.crosses]
    shortfall = [p for p in enumerated if not p.crosses]
    n_enum = len(enumerated)
    n_cross = len(crossing)
    design_enum = len(design_rows)
    design_cross = sum(1 for p in design_rows if p.crosses)

    return {
        "calibration": {
            "ok": bool(calibration_ok),
            "rel": KNOWN_PRESENT_REL,
            "qual": KNOWN_PRESENT_QUAL,
            "found": known is not None,
            "is_entry": bool(known and is_live_entry(known)),
            "calls_choke": bool(known and known["calls_choke"]),
        },
        "design": {
            "enumerated": design_enum,
            "crossing": design_cross,
            "coverage": (design_cross / design_enum) if design_enum else 0.0,
            "families": families_design,
            "rows": [asdict(p) for p in design_rows],
        },
        "current_tree": {
            "enumerated": len(live_rows),
            "crossing": sum(1 for p in live_rows if p.crosses),
            "families": families_live,
            "families_missing_wrapper": families_missing_wrapper,
            "rows": [asdict(p) for p in live_rows],
        },
        "plant": {
            "included": include_plant,
            "found": any(p.source == "planted" for p in enumerated),
            "mutant_blind": mutant_blind,
            "rows": [asdict(p) for p in plant_rows],
        },
        "coverage": {
            "enumerated": n_enum,
            "crossing": n_cross,
            "ratio": (n_cross / n_enum) if n_enum else 0.0,
            "shortfall_count": len(shortfall),
            "shortfall": [asdict(p) for p in shortfall],
        },
    }


def dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


if __name__ == "__main__":
    import sys

    plant = "--plant" in sys.argv
    mutant = "--mutant-blind" in sys.argv
    print(dump(sweep(include_plant=plant, mutant_blind=mutant)), end="")
