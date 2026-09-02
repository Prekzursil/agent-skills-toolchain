#!/usr/bin/env python3
"""Probe 2: independent --version capture + no-silent-fallback reviewer.

Signal (2) of the catalog evidence requirement: each interpreter's own
``--version`` string captured separately and parsed by a different function.
Disagreement fails this probe (parser defect). Also hides python3 from PATH
and asserts MISSING rather than falling back.
"""
from __future__ import annotations

import ast
import os
import stat
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PLUGIN = REPO / "tools" / "plugin"
SRC = PLUGIN / "interpreter_probe.py"
sys.path.insert(0, str(PLUGIN))
import interpreter_probe as ip  # noqa: E402


def _write_fake(directory: Path, name: str, banner: str) -> Path:
    path = directory / name
    path.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then\n'
        f"  printf '%s\\n' '{banner}'\n"
        "  exit 0\n"
        "fi\n"
        "exit 2\n",
        encoding="utf-8",
        newline="\n",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def _source_forbids_alias_lists() -> list[str]:
    """AST-scan: which_all / candidate_names must not iterate alias tables."""
    source = SRC.read_text(encoding="utf-8")
    tree = ast.parse(source)
    which = None
    cand = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "which_all":
            which = node
        if isinstance(node, ast.FunctionDef) and node.name == "candidate_names":
            cand = node
    problems: list[str] = []
    if which is None or cand is None:
        return ["missing which_all or candidate_names"]

    def body_source(fn: ast.FunctionDef) -> str:
        # Skip the docstring; only the executable body is load-bearing.
        body = list(fn.body)
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            body = body[1:]
        chunks = []
        for stmt in body:
            chunk = ast.get_source_segment(source, stmt)
            if chunk:
                chunks.append(chunk)
        return "\n".join(chunks)

    which_src = body_source(which)
    cand_src = body_source(cand)
    if "NEVER_SUBSTITUTE" in which_src:
        problems.append("which_all consults NEVER_SUBSTITUTE (would search aliases)")
    if "NEVER_SUBSTITUTE" in cand_src:
        problems.append("candidate_names consults NEVER_SUBSTITUTE")
    for alias in ("nodejs", "powershell"):
        if alias in which_src:
            problems.append(f"which_all mentions {alias}")
    return problems


def main() -> int:
    decls = ip.load_declarations()
    fail = False
    compared = 0
    for raw in decls["interpreters"]:
        decl = ip._normalize_decl(raw)
        matches = ip.which_all(decl["name"])
        if not matches:
            print(
                f"indep {decl['name']} capture=ABSENT verdict-check=MISSING "
                f"(independent which_all also empty; no fallback binary used)"
            )
            continue
        binary = matches[0]
        raw_indep = ip.capture_version_independent(binary, decl["version_argv"])
        probe_v = ip.parse_version_probe(raw_indep)
        indep_v = ip.parse_version_independent(raw_indep)
        agree = probe_v == indep_v
        compared += 1
        print(
            f"indep {decl['name']} path={binary} banner={raw_indep!r} "
            f"probe={probe_v} independent={indep_v} agree={agree}"
        )
        if not agree or probe_v is None:
            print(f"FAILED:IMP-0016-probe2 parser disagreement on {decl['name']}")
            fail = True

    ast_problems = _source_forbids_alias_lists()
    if ast_problems:
        print(f"FAILED:IMP-0016-probe2 alias-scan {ast_problems}")
        fail = True
    else:
        print("alias-scan which_all_and_candidate_names_clean=True")

    # Live negative control: hide python3, leave a floor-meeting `python`.
    with tempfile.TemporaryDirectory() as tmp:
        decoys = Path(tmp) / "decoys"
        decoys.mkdir()
        _write_fake(decoys, "python", "Python 3.12.0")
        _write_fake(decoys, "python3.12", "Python 3.12.0")
        row = ip.probe_one(
            ip._normalize_decl(
                {"id": "python3", "name": "python3", "floor": "3.11.0"}
            ),
            str(decoys),
        )
        print(
            f"negative-control hide-python3 verdict={row['verdict']} "
            f"path={row['resolved_path']} silent_fallback={row['silent_fallback']}"
        )
        if row["verdict"] != "MISSING" or row["silent_fallback"] or row["resolved_path"]:
            print("FAILED:IMP-0016-probe2 hidden python3 fell back")
            fail = True

    if compared < 1:
        print("FAILED:IMP-0016-probe2 no live interpreter produced a --version banner")
        fail = True

    if fail:
        print("FAILED:IMP-0016-probe2 independent version + no-fallback")
        return 1
    print(
        f"compared={compared} silent_fallback=False "
        f"declaration_source={decls.get('declaration_source')}"
    )
    print("SUCCESS:IMP-0016-probe2 independent --version parse and no silent fallback")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
