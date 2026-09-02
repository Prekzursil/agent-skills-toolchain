#!/usr/bin/env python3
"""Named probe 2: imported argv is built through agentspec.argv (AST).

No local argv builder may be introduced in the Codex fan-out adapter.
Both-states: a planted ``build_argv`` snippet is detected; the live adapter is not.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ADAPTER = REPO / "tools" / "import-adapters" / "codex_fanout.py"

LOCAL_ARGV_FN = re.compile(
    r"^(?:build|make|construct|create|local)_?argv$|^argv_(?:build|make|construct)$",
    re.IGNORECASE,
)

PLANTED_LOCAL = """
def build_argv(binary, prompt):
    return [binary, prompt, "--background"]
"""

PLANTED_CANONICAL = """
from agentspec import argv

def import_one(prompt_file, timeout_seconds):
    return argv.build("codex", prompt_file=prompt_file, timeout_seconds=timeout_seconds)
"""


def analyze(src: str) -> dict:
    tree = ast.parse(src)
    imports_argv = False
    calls_build = False
    local_builders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "agentspec.argv" or alias.name == "agentspec":
                    imports_argv = True
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == "agentspec.argv" or mod == "agentspec":
                for alias in node.names:
                    if alias.name in {"argv", "build"}:
                        imports_argv = True
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "build":
                value = func.value
                if isinstance(value, ast.Name) and value.id == "argv":
                    calls_build = True
                if isinstance(value, ast.Attribute) and value.attr == "argv":
                    calls_build = True
            if isinstance(func, ast.Name) and func.id == "build":
                calls_build = True
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if LOCAL_ARGV_FN.match(node.name):
                local_builders.append(node.name)
    return {
        "imports_agentspec_argv": imports_argv,
        "calls_argv_build": calls_build,
        "local_argv_builders": local_builders,
    }


def main() -> int:
    if not ADAPTER.is_file():
        print(f"FAILED:IMP-0161-probe2 adapter missing {ADAPTER}")
        return 1
    src = ADAPTER.read_text(encoding="utf-8")
    live = analyze(src)
    planted_bad = analyze(PLANTED_LOCAL)
    planted_good = analyze(PLANTED_CANONICAL)

    if not planted_bad["local_argv_builders"] or planted_bad["calls_argv_build"]:
        print("FAILED:IMP-0161-probe2 detector silent on planted local argv builder")
        print(json.dumps(planted_bad))
        return 1
    if (
        not planted_good["imports_agentspec_argv"]
        or not planted_good["calls_argv_build"]
        or planted_good["local_argv_builders"]
    ):
        print("FAILED:IMP-0161-probe2 detector rejects canonical argv.build usage")
        print(json.dumps(planted_good))
        return 1
    if not live["imports_agentspec_argv"]:
        print("FAILED:IMP-0161-probe2 adapter does not import agentspec.argv")
        return 1
    if not live["calls_argv_build"]:
        print("FAILED:IMP-0161-probe2 adapter does not call argv.build")
        return 1
    if live["local_argv_builders"]:
        print(
            "FAILED:IMP-0161-probe2 local argv builder introduced: "
            f"{live['local_argv_builders']}"
        )
        return 1
    if "def build_argv" in src or "def make_argv" in src:
        print("FAILED:IMP-0161-probe2 string-level local argv builder")
        return 1

    out = {
        "probe": "probe2-argv-ast",
        "unit_id": "IMP-0161",
        "pass": True,
        "adapter": ADAPTER.relative_to(REPO).as_posix(),
        "live": live,
        "planted_local_detected": True,
        "planted_canonical_accepted": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"imports_argv={live['imports_agentspec_argv']} "
        f"calls_build={live['calls_argv_build']} "
        f"local={live['local_argv_builders']}"
    )
    print("SUCCESS:IMP-0161-probe2 argv via agentspec.argv; no local builder")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
