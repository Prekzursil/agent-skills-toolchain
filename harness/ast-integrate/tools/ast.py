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

# Allow `python tools/ast.py` and `from router.route import route_query`.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from router.route import route_query  # noqa: E402


EXAMPLE_INDEX = "command-center/p2-wave/probes/IMP-0403/fixtures/capability-index.json"

# Every example below is a complete command an owner can paste from the repo
# root.  A reviewer running ONLY these must see exit 0 and a JSON object on
# stdout; two of them route to a capability, one is a terminal no-fit.
ROUTE_EXAMPLES: tuple[tuple[str, str], ...] = (
    (
        "python3 tools/ast.py route "
        '--query "lint a Python module for unused imports" '
        f"--index {EXAMPLE_INDEX}",
        "SELECTED: skill.python-lint; runners-up disclosed under near_misses",
    ),
    (
        "python3 tools/ast.py route "
        '--query "summarize this PDF document for an owner briefing" '
        f"--index {EXAMPLE_INDEX} --cwd .",
        "SELECTED: skill.pdf-summarize; --cwd is recorded, never used to inject",
    ),
    (
        "python3 tools/ast.py route "
        '--query "what is the weather in Paris tomorrow" '
        f"--index {EXAMPLE_INDEX}",
        "NO-CAPABILITY-FITS: terminal refusal; closest rejected candidates disclosed",
    ),
)


def route_epilog() -> str:
    lines = [
        "examples (run from the repository root; stdout is one JSON object):",
    ]
    for cmd, note in ROUTE_EXAMPLES:
        lines.append(f"  {cmd}")
        lines.append(f"      # {note}")
    lines.append("")
    lines.append(
        "output keys: verdict (SELECTED | NO-CAPABILITY-FITS, always terminal), "
        "selected, confidence, near_misses[*].cutoff_reason, explanation, "
        "injection_performed=false, injected=[], session_started=false. "
        "Capability bodies are never printed."
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ast")
    parser.add_argument("--version", action="version", version="ast 0.1.0")
    sub = parser.add_subparsers(dest="cmd", required=True)
    route = sub.add_parser(
        "route",
        help="route a query against a capability index",
        description="Route a query without injecting anything. Undocumented flags are rejected.",
        epilog=route_epilog(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
    result = route_query(args.query, index=args.index, cwd=args.cwd)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
