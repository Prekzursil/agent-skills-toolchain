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

SCOPE, AND WHY IT IS IN THE FIELD NAME.  16 of 23 rows have a sampled tool surface at all.
The other 7 are HTTP transports with no stdio child, so their cost is NOT MEASURED -- never
zero.  They are excluded from the ranking and counted in the header, not silently dropped.

That disclosure was already here, and it was not enough.  An independent audit of round 2
found the share being quoted downstream as "cloud-hub is 60.1% of every-turn resident MCP
cost" and, at its widest, "of the FLEET's every-turn resident MCP cost" -- a claim over 23
servers resting on a denominator of 16.  A share is only meaningful with its denominator,
and a docstring does not travel with a copied number, so the denominator now rides in the
field NAME (``resident_share_pct_of_sampled``) and in the headline STRING, and ``C5`` fails
the run closed if the headline ever loses it.  Publishing a fleet-wide figure instead is not
available: the 7 rows have no tool names anywhere in the repository, so the true fleet
denominator is UNMEASURED, not merely unpublished.

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

# The headline is a module constant so the C5 control can REPLACE it and re-run ``build``.
# Checking a predicate in isolation would prove the predicate works, not that the producer
# enforces it -- and "the control ran" is not the same claim as "the guard is wired".
HEADLINE_TMPL = (
    "{name} is {share}% of the every-turn resident cost of the {n_sampled} SAMPLED "
    "servers -- NOT of the fleet: {n_unsampled} of {n_total} rows have no stdio child to "
    "enumerate, so their names are unmeasured (never zero) and the true fleet share of "
    "this row is strictly lower"
)
# The wording an independent audit REFUTED, verbatim, kept executable so the control fires
# on the real defect instead of on a fixture invented to be caught.
REFUTED_HEADLINE_TMPL = "{name} is {share}% of every-turn resident MCP cost"

# Same reasoning as HEADLINE_TMPL, for the aggregate block C6 guards: these are the module
# constants the producer actually builds its key names from, so the control can replace them
# and re-run ``build`` rather than asserting against a predicate in isolation.
# ``AGG_KEY`` was literally "fleet" through round 3 while holding sampled-only sums.
AGG_KEY = "sampled_aggregate"
AGG_SUFFIX = "_sampled"
REFUTED_AGG_KEY = "fleet"

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
    "resident_share_pct_of_sampled": (
        "this row's share of the resident bytes of the SAMPLED servers only -- the ones "
        "with a stdio child to enumerate. It is NOT a share of the fleet: the unsampled "
        "rows contribute an unknown, non-zero amount to the true denominator, so the real "
        "fleet share of any row is strictly LOWER than this number. The scope is in the "
        "field name on purpose, because a bare percentage gets copied and its footnote "
        "does not."
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
                "resident_share_pct_of_sampled": round(
                    100.0 * r["name_bytes"] / tot_name, 1
                ),
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
    n_sampled, n_total = len(measured), len(all_rows)
    headline = HEADLINE_TMPL.format(
        name=top["name"],
        share=top["resident_share_pct_of_sampled"],
        n_sampled=n_sampled,
        n_unsampled=n_total - n_sampled,
        n_total=n_total,
    ) + (
        f". {dead_top:,} B of the row ({round(100.0 * dead_top / top['resident_bytes'], 1)}%"
        f", ~{round(dead_top / BYTES_PER_TOKEN):,} tokens on EVERY request, rough) buys "
        f"tools whose backend was measured non-functional"
        if dead_top
        else ""
    )
    # C5: a share without its denominator is the defect an audit CONFIRMED against round 2 --
    # the number was quoted downstream as fleet-wide while resting on 16 of 23 rows.  The
    # docstring already disclosed the scope and that did not travel with the copied figure,
    # so the headline must carry both counts or the run fails rather than shipping a
    # percentage that reads wider than its evidence.
    # The tokens are STRUCTURAL phrases, not bare digits: "16" and "23" can appear inside an
    # unrelated byte count and let the check pass for the wrong reason.
    required = (f"{n_sampled} SAMPLED", f"of {n_total} rows")
    if not all(tok in headline for tok in required):
        raise SystemExit(
            f"FAILED:cost-rank headline lost its denominator -- expected {required!r}, a "
            "share stated without its scope is exactly the round-2 overclaim"
        )
    payload = {
        "report": "mcp-cost-rank",
        "generated_utc_date": "2026-08-13",
        "token_basis": BASIS_LEGEND,
        "regime": (
            "deferred-schema client: tool NAMES are resident, schemas are pulled on "
            "selection. Under an eager client the contingent column becomes the resident "
            "one and this ranking inverts -- the basis is a property of the CLIENT, not "
            "of the servers, so it is stated rather than assumed."
        ),
        # Round 3 put the scope into the per-ROW share and left this block named `fleet`,
        # holding sums over the sampled rows only.  A second audit finding: the same
        # denominator defect, one level up.  `707 tools` was then copied into five prose
        # sites as a fleet total -- including round 3's own report, which called it "the
        # fleet total" three sections after fixing the share.  The block name is what a
        # copier sees, so the scope now lives in the name AND in every value key.
        AGG_KEY: {
            "scope": (
                f"SUMS OVER THE SAMPLED ROWS ONLY -- the {len(measured)} of "
                f"{len(all_rows)} mounted servers with a stdio child to enumerate. These "
                f"are NOT fleet totals: the {len(all_rows) - len(measured)} unsampled rows "
                "contribute an unknown, non-zero amount, so every figure here is a LOWER "
                "BOUND on the fleet. The scope is in the block name and in each value key "
                "on purpose -- a bare number gets copied into prose and its footnote does not."
            ),
            "servers_ranked": len(measured),
            "servers_total": len(all_rows),
            "servers_not_measured": len(all_rows) - len(measured),
            f"tools{AGG_SUFFIX}": tot_tools,
            f"resident_bytes{AGG_SUFFIX}": tot_name,
            f"contingent_bytes{AGG_SUFFIX}": tot_schema,
            f"contingent_over_resident{AGG_SUFFIX}": round(tot_schema / tot_name, 1),
            f"resident_tokens_rough{AGG_SUFFIX}": round(tot_name / BYTES_PER_TOKEN),
            f"contingent_tokens_rough{AGG_SUFFIX}": round(tot_schema / BYTES_PER_TOKEN),
        },
        "headline": headline,
        "refuted": {
            "round_2_wording": (
                "cloud-hub is 60.1% of every-turn resident MCP cost -- and, at its widest "
                "in LANE-MCPRESEARCH-GROUNDING.md, 'of the FLEET's every-turn resident MCP "
                "cost'"
            ),
            "why": (
                "the arithmetic was right and the SENTENCE was wider than it: the "
                "denominator is the sampled rows only. Kept here rather than deleted so "
                "the wording that shipped stays auditable"
            ),
            "still_true": (
                "cloud-hub IS the largest resident row by a wide margin, and the "
                "dead-backend slice of it is unchanged. Only the scope of the percentage "
                "moved"
            ),
            "round_3_wording": (
                "the aggregate block was named `fleet` and held `tools: 707`, "
                "`resident_bytes: 11645`, `contingent_bytes: 603233` -- all sums over the "
                "16 sampled rows. Downstream prose then read '707 tools' as a fleet total "
                "in MCP-FLEET-AUDIT.md, MCP-CAPABILITY-AND-DISPOSITION.md (COVERAGE line, "
                "the TOTAL table row and the DoD ledger), and in "
                "LANE-MCPRESEARCH-BUILD-R3.md, which called it 'the fleet total' three "
                "sections after fixing the per-row share"
            ),
            "round_3_why": (
                "the SAME defect as round 2's, one level up: round 3 fixed the share and "
                "left the aggregate that feeds it labelled fleet. Measured, not inferred: "
                "sum(row.tool_count) over the 16 ranked rows == 707 exactly, and 7 of the "
                "23 mounted rows carry tool_count null. Kept here rather than deleted so "
                "the wording that shipped stays auditable"
            ),
        },
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
            "C5_denominator_declared": (
                f"the headline names its denominator ({len(measured)} of {len(all_rows)} "
                "rows sampled) or the run fails -- the round-2 overclaim was a share "
                "quoted without its scope"
            ),
            "C6_aggregate_scope_in_keys": (
                "the aggregate block is not named `fleet` and every summed value key ends "
                "in `_sampled` -- C5 protected the per-row share while the block one level "
                "up still published sampled sums under a fleet label, and five prose sites "
                "copied them as fleet totals"
            ),
        },
        "rows": rows,
    }

    # --- C6, enforced rather than merely described -------------------------
    # The failure this catches is the one that got past C5: a correctly-scoped percentage
    # sitting beside an aggregate whose NAME says fleet.  Checked structurally (key names),
    # because that is what a downstream copier reads.
    if REFUTED_AGG_KEY in payload:
        raise SystemExit(
            f"FAILED:cost-rank the aggregate block is named `{REFUTED_AGG_KEY}` but sums "
            "only the sampled rows -- that label is the round-3 overclaim one level up"
        )
    summed = (
        "tools",
        "resident_bytes",
        "contingent_bytes",
        "contingent_over_resident",
        "resident_tokens_rough",
        "contingent_tokens_rough",
    )
    agg = payload[AGG_KEY]
    unscoped = [k for k in summed if k in agg]
    if unscoped:
        raise SystemExit(
            f"FAILED:cost-rank aggregate key(s) {unscoped!r} lost the `_sampled` suffix -- "
            "a bare total gets copied into prose as a fleet figure"
        )
    return payload


def self_test(base: pathlib.Path) -> int:
    """BOTH STATES for C5: the guard must go red on the wording that was refuted.

    The mutation is applied to the module constant the producer actually formats, so a
    pass here means the enforcement path is wired -- not merely that a predicate exists.
    """
    global HEADLINE_TMPL
    good = HEADLINE_TMPL
    cases: list[tuple[str, bool, bool]] = []

    payload = build(base)
    cases.append(
        (
            "the shipped headline declares its denominator",
            "16 SAMPLED" in payload["headline"] and "of 23 rows" in payload["headline"],
            True,
        )
    )
    try:
        HEADLINE_TMPL = REFUTED_HEADLINE_TMPL
        build(base)
        fired = False
    except SystemExit:
        fired = True
    finally:
        HEADLINE_TMPL = good
    cases.append(("C5 fires on the REFUTED round-2 wording", fired, True))
    # Restoring must restore: a guard that stays red after the mutation is reverted would
    # make the case above pass for the wrong reason.
    cases.append(
        ("...and the producer is green again once reverted", bool(build(base)), True)
    )
    # The rename is load-bearing -- the bare key is what got copied without its scope.
    cases.append(
        (
            "no row carries the unscoped legacy key",
            any("resident_share_pct" in r for r in payload["rows"]),
            False,
        )
    )

    # --- C6, both states, on the two constants the producer builds keys from ----------
    # C5 was green through this entire defect: the per-row share carried its scope while
    # the block one level up published sampled sums under the label `fleet`.  A control
    # that only checks the share cannot distinguish those two states -- so C6 mutates the
    # key names themselves, which is what a downstream copier actually reads.
    global AGG_KEY, AGG_SUFFIX
    good_key, good_suffix = AGG_KEY, AGG_SUFFIX
    try:
        AGG_KEY = REFUTED_AGG_KEY
        build(base)
        fired_name = False
    except SystemExit:
        fired_name = True
    finally:
        AGG_KEY = good_key
    cases.append(
        ("C6 fires when the block is renamed back to `fleet`", fired_name, True)
    )

    try:
        AGG_SUFFIX = ""
        build(base)
        fired_suffix = False
    except SystemExit:
        fired_suffix = True
    finally:
        AGG_SUFFIX = good_suffix
    cases.append(("C6 fires when a summed key loses `_sampled`", fired_suffix, True))
    cases.append(
        (
            "...and the producer is green again once both are reverted",
            bool(build(base)),
            True,
        )
    )
    cases.append(
        (
            "the shipped aggregate states its scope in the block itself",
            "NOT fleet totals" in build(base)[AGG_KEY]["scope"],
            True,
        )
    )

    bad = [n for n, got, want in cases if got != want]
    for n, got, want in cases:
        print(f"  {'ok ' if got == want else 'BAD'} {n:56} fired={got} want={want}")
    if bad:
        print(f"FAILED:cost-rank self-test {bad}")
        return 1
    print(f"SUCCESS:cost-rank self-test {len(cases)}/{len(cases)} controls behaved")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default=str(HERE))
    ap.add_argument("-o", "--out", default="")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test(pathlib.Path(args.base))

    payload = build(pathlib.Path(args.base))
    f = payload["sampled_aggregate"]
    print(
        f"  SAMPLED ONLY: {f['servers_ranked']}/{f['servers_total']} rows ranked "
        f"({f['servers_not_measured']} not measured), {f['tools_sampled']:,} tools"
    )
    print(
        f"  RESIDENT {f['resident_bytes_sampled']:,} B "
        f"(~{f['resident_tokens_rough_sampled']:,} tok/turn, rough) | "
        f"CONTINGENT {f['contingent_bytes_sampled']:,} B | "
        f"{f['contingent_over_resident_sampled']}x   <- sums over the SAMPLED rows, "
        "a lower bound on the fleet"
    )
    print(
        f"  {'server':<22} {'tools':>5} {'RESIDENT':>9} {'share*':>7} {'DEAD-BACKEND B':>15} {'move':>6}"
    )
    print(f"  {'-' * 22} {'-' * 5} {'-' * 9} {'-' * 7} {'-' * 15} {'-' * 6}")
    for r in payload["rows"]:
        adj = r["resident_bytes_over_dead_backends"]
        adj_txt = f"{adj:,}" if adj is not None else "--"
        delta = r["rank_delta"]
        move = "same" if delta == 0 else f"{delta:+d}"
        print(
            f"  {r['name']:<22} {r['tool_count']:>5} {r['resident_bytes']:>9,} "
            f"{r['resident_share_pct_of_sampled']:>6.1f}% {adj_txt:>15} {move:>6}"
        )
    print(
        f"  * share is of the {f['servers_ranked']} SAMPLED rows, not of the "
        f"{f['servers_total']}-row fleet: {f['servers_not_measured']} rows have no stdio "
        "child to enumerate and are unmeasured, never zero"
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
        f"SUCCESS:cost-rank resident={f['resident_bytes_sampled']:,}B contingent="
        f"{f['contingent_bytes_sampled']:,}B over {f['servers_ranked']} SAMPLED rows "
        f"of {f['servers_total']} (a lower bound on the fleet, never a fleet total)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
