#!/usr/bin/env python
"""tms.py - CLI for the Truth-Maintenance justification graph (see tms_core).

Commands:
  assert  <id> --statement <s> --kind <k> [--premises a,b] [--source <path>]
  retract <id>                 mark a belief OUT and cascade to all dependents
  explain <id> [--json]        the justification chain + why IN/OUT
  trace   <id> [--json]        full dependency closure (premises up, dependents down)
  status  [--out-only] [--json]
  recheck                      re-hash all source artifacts; OUT any that drifted

DB: ~/.claude/tms/beliefs.db (override with TMS_DB). Deterministic and fast.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tms_core as tms  # noqa: E402


def _mark(status: str) -> str:
    return "IN " if status == tms.STATUS_IN else "OUT"


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #
def cmd_assert(a: argparse.Namespace) -> int:
    conn = tms.connect()
    prem = [p.strip() for p in (a.premises or "").split(",") if p.strip()]
    try:
        existed = tms.assert_node(conn, a.id, a.statement, a.kind, prem, a.source)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    node = tms.get_node(conn, a.id)
    verb = "updated" if existed else "asserted"
    print(f"{verb} [{_mark(node['status'])}] {a.id}  (kind={a.kind})")
    if prem:
        print(f"  premises: {', '.join(prem)}")
    if a.source:
        print(f"  source:   {a.source}  sha={ (node['source_sha'] or 'MISSING')[:12] }")
    print(f"  reason:   {node['reason']}")
    return 0


def cmd_retract(a: argparse.Namespace) -> int:
    conn = tms.connect()
    try:
        flips = tms.retract_node(conn, a.id)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"retracted {a.id} -> OUT")
    cascaded = sorted(n for n in flips if n != a.id)
    if cascaded:
        print(f"  cascade OUT ({len(cascaded)}): {', '.join(cascaded)}")
    else:
        print("  no dependents to cascade")
    return 0


def cmd_explain(a: argparse.Namespace) -> int:
    conn = tms.connect()
    node = tms.get_node(conn, a.id)
    if not node:
        print(f"error: no such node: {a.id}", file=sys.stderr)
        return 1
    prem = tms.get_premises(conn, a.id)
    deps = tms.get_dependents(conn, a.id)
    causes = tms.root_causes(conn, a.id)
    if a.json:
        prem_rows = [{"id": p, "status": (tms.get_node(conn, p) or {}).get("status")} for p in prem]
        print(json.dumps({
            "id": node["id"], "status": node["status"], "kind": node["kind"],
            "statement": node["statement"], "reason": node["reason"],
            "premises": prem_rows, "dependents": deps,
            "root_causes": [{"id": c, "why": w} for c, w in causes],
        }, indent=2))
        return 0
    print(f"[{_mark(node['status'])}] {node['id']}  (kind={node['kind']})")
    print(f"  statement: {node['statement']}")
    print(f"  why:       {node['reason']}")
    if node["source_artifact"]:
        print(f"  source:    {node['source_artifact']}"
              + ("  [DRIFTED]" if node["source_drift"] else ""))
    print("  premises:")
    if prem:
        for p in prem:
            pn = tms.get_node(conn, p)
            print(f"    [{_mark(pn['status'])}] {p}")
    else:
        print("    (none - this is a base assumption)")
    if node["status"] == tms.STATUS_OUT and causes:
        print("  root cause(s) of OUT:")
        for cid, why in causes:
            tag = "(this node)" if cid == node["id"] else ""
            print(f"    {cid} - {why} {tag}".rstrip())
    return 0


def _print_tree(conn, nid, edges_fn, seen, depth, max_depth=12) -> None:
    for child in edges_fn(conn, nid):
        cn = tms.get_node(conn, child)
        loop = child in seen
        print(f"    {'  ' * depth}[{_mark(cn['status'])}] {child}" + ("  (cycle)" if loop else ""))
        if not loop and depth < max_depth:
            _print_tree(conn, child, edges_fn, seen | {child}, depth + 1, max_depth)


def cmd_trace(a: argparse.Namespace) -> int:
    conn = tms.connect()
    node = tms.get_node(conn, a.id)
    if not node:
        print(f"error: no such node: {a.id}", file=sys.stderr)
        return 1
    if a.json:
        print(json.dumps({
            "id": a.id, "status": node["status"],
            "ancestors": sorted(tms.ancestors(conn, a.id)),
            "descendants": sorted(tms.descendants(conn, a.id)),
        }, indent=2))
        return 0
    print(f"trace [{_mark(node['status'])}] {a.id}  (full dependency closure)")
    print("  depends on (premises, upward):")
    if tms.get_premises(conn, a.id):
        _print_tree(conn, a.id, tms.get_premises, {a.id}, 0)
    else:
        print("    (none)")
    print("  depended on by (dependents / blast radius, downward):")
    if tms.get_dependents(conn, a.id):
        _print_tree(conn, a.id, tms.get_dependents, {a.id}, 0)
    else:
        print("    (none)")
    return 0


def cmd_status(a: argparse.Namespace) -> int:
    conn = tms.connect()
    nodes = tms.all_nodes(conn, out_only=a.out_only)
    if a.json:
        print(json.dumps(nodes, indent=2))
        return 0
    if not nodes:
        print("(no beliefs)" if not a.out_only else "(no OUT beliefs)")
        return 0
    width = max(len(n["id"]) for n in nodes)
    for n in nodes:
        print(f"[{_mark(n['status'])}] {n['id']:<{width}}  {n['kind']:<8}  {n['reason']}")
    return 0


def cmd_recheck(a: argparse.Namespace) -> int:
    conn = tms.connect()
    drift, flips = tms.recheck(conn)
    if not drift:
        print("recheck: all source artifacts unchanged")
    else:
        for nid, drifted in sorted(drift.items()):
            print(f"recheck: {nid} -> {'DRIFTED (OUT)' if drifted else 'restored'}")
    cascaded = sorted(n for n, (old, new) in flips.items() if new == tms.STATUS_OUT)
    if cascaded:
        print(f"  now OUT ({len(cascaded)}): {', '.join(cascaded)}")
    return 0


# --------------------------------------------------------------------------- #
# arg parsing
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="tms.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("assert", help="create/refresh a belief")
    p.add_argument("id")
    p.add_argument("--statement", required=True)
    p.add_argument("--kind", required=True, choices=list(tms.KINDS))
    p.add_argument("--premises", default="", help="comma-separated premise ids")
    p.add_argument("--source", default=None, help="path to the source artifact")
    p.set_defaults(func=cmd_assert)

    p = sub.add_parser("retract", help="mark a belief OUT and cascade")
    p.add_argument("id")
    p.set_defaults(func=cmd_retract)

    p = sub.add_parser("explain", help="justification chain + why IN/OUT")
    p.add_argument("id")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_explain)

    p = sub.add_parser("trace", help="full dependency closure")
    p.add_argument("id")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_trace)

    p = sub.add_parser("status", help="list beliefs")
    p.add_argument("--out-only", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("recheck", help="re-hash sources; OUT any that drifted")
    p.set_defaults(func=cmd_recheck)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
