#!/usr/bin/env python3
"""ast CLI. `ast route` is the documented router entrypoint. IMP-0403.

G-1 puts ``tools/`` on PYTHONPATH, so ``import ast`` binds THIS file. Re-export
the stdlib ``ast`` surface (parse/walk/Add/BitAnd/…) so inspect, jsonschema and
TST-0223 mutation probes keep working. CLI entrypoints stay on this module.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import sysconfig
from pathlib import Path


def _reexport_stdlib_ast() -> None:
    stdlib = sysconfig.get_path("stdlib")
    if not stdlib:
        return
    root = Path(stdlib)
    candidates = (root / "ast.py", root / "ast" / "__init__.py")
    path = next((p for p in candidates if p.is_file()), None)
    if path is None:
        return
    spec = importlib.util.spec_from_file_location("_py_stdlib_ast", path)
    if spec is None or spec.loader is None:
        return
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    skip = {"__name__", "__file__", "__package__", "__loader__", "__spec__", "__cached__"}
    for key, val in mod.__dict__.items():
        if key in skip:
            continue
        globals()[key] = val


_reexport_stdlib_ast()

# Allow `python tools/ast.py` to resolve the router import at call time.
# IMP-0333 shard10 repair 2026-10-24: this import was module-level, which made
# `import ast` -> tools/ast.py -> router.route -> dataclasses re-enter a
# partially-initialized dataclasses whenever G-1's PYTHONPATH put tools/ ahead
# of the stdlib and dataclasses initialized before stdlib ast was cached
# (measured: probe2_negative_control subprocess died with ImportError). The
# router import is now lazy; CLI behavior is unchanged because route_query is
# only referenced inside main().
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ast")
    parser.add_argument("--version", action="version", version="ast 0.1.0")
    sub = parser.add_subparsers(dest="cmd", required=True)
    route = sub.add_parser(
        "route",
        help="route a query against a capability index",
        description="Route a query without injecting anything. Undocumented flags are rejected.",
    )
    route.add_argument("--query", required=True, help="natural-language query")
    route.add_argument("--index", default="capability-index.json", help="capability index path")
    route.add_argument("--cwd", default=".", help="working directory")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    if args.cmd != "route":
        parser.error("unknown command")
    from router.route import route_query  # lazy: see the repair note at module top

    result = route_query(args.query, index=args.index, cwd=args.cwd)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
