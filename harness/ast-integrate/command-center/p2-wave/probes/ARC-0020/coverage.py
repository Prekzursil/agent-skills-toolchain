"""AST path-coverage of client.py execute sinks versus the verification choke."""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CLIENT = HERE / "client.py"
SINK = "execute_package_content"
CHOKE = "verify_package"
AFTER = "_after_choke"
FORBIDDEN = frozenset(
    {
        "fetch_public",
        "install_from_public",
        "resolve_extra_index",
        "npm_fallback",
        "pypi_fallback",
    }
)
MUTANT_TAIL = (
    "\n\ndef smuggle_unsigned(package):\n"
    "    return execute_package_content(package['content_bytes'])\n"
)


def _call_name(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _call_linenos(fn: ast.FunctionDef, name: str) -> list[int]:
    out: list[int] = []
    for node in ast.walk(fn):
        if _call_name(node) == name:
            out.append(int(getattr(node, "lineno", 0)))
    return out


def _tuple_strs(node: ast.AST) -> list[str] | None:
    if not isinstance(node, ast.Tuple):
        return None
    vals: list[str] = []
    for elt in node.elts:
        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
            vals.append(elt.value)
        else:
            return None
    return vals


def analyze_source(source: str) -> dict[str, Any]:
    tree = ast.parse(source)
    funcs = {
        n.name: n
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef)
    }
    public_paths: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "PUBLIC_EXECUTE_PATHS":
                    vals = _tuple_strs(node.value)
                    if vals is not None:
                        public_paths = vals
    forbidden_hits = 0
    for node in ast.walk(tree):
        name = _call_name(node)
        if name in FORBIDDEN:
            forbidden_hits += 1
        if isinstance(node, ast.FunctionDef) and node.name in FORBIDDEN:
            forbidden_hits += 1

    sink_callers = [
        name for name, fn in funcs.items() if _call_linenos(fn, SINK)
    ]
    choke_before_sink = False
    if sink_callers == [AFTER] and AFTER in funcs:
        choke_lines = _call_linenos(funcs[AFTER], CHOKE)
        sink_lines = _call_linenos(funcs[AFTER], SINK)
        choke_before_sink = bool(choke_lines) and bool(sink_lines) and min(choke_lines) < min(sink_lines)

    missing_public: list[str] = []
    public_cross: list[str] = []
    for name in public_paths:
        fn = funcs.get(name)
        if fn is None:
            missing_public.append(name)
            continue
        if _call_linenos(fn, AFTER) and not _call_linenos(fn, SINK):
            public_cross.append(name)
        else:
            missing_public.append(name)

    all_cross = (
        choke_before_sink
        and not missing_public
        and len(public_paths) >= 2
        and len(sink_callers) == 1
        and forbidden_hits == 0
    )
    return {
        "computed_not_asserted": True,
        "method": "ast.parse(client.py); sink callers, choke lineno, PUBLIC_EXECUTE_PATHS",
        "public_paths": public_paths,
        "public_path_count": len(public_paths),
        "public_paths_crossing_choke": public_cross,
        "missing_public": missing_public,
        "sink_callers": sink_callers,
        "sink_caller_count": len(sink_callers),
        "choke_before_sink": choke_before_sink,
        "forbidden_hits": forbidden_hits,
        "all_execute_paths_cross_choke": all_cross,
    }


def analyze_client(path: Path | None = None) -> dict[str, Any]:
    target = path or CLIENT
    return analyze_source(target.read_text(encoding="utf-8"))


def mutant_report() -> dict[str, Any]:
    src = CLIENT.read_text(encoding="utf-8") + MUTANT_TAIL
    return analyze_source(src)


def both_states() -> dict[str, Any]:
    live = analyze_client()
    mutant = mutant_report()
    return {
        "live_ok": live.get("all_execute_paths_cross_choke") is True,
        "mutant_ok": mutant.get("all_execute_paths_cross_choke") is True,
        "live": live,
        "mutant_sink_callers": mutant.get("sink_callers"),
        "both_states_pass": (
            live.get("all_execute_paths_cross_choke") is True
            and mutant.get("all_execute_paths_cross_choke") is not True
        ),
    }
