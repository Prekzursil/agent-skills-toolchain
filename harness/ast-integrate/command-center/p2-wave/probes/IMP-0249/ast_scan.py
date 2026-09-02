"""AST scan: a council consumer must not embed a deliberation control plane."""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable

FORBIDDEN_DEF_NAMES = frozenset(
    {
        "deliberate",
        "run_round",
        "run_rounds",
        "take_turn",
        "collect_votes",
        "tally_votes",
        "aggregate_votes",
        "synthesize_from_votes",
        "moderate_council",
        "council_loop",
        "moderator_loop",
    }
)
DELIB_CALL_NAMES = frozenset(
    {
        "speak",
        "vote",
        "rebut",
        "reply",
        "synthesize",
        "deliberate",
        "run_round",
        "take_turn",
        "collect_votes",
        "tally",
        "moderate",
        "complete",
        "chat",
        "generate",
    }
)
ROUND_HINTS = frozenset({"round", "rounds", "turn", "turns", "cycle", "cycles"})
PART_HINTS = frozenset(
    {"participant", "participants", "seat", "seats", "voice", "voices", "member", "members", "voter", "voters"}
)


def _names_in(node: ast.AST) -> set[str]:
    out: set[str] = set()
    if isinstance(node, ast.Name):
        out.add(node.id.lower())
    elif isinstance(node, ast.Attribute):
        out.add(node.attr.lower())
        out |= _names_in(node.value)
    elif isinstance(node, ast.Tuple | ast.List):
        for elt in node.elts:
            out |= _names_in(elt)
    elif isinstance(node, ast.Call):
        out |= _names_in(node.func)
        for arg in node.args:
            out |= _names_in(arg)
    elif isinstance(node, ast.Constant) and isinstance(node.value, str):
        out.add(node.value.lower())
    elif isinstance(node, ast.Subscript):
        out |= _names_in(node.value)
        out |= _names_in(node.slice)
    return out


def _call_name(node: ast.Call) -> str:
    fn = node.func
    if isinstance(fn, ast.Name):
        return fn.id.lower()
    if isinstance(fn, ast.Attribute):
        return fn.attr.lower()
    return ""


def _has_delib_call(nodes: Iterable[ast.AST]) -> bool:
    for node in nodes:
        for child in ast.walk(node):
            if isinstance(child, ast.Call) and _call_name(child) in DELIB_CALL_NAMES:
                return True
    return False


def _hinted(names: set[str], hints: frozenset[str]) -> bool:
    for name in names:
        tokens = set(name.replace("-", "_").split("_"))
        tokens.add(name)
        if tokens & hints:
            return True
    return False


def _for_kind(node: ast.For) -> str | None:
    names = _names_in(node.target) | _names_in(node.iter)
    if _hinted(names, ROUND_HINTS):
        return "round"
    if _hinted(names, PART_HINTS):
        return "participant"
    return None


def scan_source(src: str, *, filename: str = "<mem>") -> dict:
    tree = ast.parse(src, filename=filename)
    hits: list[dict] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if node.name.lower() in FORBIDDEN_DEF_NAMES:
                hits.append(
                    {
                        "kind": "forbidden-def",
                        "name": node.name,
                        "lineno": node.lineno,
                        "file": filename,
                    }
                )
        if isinstance(node, ast.For):
            kind = _for_kind(node)
            if kind == "round":
                inner_fors = [c for c in ast.walk(node) if isinstance(c, ast.For) and c is not node]
                part_inners = [c for c in inner_fors if _for_kind(c) == "participant"]
                if part_inners and _has_delib_call(part_inners):
                    hits.append(
                        {
                            "kind": "nested-round-participant-loop",
                            "lineno": node.lineno,
                            "file": filename,
                        }
                    )
            if kind == "participant" and _has_delib_call(node.body):
                hits.append(
                    {
                        "kind": "participant-turn-loop",
                        "lineno": node.lineno,
                        "file": filename,
                    }
                )
        if isinstance(node, ast.While):
            test_names = _names_in(node.test)
            if test_names & ROUND_HINTS or "stop" in " ".join(test_names):
                inner_fors = [c for c in ast.walk(node) if isinstance(c, ast.For)]
                if any(_for_kind(c) == "participant" for c in inner_fors) and _has_delib_call(
                    node.body
                ):
                    hits.append(
                        {
                            "kind": "while-round-loop",
                            "lineno": node.lineno,
                            "file": filename,
                        }
                    )
    return {
        "file": filename,
        "hits": hits,
        "has_deliberation_loop": bool(hits),
    }


def scan_path(path: Path) -> dict:
    src = path.read_text(encoding="utf-8")
    return scan_source(src, filename=str(path))


def scan_tree(root: Path) -> dict:
    files = sorted(p for p in root.rglob("*.py") if p.is_file())
    reports = [scan_path(p) for p in files]
    hits = [h for r in reports for h in r["hits"]]
    return {
        "root": str(root),
        "files_scanned": [r["file"] for r in reports],
        "file_count": len(reports),
        "hits": hits,
        "has_deliberation_loop": bool(hits),
    }
