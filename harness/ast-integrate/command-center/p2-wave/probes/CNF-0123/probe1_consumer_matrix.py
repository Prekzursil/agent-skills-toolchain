#!/usr/bin/env python3
"""Named probe 1: re-run the consumer matrix independently of the report body."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from consumers import artifact_payload  # noqa: E402
from measure import measure_classes  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0123-downstream-readability.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0123-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0123":
        print("FAILED:CNF-0123-probe1 unit_id", doc.get("unit_id"))
        return 1
    text = json.dumps(doc)
    if "SUCCESS:CNF-0123" not in text:
        print("FAILED:CNF-0123-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:CNF-0123-probe1 self-declared", doc.get("state"))
        return 1

    live = measure_classes()
    live_map = {r["class_id"]: r for r in live}
    art_rows = artifact_payload(doc).get("classes") or []
    if len(art_rows) < 50:
        print(f"FAILED:CNF-0123-probe1 class rows {len(art_rows)} want>=50")
        return 1

    mismatches: list[str] = []
    for row in art_rows:
        cid = row.get("class_id")
        live_row = live_map.get(cid)
        if live_row is None:
            mismatches.append(f"{cid}: missing from live inventory")
            continue
        # Self artifact is stamped at emit time; live re-run must consume it.
        if cid == "conformance-report":
            if live_row.get("finding") != "consumed-readable":
                mismatches.append(
                    f"conformance-report live finding={live_row.get('finding')}"
                )
            continue
        if row.get("finding") != live_row.get("finding"):
            mismatches.append(
                f"{cid}: artifact={row.get('finding')} live={live_row.get('finding')}"
            )
        if row.get("finding") in ("unconsumed", "no-produced-sample"):
            if row.get("exit_code") is not None or live_row.get("exit_code") is not None:
                mismatches.append(f"{cid}: {row.get('finding')} but exit_code set")
        elif row.get("exit_code") is None:
            mismatches.append(f"{cid}: no exit_code and not unconsumed")
        elif row.get("exit_code") != live_row.get("exit_code"):
            mismatches.append(
                f"{cid}: exit artifact={row.get('exit_code')} live={live_row.get('exit_code')}"
            )

    extra_live = set(live_map) - {r.get("class_id") for r in art_rows}
    if extra_live:
        mismatches.append(f"live classes omitted: {sorted(extra_live)[:12]}")

    if mismatches:
        print("FAILED:CNF-0123-probe1 matrix mismatch")
        for line in mismatches[:30]:
            print(" ", line)
        return 1

    unconsumed_live = [r for r in live if r["finding"] == "unconsumed"]
    planted = live_map.get("planted-unconsumed")
    if planted is None or planted["finding"] != "unconsumed":
        print("FAILED:CNF-0123-probe1 planted-unconsumed not unconsumed")
        return 1
    if any(r.get("exit_code") == 0 for r in unconsumed_live):
        print("FAILED:CNF-0123-probe1 unconsumed marked passing")
        return 1

    produced = [r for r in live if r.get("sample_source") == "produced"]
    readable = [r for r in produced if r["finding"] == "consumed-readable"]
    if len(readable) < 3:
        print(f"FAILED:CNF-0123-probe1 produced readable={len(readable)}")
        return 1

    print(
        json.dumps(
            {
                "probe": "probe1-consumer-matrix",
                "unit_id": "CNF-0123",
                "classes": len(live),
                "unconsumed": len(unconsumed_live),
                "produced_readable": [r["class_id"] for r in readable],
                "planted_unconsumed": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"classes={len(live)} unconsumed={len(unconsumed_live)} "
        f"produced_readable={len(readable)}"
    )
    print("SUCCESS:CNF-0123-probe1 consumer matrix and unconsumed-not-passing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
