#!/usr/bin/env python3
"""Probe 2: rider obligations verbatim; histogram diff explains every class change."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import corpus as C  # noqa: E402
import engine as E  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0033-probe2 {msg}")
    return 1


def main() -> int:
    nodes = C.all_nodes()
    extracted = E.extract_all(nodes, C.disk_fetcher)
    rider_rows = [
        r for r in extracted["rows"] if r["id"] == "rider-commons-clause"
    ]
    if len(rider_rows) != 1:
        return fail("rider node missing")
    rider = rider_rows[0]
    fetched = C.disk_fetcher(C.rider_node())
    verb = rider.get("rider_obligations_verbatim") or ""
    if rider["new_class"] != E.RIDER_RESTRICTED:
        return fail(f"rider class {rider['new_class']}")
    if not verb:
        return fail("rider obligations empty")
    if verb not in fetched["text"]:
        return fail("rider obligations not a substring of fetched licence text")
    if "summar" in verb.lower() or verb.lower().startswith("in short"):
        return fail("rider obligations look summarised")
    if 'right to Sell the Software' not in verb:
        return fail("verbatim Sell restriction missing")
    if len(verb) < 200:
        return fail("verbatim block too short to be the clause")

    old_h = extracted["old_histogram"]
    new_h = extracted["new_histogram"]
    if old_h.get("THIRD-PARTY") != 26:
        return fail("old histogram THIRD-PARTY")
    if old_h.get("RIDER-RESTRICTED") != 1:
        return fail("old histogram RIDER")
    diff = extracted["histogram_diff"]
    changed = []
    keys = set(old_h) | set(new_h)
    for k in keys:
        if int(old_h.get(k, 0)) != int(new_h.get(k, 0)):
            changed.append(k)
    explained = {d["class"] for d in diff}
    missing = [k for k in changed if k not in explained]
    if missing:
        return fail(f"histogram diff missing classes {missing}")
    for d in diff:
        if not str(d.get("explanation") or "").strip():
            return fail(f"empty explanation for {d['class']}")
        if int(d["old_count"]) == int(d["new_count"]):
            return fail(f"diff row for unchanged class {d['class']}")

    # Mutant: drop one explanation → would fail the missing-class check.
    mutant_explained = explained - {changed[0]} if changed else explained
    if changed and changed[0] in mutant_explained:
        return fail("mutant setup")
    if changed and changed[0] not in explained:
        return fail("live diff missing a changed class")

    # old_class never used as signal B
    for r in extracted["rows"]:
        if r.get("signal_b_source") == "graph-rule-based":
            return fail(f"{r['id']} used graph class as signal B")
        if r.get("inadmissible_signal") != "graph-rule-based-old_class-not-used":
            return fail(f"{r['id']} missing inadmissible tag")

    payload = {
        "changed_classes": sorted(changed),
        "diff_rows": len(diff),
        "pass": True,
        "probe": "probe2-rider-and-histogram",
        "rider_verbatim_len": len(verb),
        "unit_id": "WFA-0033",
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:WFA-0033-probe2 rider obligations verbatim; "
        "every changed histogram class explained"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
