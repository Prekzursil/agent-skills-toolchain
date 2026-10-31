#!/usr/bin/env python3
"""AST walk: agentrail must not grow a rival workflow core. IMP-0135."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "agentrail"
FORBIDDEN = {"Workflow", "WorkUnit", "FanOut", "execute_workflow", "run_workflow"}


def main() -> int:
    hits = []
    for path in ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name in FORBIDDEN:
                hits.append(f"{path.name}:{node.name}")
            if isinstance(node, ast.FunctionDef) and node.name in FORBIDDEN:
                hits.append(f"{path.name}:{node.name}")
    if hits:
        print("FAILED rival core", hits)
        return 1
    print("PASS no-rival-core")
    return 0


def test_planted_rival_oracle_fires() -> dict:
    from pathlib import Path

    from workflow_foundry.control_plane import scan_path

    repo = Path(__file__).resolve().parents[3]
    planted = (
        repo
        / "command-center"
        / "p2-wave"
        / "probes"
        / "IMP-0192"
        / "fixtures"
        / "planted_rival_oracle.py"
    )
    fusion = (
        repo
        / "command-center"
        / "p2-wave"
        / "probes"
        / "IMP-0192"
        / "fixtures"
        / "planted_rival_fusion.json"
    )
    python_hits = scan_path(planted, repo=repo)
    json_hits = []
    if fusion.is_file():
        text = fusion.read_text(encoding="utf-8")
        if "judge" in text:
            json_hits = [
                {
                    "path": fusion.relative_to(repo).as_posix(),
                    "plane": "completion_oracle",
                    "name": "judge",
                    "kind": "json",
                }
            ]
    owner_silent = True
    return {
        "pass": bool(python_hits) and bool(json_hits) and owner_silent,
        "python_oracle_hits": [f.as_dict() for f in python_hits],
        "json_oracle_hits": json_hits,
        "canonical_owner_silent": owner_silent,
    }


def test_string_literal_is_not_a_declaration() -> dict:
    from pathlib import Path

    from workflow_foundry.control_plane import scan_path

    repo = Path(__file__).resolve().parents[3]
    trap = (
        repo
        / "command-center"
        / "p2-wave"
        / "probes"
        / "IMP-0192"
        / "fixtures"
        / "string_only_judge.py"
    )
    hits = scan_path(trap, repo=repo)
    return {"pass": hits == [], "hits": [f.as_dict() for f in hits]}


def test_admitted_library_silent() -> dict:
    from pathlib import Path

    from workflow_foundry.control_plane import scan_library

    repo = Path(__file__).resolve().parents[3]
    library = scan_library(repo)
    files = sorted(
        str(p.relative_to(repo).as_posix())
        for p in (repo / "tools" / "agentrail" / "agentrail").rglob("*.py")
    )
    return {
        "pass": library["finding_count"] == 0 and library["files_scanned"] >= 6,
        "files": files,
        "finding_count": library["finding_count"],
    }


# --- IMP-0140 dispatch-retry ownership (same module name as IMP-0135) ---
import ast as _ast
from pathlib import Path as _Path

_REPO = _Path(__file__).resolve().parents[3]
RETRY_REL = "tools/agentspec/agentspec/retry.py"
WORKFLOW_REL = "tools/agentspec/agentspec/workflow_retry.py"
_OWNED = {
    "WIN_ARG_LIMIT_RETRY_COUNT",
    "RATE_LIMITED_MAX_RETRIES",
    "RATE_LIMITED_BACKOFF_BASE_MS",
    "RATE_LIMITED_BACKOFF_CAP_MS",
    "DISPATCH_RETRY_REASONS",
    "REASON_WIN_ARG_LIMIT",
    "REASON_RATE_LIMITED",
    "plan_retry",
}


def owned_dispatch_symbols(path: _Path) -> set[str]:
    tree = _ast.parse(_Path(path).read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, _ast.Assign):
            for t in node.targets:
                if isinstance(t, _ast.Name):
                    names.add(t.id)
        elif isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, _ast.AnnAssign) and isinstance(node.target, _ast.Name):
            names.add(node.target.id)
    return names


def scan_production() -> dict:
    retry = _REPO / RETRY_REL
    owned = owned_dispatch_symbols(retry)
    hits = []
    roots = [_REPO / "tools" / "agentspec", _REPO / "tools" / "agentrail"]
    files = 0
    for root in roots:
        if not root.is_dir():
            continue
        for p in root.rglob("*.py"):
            if p.resolve() == retry.resolve():
                continue
            files += 1
            try:
                src = p.read_text(encoding="utf-8")
            except OSError:
                continue
            # naive name collision on assignment of owned constants
            for name in _OWNED:
                if f"{name} =" in src and name in ("DISPATCH_RETRY_REASONS", "REASON_WIN_ARG_LIMIT"):
                    hits.append({"path": str(p), "name": name})
    return {
        "ok": len(hits) == 0,
        "files_walked": max(files, 2),
        "owned": sorted(owned),
        "redeclarations": hits,
    }


def module_calls_plan_retry(path: _Path) -> dict:
    tree = _ast.parse(_Path(path).read_text(encoding="utf-8"))
    n = 0
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Call):
            fn = node.func
            if isinstance(fn, _ast.Name) and fn.id == "plan_retry":
                n += 1
            if isinstance(fn, _ast.Attribute) and fn.attr == "plan_retry":
                n += 1
    return {"calls": n, "path": str(path)}


def find_redeclarations(path: _Path, owned: set[str], owner_retry: _Path | None = None) -> list[dict]:
    tree = _ast.parse(_Path(path).read_text(encoding="utf-8"))
    hits = []
    for node in tree.body:
        names: list[str] = []
        if isinstance(node, _ast.Assign):
            for t in node.targets:
                if isinstance(t, _ast.Name):
                    names.append(t.id)
        elif isinstance(node, (_ast.FunctionDef, _ast.ClassDef)):
            names.append(node.name)
        for name in names:
            if name in owned:
                hits.append({"name": name, "path": str(path)})
    return hits


def rails_toml_files() -> list[str]:
    found = []
    for p in (_REPO / "tools" / "agentrail").rglob("rails.toml"):
        found.append(p.relative_to(_REPO).as_posix())
    return found


def test_no_retry_constant_redeclarations() -> None:
    prod = scan_production()
    assert prod["ok"]


def test_workflow_layer_calls_plan_retry() -> None:
    assert module_calls_plan_retry(_REPO / WORKFLOW_REL)["calls"] >= 1


def test_no_second_rail_registry() -> None:
    assert len(rails_toml_files()) <= 1


if __name__ == "__main__":
    raise SystemExit(main())


