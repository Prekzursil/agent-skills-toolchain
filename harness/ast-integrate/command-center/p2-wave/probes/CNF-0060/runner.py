"""Stdlib runner for the CNF-0060 skip-surface suite.

Executes tests (not just AST). Classifies skip kinds from decorators AND
runtime pytest.skip(). Collection.json deselects are a separate bucket —
not skipped, not executed.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import sys
import traceback
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from pytest_shim import Skip  # noqa: E402

PLANTED_TEST = "test_planted_target"
PLANTED_REASON = "CNF-0060-planted"
SUITE_FILE = "test_skip_surface.py"


def _platformish(node: ast.AST) -> bool:
    for n in ast.walk(node):
        if isinstance(n, ast.Attribute) and n.attr in {"platform", "name"}:
            if isinstance(n.value, ast.Name) and n.value.id in {"sys", "os"}:
                return True
        if isinstance(n, ast.Attribute) and n.attr in {"system", "machine"}:
            if isinstance(n.value, ast.Name) and n.value.id == "platform":
                return True
    return False


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Call):
        return _call_name(node.func)
    return ""


def ast_marks(path: Path) -> dict[str, list[dict[str, Any]]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    out: dict[str, list[dict[str, Any]]] = {}
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_"):
            continue
        marks: list[dict[str, Any]] = []
        for dec in node.decorator_list:
            kind = _call_name(dec)
            if kind == "skip":
                marks.append({"type": "skip", "skip_kind": "unconditional"})
            elif kind == "skipif":
                arg0 = dec.args[0] if isinstance(dec, ast.Call) and dec.args else None
                sk = "platform-conditional" if arg0 is not None and _platformish(arg0) else "conditional"
                marks.append({"type": "skipif", "skip_kind": sk})
            elif kind == "xfail":
                marks.append({"type": "xfail", "skip_kind": "xfail"})
        out[node.name] = marks
    return out


def load_collection(suite_dir: Path) -> dict[str, Any]:
    raw = json.loads((suite_dir / "collection.json").read_text(encoding="utf-8"))
    return {
        "deselect_ids": list(raw.get("deselect_ids") or []),
        "reason": str(raw.get("reason") or "deselected"),
    }


def counts_of(members: list[dict[str, Any]]) -> dict[str, int]:
    n = {"passed": 0, "failed": 0, "skipped": 0, "error": 0, "collection_error": 0, "xfailed": 0, "xpassed": 0}
    for m in members:
        o = str(m.get("outcome") or "")
        if o in n:
            n[o] += 1
    return {
        "passed": n["passed"] + n["xpassed"],
        "failed": n["failed"],
        "skipped": n["skipped"] + n["xfailed"],
        "error": n["error"],
        "collection_error": n["collection_error"],
        "total_ids": len(members),
    }


def _load(path: Path):
    name = f"cnf0060_{path.stem}_{abs(hash(str(path.resolve()))) % 10_000_000}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"no spec for {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def run_suite(suite_dir: Path) -> dict[str, Any]:
    suite_dir = suite_dir.resolve()
    path = suite_dir / SUITE_FILE
    coll = load_collection(suite_dir)
    deselect = set(coll["deselect_ids"])
    ast_map = ast_marks(path)
    sys.path.insert(0, str(HERE))
    try:
        mod = _load(path)
    except Exception as exc:
        return {
            "label": suite_dir.name,
            "members": [
                {
                    "id": f"{SUITE_FILE}::<collection>",
                    "outcome": "collection_error",
                    "diagnostic": f"{type(exc).__name__}: {exc}",
                }
            ],
            "counts": {
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "error": 0,
                "collection_error": 1,
                "total_ids": 1,
            },
            "executed_ids": [],
            "skipped_ids": [],
            "xfailed_ids": [],
            "deselected": [
                {"id": f"{SUITE_FILE}::{n}", "reason": coll["reason"]} for n in sorted(deselect)
            ],
            "collection_error": True,
        }

    members: list[dict[str, Any]] = []
    deselected_rows: list[dict[str, str]] = []
    tests = [
        (name, getattr(mod, name))
        for name in dir(mod)
        if name.startswith("test_") and callable(getattr(mod, name))
    ]
    tests.sort(key=lambda t: t[0])
    for name, fn in tests:
        nid = f"{SUITE_FILE}::{name}"
        if name in deselect:
            deselected_rows.append({"id": nid, "reason": coll["reason"]})
            continue
        runtime_marks = list(getattr(fn, "_cnf60_marks", []))
        ast_m = ast_map.get(name) or []
        skip_kind = None
        skip_reason = ""
        xfail_reason = ""
        outcome = None
        for m in runtime_marks:
            if m.get("type") == "skip":
                outcome = "skipped"
                skip_kind = "unconditional"
                skip_reason = str(m.get("reason") or "")
            elif m.get("type") == "skipif" and m.get("condition"):
                outcome = "skipped"
                skip_kind = next(
                    (a["skip_kind"] for a in ast_m if a.get("type") == "skipif"),
                    "conditional",
                )
                skip_reason = str(m.get("reason") or "")
            elif m.get("type") == "xfail":
                xfail_reason = str(m.get("reason") or "")
        row: dict[str, Any] = {"id": nid}
        if outcome == "skipped":
            row.update(
                {
                    "outcome": "skipped",
                    "diagnostic": skip_reason,
                    "skip_kind": skip_kind,
                    "skip_reason": skip_reason,
                    "executed": False,
                }
            )
            members.append(row)
            continue
        try:
            fn()
        except Skip as sk:
            row.update(
                {
                    "outcome": "skipped",
                    "diagnostic": sk.reason,
                    "skip_kind": "runtime-unconditional",
                    "skip_reason": sk.reason,
                    "executed": False,
                }
            )
        except Exception as exc:
            tb = traceback.format_exc().splitlines()[-1]
            if xfail_reason:
                row.update(
                    {
                        "outcome": "xfailed",
                        "diagnostic": f"{xfail_reason}: {tb}",
                        "xfail_reason": xfail_reason,
                        "executed": True,
                    }
                )
            else:
                row.update(
                    {
                        "outcome": "failed",
                        "diagnostic": f"{type(exc).__name__}: {exc}",
                        "executed": True,
                    }
                )
        else:
            if xfail_reason:
                row.update(
                    {
                        "outcome": "xpassed",
                        "diagnostic": xfail_reason,
                        "xfail_reason": xfail_reason,
                        "executed": True,
                    }
                )
            else:
                row.update({"outcome": "passed", "executed": True})
        if any(a.get("type") == "skipif" for a in ast_m) and row.get("outcome") != "skipped":
            row["skipif_armed_but_false"] = next(
                a["skip_kind"] for a in ast_m if a.get("type") == "skipif"
            )
        members.append(row)

    executed_ids = sorted(m["id"] for m in members if m.get("executed") is True)
    skipped_ids = sorted(m["id"] for m in members if m.get("outcome") == "skipped")
    xfailed_ids = sorted(m["id"] for m in members if m.get("outcome") in {"xfailed", "xpassed"})
    return {
        "label": suite_dir.name,
        "members": members,
        "counts": counts_of(members),
        "executed_ids": executed_ids,
        "executed_count": len(executed_ids),
        "skipped_ids": skipped_ids,
        "xfailed_ids": xfailed_ids,
        "deselected": deselected_rows,
        "deselected_ids": [d["id"] for d in deselected_rows],
        "collection_error": False,
        "source": str(path),
    }


def plant_skip(suite_dir: Path, test_name: str = PLANTED_TEST, reason: str = PLANTED_REASON) -> str:
    path = suite_dir / SUITE_FILE
    text = path.read_text(encoding="utf-8")
    line = f'@pytest.mark.skip(reason="{reason}")\n'
    needle = f"def {test_name}("
    if f'reason="{reason}"' in text and needle in text:
        return f"{SUITE_FILE}::{test_name}"
    if needle not in text:
        raise FileNotFoundError(f"{needle} not in {path}")
    path.write_text(text.replace(needle, line + needle, 1), encoding="utf-8")
    return f"{SUITE_FILE}::{test_name}"
