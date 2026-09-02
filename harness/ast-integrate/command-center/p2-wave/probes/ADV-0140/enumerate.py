"""Dispatch-graph enumerator for ADV-0140.

Walks shipped plugin / marketplace / foundry / council (plus catalog
dispatcher and workflow YAML) and classifies sinks by EFFECT. Fixture
trees are optional and labeled origin=scratch-control.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import effects as E  # noqa: E402
from fake_sink import FakeSink  # noqa: E402

PROD_ROOTS = (
    "tools/plugin",
    "tools/marketplace",
    "tools/workflow_foundry",
    "tools/council",
    "tools/lib",
    "tools/agentspec",
    "tools/command-center",
    "command-center/ready_units.py",
    ".github/workflows",
)
SKIP_PARTS = {
    "tests",
    "probes",
    "__pycache__",
    "p2-wave",
    "node_modules",
    ".git",
}
ENTRY_HINTS = ("main", "cli", "run", "dispatch", "handle", "trigger", "compile", "execute")


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return path.as_posix()


def _skip(path: Path) -> bool:
    if set(path.parts) & SKIP_PARTS:
        return True
    return path.suffix not in {".py", ".yml", ".yaml"}


def iter_files(roots: list[Path]) -> list[Path]:
    out: list[Path] = []
    for root in roots:
        if root.is_file() and not _skip(root):
            out.append(root)
            continue
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file() and not _skip(path):
                out.append(path)
    return out


def _call_graph(tree: ast.AST) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            callees: set[str] = set()
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    qual = E._qual(child.func)
                    leaf = qual.split(".")[-1] if qual else ""
                    if leaf:
                        callees.add(leaf)
            graph[node.name] = callees
    return graph


def bags_to_paths(
    bags: list[E.FunctionBag],
    tree: ast.AST,
    *,
    origin: str,
) -> list[dict[str, Any]]:
    _ = _call_graph(tree)
    rows: list[dict[str, Any]] = []
    for bag in bags:
        fx = bag.effects()
        if not fx:
            continue
        gates = sorted(bag.gate_hits)
        gated = bool(gates or bag.gated())
        for effect in sorted(fx):
            rows.append(
                {
                    "path_id": f"{effect}:{origin}:{bag.rel}:{bag.name}:{bag.lineno}",
                    "path_id": f"{effect}:{origin}:{bag.rel}:{bag.name}:{bag.lineno}",
                    "action_class": effect,
                    "origin": origin,
                    "entry": {
                        "kind": "function",
                        "symbol": bag.name,
                        "file": bag.rel,
                        "line": bag.lineno,
                    },
                    "sink": {
                        "effect": effect,
                        "file": bag.rel,
                        "line": bag.lineno,
                        "symbol": bag.name,
                        "identification": "effect (hosts/methods/argv/fs), not function name",
                        "urls": sorted(set(bag.urls)),
                        "methods": sorted(bag.methods),
                    },
                    "nodes": [bag.name],
                    "gate": (
                        {"kind": "checkpoint", "symbols": gates, "file": bag.rel}
                        if gated
                        else None
                    ),
                    "gated": gated,
                    "fake_sink_proof": None,
                    "fake_sink_proof": None,
                }
            )
    return rows


def scan_python(path: Path, *, origin: str) -> list[dict[str, Any]]:
    src = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    bags = E.classify_module(src, _rel(path) if origin == "production" else f"fixtures/{path.name}")
    return bags_to_paths(bags, tree, origin=origin)


def scan_yaml(path: Path, *, origin: str) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    rel = _rel(path)
    lowered = text.lower()
    hits: list[str] = []
    if "npm publish" in lowered or "twine upload" in lowered:
        hits.append("public_publishing")
    if "gh repo create" in lowered or "gh org create" in lowered:
        hits.append("creating_public_repositories_or_organizations")
    if "rm -rf" in lowered and "user_data" in lowered:
        hits.append("deleting_user_data")
    gated = "environment:" in lowered or "human_checkpoint" in lowered
    rows: list[dict[str, Any]] = []
    for effect in hits:
        rows.append(
            {
                "path_id": f"{effect}:{origin}:{rel}:workflow",
                "action_class": effect,
                "origin": origin,
                "entry": {"kind": "workflow", "symbol": path.name, "file": rel, "line": 1},
                "sink": {
                    "effect": effect,
                    "file": rel,
                    "line": 1,
                    "symbol": path.name,
                    "identification": "effect (workflow mutating publish/org/user-data verbs)",
                    "urls": [],
                    "methods": [],
                },
                "nodes": [path.name],
                "gate": (
                    {"kind": "environment-gate", "symbols": ["environment"], "file": rel}
                    if gated
                    else None
                ),
                "gated": gated,
                "fake_sink_proof": None,
            }
        )
    return rows


def _load_fixture(name: str):
    path = HERE / "fixtures" / name
    spec = importlib.util.spec_from_file_location(f"adv0140_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def prove_ungated_publish() -> dict[str, Any]:
    plant = _load_fixture("ungated_publish.py")
    sink = FakeSink()
    plant.TRANSPORT = sink
    getattr(plant, "scratch_cli_publish", plant.scratch_cli_publish)(b"fake-wheel")
    if sink.real_transport_invoked:
        raise RuntimeError("real transport invoked")
    if not sink.calls:
        raise RuntimeError("fake sink recorded no calls")
    call = sink.calls[0]
    if "pypi.org" not in call["url"] or call["method"] != "POST":
        raise RuntimeError(f"unexpected fake call {call}")
    return sink.as_receipt()


def rename_control() -> dict[str, Any]:
    src_path = HERE / "fixtures" / "gated_publish.py"
    src = src_path.read_text(encoding="utf-8")
    original = "upload_distribution"
    renamed = "dispatch_bytes_to_index"
    if f"def {original}" not in src:
        raise RuntimeError("rename control fixture missing original symbol")
    mutated = src.replace(f"def {original}", f"def {renamed}")
    before = E.classify_module(src, "fixtures/gated_publish.py")
    after = E.classify_module(mutated, "fixtures/gated_publish.py.renamed")
    before_hit = [b for b in before if "public_publishing" in b.effects()]
    after_hit = [b for b in after if "public_publishing" in b.effects()]
    if not before_hit or not after_hit:
        raise RuntimeError("effect classifier lost the sink on rename")
    name_lost = (not E.name_based_would_hit(renamed)) and E.name_based_would_hit(
        original
    )
    if not name_lost:
        raise RuntimeError("name-based foil did not lose the renamed sink")
    row_before = before_hit[0].as_row()
    row_after = after_hit[0].as_row()
    return {
        "original_symbol": original,
        "renamed_symbol": renamed,
        "effect_before": row_before,
        "effect_after": row_after,
        "effect_still_classified": True,
        "name_based_lost_renamed_sink": True,
        "identification": "POST + upload.pypi.org host, independent of def name",
    }


def enumerate_all(*, include_fixtures: bool = True) -> dict[str, Any]:
    roots = [REPO / r for r in PROD_ROOTS]
    scanned = iter_files(roots)
    prod_rows: list[dict[str, Any]] = []
    for path in scanned:
        if path.suffix == ".py":
            prod_rows.extend(scan_python(path, origin="production"))
        else:
            prod_rows.extend(scan_yaml(path, origin="production"))

    control_rows: list[dict[str, Any]] = []
    if include_fixtures:
        for path in sorted((HERE / "fixtures").glob("*.py")):
            control_rows.extend(scan_python(path, origin="scratch-control"))

    proof = prove_ungated_publish()
    for row in control_rows:
        if row["action_class"] == "public_publishing" and not row["gated"]:
            row["fake_sink_proof"] = proof

    by_class: dict[str, list[dict[str, Any]]] = {c: [] for c in E.ACTION_CLASSES}
    for row in prod_rows + control_rows:
        by_class.setdefault(row["action_class"], []).append(row)

    ungated = [r for r in prod_rows + control_rows if not r["gated"]]
    for row in ungated:
        if row["origin"] == "production" and row["fake_sink_proof"] is None:
            raise RuntimeError(f"unproven production ungated path {row['path_id']}")

    planted = [
        r
        for r in control_rows
        if r["action_class"] == "public_publishing" and not r["gated"]
    ]
    if not planted:
        raise RuntimeError("planted ungated publish path not found")

    return {
        "production_paths": prod_rows,
        "control_paths": control_rows,
        "by_class": by_class,
        "ungated": ungated,
        "planted_bypass": planted,
        "rename_control": rename_control(),
        "fake_sink_receipt": proof,
        "fake_sink_receipt": proof,
        "no_real_sink_executed": True,
        "files_scanned": [_rel(p) for p in scanned],
        "files_scanned": [_rel(p) for p in scanned],
    }


enumerate_all = enumerate_all
PROD_ROOTS = PROD_ROOTS
enumerate_all = enumerate_all
PROD_ROOTS = PROD_ROOTS


def main() -> int:
    doc = enumerate_all()
    summary = {
        k: {
            "n": len(v),
            "ungated": sum(1 for r in v if not r["gated"]),
            "origins": sorted({r["origin"] for r in v}),
        }
        for k, v in doc["by_class"].items()
    }
    print(json.dumps({"classes": summary, "planted": len(doc["planted_bypass"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
