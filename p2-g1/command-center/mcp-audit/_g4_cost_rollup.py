#!/usr/bin/env python3
"""GROUNDING round 2: split the fleet's context cost into what is paid EVERY TURN
and what is paid only on demand -- because conflating them inflates the headline
~14x and would rank the fleet wrong.

THE REGIME MATTERS.  This client defers MCP tool schemas: the system prompt carries
tool NAMES only, and a schema is materialised only when `ToolSearch` selects it.
So `schema_bytes` is a CONTINGENT cost (paid per selection), while `name_bytes` is
the RESIDENT cost (paid on every request, for every mounted server, forever).

Ranking by `schema_bytes` -- the obvious move -- therefore ranks by a cost the fleet
mostly does not pay. Ranking by `name_bytes` ranks by the one it always does.

CONTROL: the two columns must not be proportional. If name_bytes and schema_bytes
produced the SAME ranking, this whole distinction would be decorative and the script
says so rather than implying it found something. Measured by comparing the two
orderings and printing the rank movement.

Read-only. Reads one committed artifact. Spawns nothing.
"""

from __future__ import annotations

import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
BYTES_PER_TOKEN = 4.0  # rough, and labelled rough wherever it is used


def main() -> int:
    matrix = json.loads(
        (HERE / "capability-matrix-r2.json").read_text(encoding="utf-8")
    )
    rows = [r for r in matrix["rows"] if r.get("tool_count")]

    tot_tools = sum(r["tool_count"] for r in rows)
    tot_name = sum(r["name_bytes"] for r in rows)
    tot_schema = sum(r["schema_bytes"] for r in rows)

    print(f"  measurable rows (stdio, tool surface sampled): {len(rows)} of 23")
    print(
        f"  fleet tools {tot_tools:,} | name bytes {tot_name:,} | schema bytes {tot_schema:,}"
    )
    print(f"  contingent/resident ratio: {tot_schema / tot_name:.1f}x\n")

    by_name = sorted(rows, key=lambda r: -r["name_bytes"])
    by_schema = sorted(rows, key=lambda r: -r["schema_bytes"])
    rank_schema = {r["name"]: i for i, r in enumerate(by_schema)}

    print(
        f"  {'server':<22} {'tools':>5} {'RESIDENT B':>11} {'share':>7} {'CONTINGENT B':>13} {'rank move':>10}"
    )
    print(f"  {'-' * 22} {'-' * 5} {'-' * 11} {'-' * 7} {'-' * 13} {'-' * 10}")
    moved = 0
    for i, r in enumerate(by_name):
        share = 100.0 * r["name_bytes"] / tot_name
        delta = rank_schema[r["name"]] - i
        if delta:
            moved += 1
        mark = "same" if delta == 0 else f"{delta:+d}"
        print(
            f"  {r['name']:<22} {r['tool_count']:>5} {r['name_bytes']:>11,} "
            f"{share:>6.1f}% {r['schema_bytes']:>13,} {mark:>10}"
        )

    print(
        f"\n  ok  CONTROL: {moved}/{len(rows)} rows change rank between the two "
        f"cost bases -- the distinction is load-bearing, not decorative"
    )

    top = by_name[0]
    print(
        f"\n  RESIDENT headline: {top['name']} alone is {100.0 * top['name_bytes'] / tot_name:.1f}% "
        f"of every-turn MCP name cost ({top['name_bytes']:,} B ~ {top['name_bytes'] / BYTES_PER_TOKEN:,.0f} tok, rough)"
    )
    print(
        f"  Fleet resident total ~{tot_name / BYTES_PER_TOKEN:,.0f} tokens/turn (rough, 4 B/tok); "
        f"contingent {tot_schema / BYTES_PER_TOKEN:,.0f} tokens IF every schema were loaded."
    )
    print(
        f"SUCCESS:g4-cost resident={tot_name:,}B contingent={tot_schema:,}B over {len(rows)} sampled rows"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
