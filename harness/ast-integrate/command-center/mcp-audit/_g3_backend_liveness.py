#!/usr/bin/env python3
"""CENSUS: how much of cloud-hub's advertised surface sits over a backend that cannot answer.

WHY.  ``call_verified`` was correctly narrowed to "the process starts and ADVERTISES a tool
surface".  ``searxng`` was the worked counter-example: 4 advertised tools over a dead
instance.  That example understates the problem by roughly 60x -- ``cloud-hub`` is the
largest row in the fleet and is not one server but a proxy over ~12 backends, each of which
can be down while ITS TOOLS STAY LISTED.  Not an inference; it is what the server says::

    [cloud-hub] backend 'rclone (rclone-mcp over rcd)' is unavailable: initialize failed:
    deadline exceeded. Its other tools stay listed; fix the credentials/login for that
    backend and restart the session.

WHAT CHANGED, AND WHY THIS FILE SHRANK.  This script used to own three things: the
tool->backend classifier, a hand-typed ``BACKEND_PROBES`` dict of measured verdicts, and
the census that joins them.  The first two were duplicates of what the producer needed, and
a hand-typed verdict dict is the same defect as ``rank_disposition.S4_EXECUTED`` -- a claim
living inside the thing that reports it.  Both now have ONE home:

  * the classifier + its C1/C2/C3 controls -> ``backend_map.py`` (CI-wired, deterministic)
  * the measured verdicts                  -> ``s4-evidence.json`` (dated, attributed)

What is left here is only the CENSUS, whose verdict is a dated liveness claim and therefore
stays out of CI -- the same split ``_r2_ruff_census.py`` already sets.  Running it per PR
would re-assert a 2026-08-13 fleet state indefinitely.

Read-only.  Spawns nothing.  Prints no credential value.
"""

from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import backend_map  # noqa: E402
import s4_evidence  # noqa: E402


def main() -> int:
    matrix = json.loads((HERE / backend_map.MATRIX).read_text(encoding="utf-8"))
    row = next(r for r in matrix["rows"] if r["name"] == backend_map.PROXY_SERVER)
    names: list[str] = row["tool_names"]
    total, schema_b, name_b = row["tool_count"], row["schema_bytes"], row["name_bytes"]

    # The classifier's own controls live with the classifier; run them first, because a
    # census over an unvalidated partition is fiction.
    if backend_map.self_test(HERE) != 0:
        print("FAILED:g3-backend classifier controls are red -- census withheld")
        return 1

    ev = s4_evidence.load(HERE)
    probes = ev.backends(backend_map.PROXY_SERVER)
    buckets, unclassified = backend_map.bucket(names)
    if unclassified:
        print(f"FAILED:g3-backend {len(unclassified)} unclassified after C1 passed")
        return 1

    per_tool_b = schema_b / total if total else 0.0
    print(
        f"\n  cloud-hub advertised surface: {total} tools, {schema_b:,} B schema, {name_b:,} B names"
    )
    print(f"  {'backend':<16} {'tools':>6} {'~schema B':>11} {'name B':>8}  probe")
    print(f"  {'-' * 16} {'-' * 6} {'-' * 11} {'-' * 8}  {'-' * 46}")

    dead_tools = 0
    dead_name_b = 0
    for backend in sorted(buckets, key=lambda k: -len(buckets[k])):
        tools = buckets[backend]
        nb = sum(len(t) for t in tools)
        rec = probes.get(backend)
        if rec:
            mark = f"{rec['verdict'].upper():<9} via {rec['tool']}"
            if rec["verdict"] not in s4_evidence.LIVE:
                dead_tools += len(tools)
                dead_name_b += nb
        else:
            mark = "UNMEASURED (not claimed live)"
        print(
            f"  {backend:<16} {len(tools):>6} {len(tools) * per_tool_b:>11,.0f} {nb:>8,}  {mark}"
        )

    # Recompute both totals by an independent route and require agreement -- one sum that
    # cannot visibly be wrong is not a measurement.
    dead_set = {b for b, r in probes.items() if r["verdict"] not in s4_evidence.LIVE}
    indep_tools = sum(1 for t in names if backend_map.classify(t) in dead_set)
    indep_bytes = sum(len(t) for t in names if backend_map.classify(t) in dead_set)
    if (dead_tools, dead_name_b) != (indep_tools, indep_bytes):
        print(
            f"FAILED:g3-backend disagreement tools {dead_tools}!={indep_tools} "
            f"or bytes {dead_name_b}!={indep_bytes}"
        )
        return 1
    print(
        f"\n  ok  dead-surface totals agree on two independent sums ({dead_tools} tools, {dead_name_b:,} B)"
    )

    pct = 100.0 * dead_tools / total if total else 0.0
    pct_b = 100.0 * dead_name_b / name_b if name_b else 0.0
    print(
        f"\n  MEASURED-DEAD advertised surface: {dead_tools}/{total} tools ({pct:.1f}%), "
        f"~{dead_tools * per_tool_b:,.0f} B schema, {dead_name_b:,} B of RESIDENT name cost ({pct_b:.1f}% of the row)"
    )
    print(
        f"  SCOPE: {len(probes)} of {len(buckets)} backends probed; the other "
        f"{len(buckets) - len(probes)} are UNMEASURED -- explicitly NOT claimed live."
    )
    print(
        f"SUCCESS:g3-backend {dead_tools}/{total} cloud-hub tools ({pct:.1f}%) are "
        "advertised over a backend measured non-functional"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
