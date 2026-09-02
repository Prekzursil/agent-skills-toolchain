#!/usr/bin/env python3
"""Probe 2: write-order inspection of producing code.

Mechanically different from the truncation sweep: AST-walk producers for
destination writes that flush a sentinel (or any prefix) before the payload
is complete. Planted both-states control: sentinel-first must fire,
atomic-complete must stay silent.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from common import REPO, UNIT  # noqa: E402

PLANTED_BAD = _HERE / "fixtures" / "planted_sentinel_first.py"
PLANTED_GOOD = _HERE / "fixtures" / "planted_atomic_complete.py"
RECEIPT_WRITER = REPO / "command-center" / "receipt_writer.py"

SENTINEL_TOKENS = ("sentinel", "SUCCESS:", "SENTINEL:")


def _fail(msg: str) -> int:
    print(f"FAILED:ADV-0004-probe2 {msg}")
    return 1


def _const_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = []
        for v in node.values:
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                parts.append(v.value)
            else:
                parts.append("{expr}")
        return "".join(parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        a = _const_str(node.left)
        b = _const_str(node.right)
        if a is not None and b is not None:
            return a + b
        if a is not None:
            return a
        if b is not None:
            return b
    return None


def _name_of(func: ast.AST) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _looks_tmp(path_hint: str | None) -> bool:
    if not path_hint:
        return False
    low = path_hint.lower()
    return ".tmp" in low or "tmp_name" in low or "tmp_path" in low or "mkstemp" in low


def _path_hint(node: ast.AST) -> str | None:
    s = _const_str(node)
    if s:
        return s
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return ast.dump(node, include_attributes=False)[:120]
    if isinstance(node, ast.Call):
        return _name_of(node.func)
    return None


class FunctionFinder(ast.NodeVisitor):
    def __init__(self) -> None:
        self.funcs: list[ast.AST] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.funcs.append(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.funcs.append(node)
        self.generic_visit(node)


def _function_uses_atomic_tmp(fn: ast.AST) -> bool:
    names = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            names.add(_name_of(node.func))
    return (
        ("mkstemp" in names or "NamedTemporaryFile" in names)
        and "replace" in names
    )


def analyze_function(fn: ast.FunctionDef | ast.AsyncFunctionDef, rel: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    writes_on: dict[str, list[dict[str, Any]]] = {}
    atomic_tmp = _function_uses_atomic_tmp(fn)

    def record(target: str, lineno: int, text: str | None, tmp: bool) -> None:
        writes_on.setdefault(target, []).append(
            {
                "lineno": lineno,
                "text": (text or "")[:160],
                "tmp": tmp,
                "has_sentinel": bool(
                    text
                    and any(tok.lower() in text.lower() for tok in SENTINEL_TOKENS)
                ),
            }
        )

    loop_lines: set[int] = set()
    for node in ast.walk(fn):
        if isinstance(node, (ast.For, ast.While, ast.AsyncFor)):
            for child in ast.walk(node):
                if hasattr(child, "lineno"):
                    loop_lines.add(int(child.lineno))

    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        name = _name_of(node.func)
        if name in {"print", "dumps"}:
            continue
        if name in {"write_text", "write_bytes"}:
            # receiver.write_text(data)
            recv = node.func.value if isinstance(node.func, ast.Attribute) else None
            hint = _path_hint(recv) if recv is not None else fn.name
            data = node.args[0] if node.args else None
            record(str(hint), node.lineno, _const_str(data) if data else None, _looks_tmp(str(hint)))
        elif name == "write" and isinstance(node.func, ast.Attribute):
            recv = node.func.value
            hint = _path_hint(recv) if recv is not None else "fh"
            data = node.args[0] if node.args else None
            record(str(hint), node.lineno, _const_str(data) if data else None, _looks_tmp(str(hint)))
        elif name == "replace" and isinstance(node.func, ast.Attribute):
            # os.replace(tmp, dest) — destination receives a complete tmp.
            pass
        elif name in {"replace"} and isinstance(node.func, ast.Name):
            pass

    # with open(...) as fh:  — attribute writes already recorded as "fh"/name
    for target, events in writes_on.items():
        if _looks_tmp(target) or (atomic_tmp and target in {"fh", "f"}):
            continue
        events_sorted = sorted(events, key=lambda e: e["lineno"])
        in_loop = any(e["lineno"] in loop_lines for e in events_sorted)
        if len(events_sorted) < 2 and not in_loop:
            continue
        first = events_sorted[0]
        # Incremental writes to a non-tmp destination.
        kind = (
            "sentinel-before-payload"
            if first.get("has_sentinel")
            else "incremental-destination-write"
        )
        findings.append(
            {
                "file": rel,
                "function": fn.name,
                "lineno": first["lineno"],
                "target": target,
                "kind": kind,
                "write_count": len(events_sorted),
                "in_loop": in_loop,
                "first_write_preview": first.get("text") or "",
            }
        )
    return findings


def analyze_file(path: Path) -> list[dict[str, Any]]:
    rel = path.relative_to(REPO).as_posix() if path.is_relative_to(REPO) else str(path)
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        return [
            {
                "file": rel,
                "function": "<parse>",
                "lineno": 0,
                "kind": "unparseable",
                "detail": f"{type(exc).__name__}:{exc}",
            }
        ]
    finder = FunctionFinder()
    finder.visit(tree)
    out: list[dict[str, Any]] = []
    for fn in finder.funcs:
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.extend(analyze_function(fn, rel))
    return out


def production_emit_paths() -> list[Path]:
    paths = [RECEIPT_WRITER]
    probes = REPO / "command-center" / "p2-wave" / "probes"
    if probes.is_dir():
        for name in (
            "emit.py",
            "emit_artifact.py",
            "emit_report.py",
            "emit_receipt.py",
        ):
            paths.extend(sorted(probes.glob(f"*/{name}")))
    # De-dupe, skip our own planted fixtures (handled separately).
    seen = set()
    out = []
    for p in paths:
        if not p.is_file():
            continue
        key = p.resolve()
        if key in seen:
            continue
        if "ADV-0004/fixtures" in p.as_posix():
            continue
        seen.add(key)
        out.append(p)
    return out


def main() -> int:
    bad = analyze_file(PLANTED_BAD)
    good = analyze_file(PLANTED_GOOD)
    planted_fires = any(f.get("kind") == "sentinel-before-payload" for f in bad)
    planted_silent = [
        f
        for f in good
        if f.get("kind") in {"sentinel-before-payload", "incremental-destination-write"}
    ]

    live_findings: list[dict[str, Any]] = []
    scanned = []
    for path in production_emit_paths():
        rel = path.relative_to(REPO).as_posix()
        scanned.append(rel)
        for f in analyze_file(path):
            if f.get("kind") in {
                "sentinel-before-payload",
                "incremental-destination-write",
            }:
                live_findings.append(f)

    # receipt_writer.naive_write_bytes is a named non-production control.
    naive = [
        f
        for f in live_findings
        if f.get("function") == "naive_write_bytes"
        and f.get("file", "").endswith("receipt_writer.py")
    ]
    production = [
        f
        for f in live_findings
        if not (
            f.get("function") == "naive_write_bytes"
            and f.get("file", "").endswith("receipt_writer.py")
        )
    ]
    atomic = analyze_file(RECEIPT_WRITER)
    atomic_ok = not any(
        f.get("function") == "atomic_write_bytes"
        and f.get("kind") in {"sentinel-before-payload", "incremental-destination-write"}
        for f in atomic
    )

    controls = {
        "planted_sentinel_first_fires": planted_fires,
        "planted_atomic_complete_silent": len(planted_silent) == 0,
        "naive_write_bytes_flagged": len(naive) > 0,
        "atomic_write_bytes_not_flagged": atomic_ok,
    }
    failed = [k for k, v in controls.items() if not v]
    if failed:
        print(json.dumps({"controls": controls, "bad": bad, "good": good, "naive": naive}, indent=2))
        return _fail("controls-failed:" + ",".join(failed))

    out = {
        "ok": True,
        "probe": "probe2-write-order",
        "unit_id": UNIT,
        "controls": controls,
        "planted_bad": bad,
        "planted_good": good,
        "naive_write_bytes": naive,
        "production_incremental_or_sentinel_first": production,
        "scanned_file_count": len(scanned),
        "scanned_files_sample": scanned[:20],
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "SUCCESS:ADV-0004-probe2 "
        f"planted_fires={planted_fires} "
        f"production_hits={len(production)} "
        f"naive_flagged={len(naive)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
