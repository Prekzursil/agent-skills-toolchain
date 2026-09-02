#!/usr/bin/env python3
"""Probe 2: this slice has zero deliberation logic (AST); a planted loop fails.

Live scan covers tools/blueprint_library/*.py. The instrument itself lives in
this probe file so `for node in ast.walk` is not mistaken for council logic.
"""
from __future__ import annotations

import ast
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SLICE = REPO / "tools" / "blueprint_library"

DELIB_FN = re.compile(
    r"(deliberat|tally_vote|count_ballot|majority_vote|consensus_round|"
    r"mediate_round|negotiate_turn|collect_vote)",
    re.I,
)
DELIB_BIND = re.compile(
    r"(^|_)(round|votes|vote|ballot|ballots|jurors|speakers|turns|"
    r"deliberation|consensus)(_|$)",
    re.I,
)
# Also match those tokens as whole names (iterables named `votes`, `ballots`).
DELIB_TOKEN = re.compile(
    r"\b(round|votes|vote|ballot|ballots|jurors|speakers|turns|"
    r"deliberation|consensus)\b",
    re.I,
)


def _expr(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_expr(node.value)}.{node.attr}"
    if isinstance(node, ast.Tuple):
        return ",".join(_expr(elt) for elt in node.elts)
    try:
        return ast.unparse(node)
    except Exception:
        return type(node).__name__


def scan_tree(tree: ast.AST, origin: str) -> list[str]:
    findings: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.While):
            findings.append(f"{origin}:while:{getattr(node, 'lineno', 0)}")
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if DELIB_FN.search(node.name) or DELIB_TOKEN.fullmatch(node.name or ""):
                findings.append(
                    f"{origin}:fn:{node.name}:{getattr(node, 'lineno', 0)}"
                )
        if isinstance(node, ast.For):
            target = _expr(node.target)
            it = _expr(node.iter)
            if DELIB_TOKEN.search(target) or DELIB_TOKEN.search(it):
                findings.append(
                    f"{origin}:for:{target} in {it}:{getattr(node, 'lineno', 0)}"
                )
        if isinstance(node, ast.comprehension):
            target = _expr(node.target)
            it = _expr(node.iter)
            if DELIB_TOKEN.search(target) or DELIB_TOKEN.search(it):
                findings.append(
                    f"{origin}:comp:{target} in {it}:{getattr(node, 'lineno', 0)}"
                )
    return findings


def scan_source(text: str, origin: str) -> list[str]:
    return scan_tree(ast.parse(text), origin)


def scan_slice(root: Path) -> dict[str, list[str]]:
    by_file: dict[str, list[str]] = {}
    for path in sorted(root.glob("*.py")):
        rel = path.relative_to(REPO).as_posix()
        hits = scan_source(path.read_text(encoding="utf-8"), rel)
        if hits:
            by_file[rel] = hits
    return by_file


PLANTED = '''
def collect_vote(ballots):
    consensus = False
    for round in range(3):
        votes = ballots
        while not consensus:
            for ballot in votes:
                consensus = True
    return consensus
'''


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0256-probe2 {msg}")
    return 1


def main() -> int:
    live = scan_slice(SLICE)
    print(f"live_files={len(list(SLICE.glob('*.py')))} live_findings={live}")
    if live:
        return fail(f"deliberation AST hits on live slice: {live}")

    planted_hits = scan_source(PLANTED, "planted-loop")
    print(f"planted_hits={planted_hits}")
    if not planted_hits:
        return fail("planted deliberation loop was silent (detector dead)")

    compiler = SLICE / "compiler.py"
    mutated = compiler.read_text(encoding="utf-8") + "\n" + PLANTED
    with tempfile.TemporaryDirectory(prefix="imp0256-plant-") as tmp:
        plant_path = Path(tmp) / "compiler_planted.py"
        plant_path.write_text(mutated, encoding="utf-8")
        plant_hits = scan_source(plant_path.read_text(encoding="utf-8"), plant_path.name)
    print(f"mutant_compiler_hits={plant_hits}")
    if not plant_hits:
        return fail("planted loop grafted onto compiler.py was accepted")

    clean = scan_source(compiler.read_text(encoding="utf-8"), "compiler.py")
    if clean:
        return fail(f"compiler.py itself is dirty: {clean}")

    print(
        "both-states: live_silent=True planted_fires=True "
        f"planted_n={len(planted_hits)} mutant_n={len(plant_hits)}"
    )
    print("SUCCESS:IMP-0256-probe2 AST boundary zero-deliberation; planted loop fails")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
