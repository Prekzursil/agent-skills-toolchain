#!/usr/bin/env python3
"""Rank per-server context cost by what the fleet ACTUALLY PAYS, and net out dead surface.

TWO COSTS, NOT ONE.  This client defers MCP tool schemas: the system prompt carries tool
NAMES, and a schema is materialised only when the model selects that tool.  So

    RESIDENT   = ``name_bytes``    paid on EVERY request, for every mounted server, forever
    CONTINGENT = ``schema_bytes``  paid only when a schema is actually pulled in

Ranking by ``schema_bytes`` is the obvious move and it ranks by a cost the fleet mostly does
NOT pay.  Measured here: contingent is ~52x resident fleet-wide, and the two bases disagree
about the ordering for most rows -- so the choice of basis is load-bearing, not decorative.
``C1`` asserts exactly that, because if the two orderings agreed this whole file would be
ceremony and should say so instead of implying it found something.

THE ADJUSTED COLUMN.  ``resident_bytes_over_dead_backends`` is the part of the every-turn
cost that buys tools which cannot run -- attributed per tool via ``backend_map``, never
pro-rated.  ``name_bytes`` is defined upstream as ``sum(len(n) for n in tool_names)``, a
plain sum, so the attribution reconciles EXACTLY against the committed field rather than
approximately: ``C3`` fails closed unless the buckets re-sum to the number that shipped.
That is the difference between a control that checks the claim and one that only proves the
file was readable.

SCOPE, inline: 16 of 23 rows have a sampled tool surface at all.  The other 7 are HTTP
transports with no stdio child, so their cost is NOT MEASURED -- never zero.  They are
excluded from the ranking and counted in the header, not silently dropped.

Deterministic: committed inputs only, sorted output, ``newline="\\n"``.  Spawns nothing.

Run::

    python cost_rank.py -o cost-rank.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import backend_map  # noqa: E402
import s4_evidence  # noqa: E402

MATRIX = "capability-matrix-r2.json"
BYTES_PER_TOKEN = 4.0  # rough, and labelled rough at every use

BASIS_LEGEND = {
    "resident_bytes": (
        "name_bytes -- the tool NAMES, carried on every request for every mounted "
        "server. This is the cost the fleet actually pays per turn under a deferred-"
        "schema client, and the basis this table ranks by."
    ),
    "contingent_bytes": (
        "schema_bytes -- the full tool schemas, paid only when a schema is materialised. "
        "Large but mostly unpaid here; ranking by it ranks by a cost the fleet does not "
        "incur. Kept visible so the choice of basis stays auditable."
    ),
    "resident_bytes_over_dead_backends": (
        "the slice of resident cost buying tools whose BACKEND was measured "
        "non-functional. Attributed per tool via backend_map (exact, not pro-rated) and "
        "reconciled against the committed name_bytes by C3. Null where no tool->backend "
        "map exists -- null means NOT ATTRIBUTED, never zero."
    ),
    "not_measured": (
        "a server with no sampled tool surface (HTTP transport, no stdio child to "
        "spawn). Excluded from the ranking and counted in the header. Not zero."
    ),
}


def build(base: pathlib.Path) -> dict[str, Any]:
    matrix = json.loads((base / MATRIX).read_text(encoding="utf-8"))
    ev = s4_evidence.load(base)
    all_rows = matrix.get("rows") or []
    measured = [r for r in all_rows if r.get("tool_count") and r.get("name_bytes")]
    if not measured:
        raise SystemExit(
            "FAILED:cost-rank zero measurable rows -- refusing to publish a ranking "
            "over nothing (fail closed)"
        )

    tot_name = sum(r["name_bytes"] for r in measured)
    tot_schema = sum(r["schema_bytes"] for r in measured)
    tot_tools = sum(r["tool_count"] for r in measured)

    by_resident = sorted(measured, key=lambda r: (-r["name_bytes"], r["name"]))
    by_contingent = sorted(measured, key=lambda r: (-r["schema_bytes"], r["name"]))
    contingent_rank = {r["name"]: i for i, r in enumerate(by_contingent)}

    rows: list[dict[str, Any]] = []
    moved = 0
    reconciled: list[str] = []
    for i, r in enumerate(by_resident):
        name = r["name"]
        dead_bytes: int | None = None
        dead_tools: int | None = None
        note = (
            "NOT ATTRIBUTED: no tool->backend map exists for this server, so its "
            "resident cost cannot be split across backends"
        )
        if name == backend_map.PROXY_SERVER:
            names = r.get("tool_names") or []
            buckets, unclassified = backend_map.bucket(names)
            if unclassified:
                raise SystemExit(
                    f"FAILED:cost-rank {len(unclassified)} {name} tool(s) unclassified "
                    "-- the adjusted column would under-report"
                )
            # C3: the buckets must re-sum EXACTLY to the committed name_bytes.  A
            # reconciliation against the shipped number is what makes this an attribution
            # rather than an estimate that happens to look plausible.
            bucket_sum = sum(len(t) for tools in buckets.values() for t in tools)
            if bucket_sum != r["name_bytes"]:
                raise SystemExit(
                    f"FAILED:cost-rank {name} bucket bytes {bucket_sum} != committed "
                    f"name_bytes {r['name_bytes']} -- attribution does not reconcile"
                )
            reconciled.append(name)
            dead = set(ev.dead_backends(name))
            dead_bytes = sum(
                len(t) for b, tools in buckets.items() if b in dead for t in tools
            )
            dead_tools = sum(len(tools) for b, tools in buckets.items() if b in dead)
            unprobed = ev.unprobed_backends(name)
            note = (
                f"{dead_tools}/{r['tool_count']} tools over {len(dead)} backend(s) "
                f"measured non-functional"
                + (f"; {len(unprobed)} backend(s) UNMEASURED" if unprobed else "")
            )

        delta = contingent_rank[name] - i
        moved += 1 if delta else 0
        rows.append(
            {
                "name": name,
                "resident_rank": i,
                "contingent_rank": contingent_rank[name],
                "rank_delta": delta,
                "tool_count": r["tool_count"],
                "resident_bytes": r["name_bytes"],
                "resident_share_pct": round(100.0 * r["name_bytes"] / tot_name, 1),
                "contingent_bytes": r["schema_bytes"],
                "resident_bytes_over_dead_backends": dead_bytes,
                "tools_over_dead_backends": dead_tools,
                "dead_surface_note": note,
            }
        )

    # C1: if the two bases produced the SAME ordering the distinction would be decorative.
    if not moved:
        raise SystemExit(
            "FAILED:cost-rank the resident and contingent orderings are identical -- "
            "the two-basis split would be decorative; say so rather than imply a finding"
        )
    # C4: an adjusted slice can never exceed the whole it is a slice of.
    for row in rows:
        adj = row["resident_bytes_over_dead_backends"]
        if adj is not None and adj > row["resident_bytes"]:
            raise SystemExit(
                f"FAILED:cost-rank {row['name']} adjusted {adj} > resident "
                f"{row['resident_bytes']}"
            )

    top = rows[0]
    dead_top = top["resident_bytes_over_dead_backends"]
    return {
        "report": "mcp-cost-rank",
        "generated_utc_date": "2026-08-13",
        "token_basis": BASIS_LEGEND,
        "regime": (
            "deferred-schema client: tool NAMES are resident, schemas are pulled on "
            "selection. Under an eager client the contingent column becomes the resident "
            "one and this ranking inverts -- the basis is a property of the CLIENT, not "
            "of the servers, so it is stated rather than assumed."
        ),
        "fleet": {
            "servers_ranked": len(measured),
            "servers_total": len(all_rows),
            "servers_not_measured": len(all_rows) - len(measured),
            "tools": tot_tools,
            "resident_bytes": tot_name,
            "contingent_bytes": tot_schema,
            "contingent_over_resident": round(tot_schema / tot_name, 1),
            "resident_tokens_rough": round(tot_name / BYTES_PER_TOKEN),
            "contingent_tokens_rough": round(tot_schema / BYTES_PER_TOKEN),
        },
        "headline": (
            f"{top['name']} is {top['resident_share_pct']}% of every-turn resident MCP "
            f"cost"
            + (
                f", and {dead_top:,} B of that ({round(100.0 * dead_top / top['resident_bytes'], 1)}%"
                f" of the row, ~{round(dead_top / BYTES_PER_TOKEN):,} tokens on EVERY "
                f"request, rough) buys tools whose backend was measured non-functional"
                if dead_top
                else ""
            )
        ),
        "controls": {
            "C1_rank_movement": (
                f"{moved}/{len(rows)} rows change rank between the two bases -- the "
                "basis choice is load-bearing, not decorative"
            ),
            "C2_fail_closed": "a run with zero measurable rows raises instead of publishing",
            "C3_reconciliation": (
                f"per-tool attribution re-sums EXACTLY to the committed name_bytes for "
                f"{reconciled or 'no rows'} -- an estimate that cannot be checked is not "
                "an attribution"
            ),
            "C4_slice_bound": "no adjusted slice may exceed its own row's resident bytes",
        },
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default=str(HERE))
    ap.add_argument("-o", "--out", default="")
    args = ap.parse_args(argv)

    payload = build(pathlib.Path(args.base))
    f = payload["fleet"]
    print(
        f"  fleet: {f['servers_ranked']}/{f['servers_total']} rows ranked "
        f"({f['servers_not_measured']} not measured), {f['tools']:,} tools"
    )
    print(
        f"  RESIDENT {f['resident_bytes']:,} B (~{f['resident_tokens_rough']:,} tok/turn, rough) | "
        f"CONTINGENT {f['contingent_bytes']:,} B | {f['contingent_over_resident']}x"
    )
    print(
        f"  {'server':<22} {'tools':>5} {'RESIDENT':>9} {'share':>7} {'DEAD-BACKEND B':>15} {'move':>6}"
    )
    print(f"  {'-' * 22} {'-' * 5} {'-' * 9} {'-' * 7} {'-' * 15} {'-' * 6}")
    for r in payload["rows"]:
        adj = r["resident_bytes_over_dead_backends"]
        adj_txt = f"{adj:,}" if adj is not None else "--"
        delta = r["rank_delta"]
        move = "same" if delta == 0 else f"{delta:+d}"
        print(
            f"  {r['name']:<22} {r['tool_count']:>5} {r['resident_bytes']:>9,} "
            f"{r['resident_share_pct']:>6.1f}% {adj_txt:>15} {move:>6}"
        )
    for k, v in payload["controls"].items():
        print(f"  ok  {k}: {v}")
    print(f"\n  HEADLINE: {payload['headline']}")

    if args.out:
        pathlib.Path(args.out).write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        print(f"wrote {args.out}")
    print(
        f"SUCCESS:cost-rank resident={f['resident_bytes']:,}B contingent="
        f"{f['contingent_bytes']:,}B over {f['servers_ranked']} ranked rows"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
