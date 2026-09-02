#!/usr/bin/env python3
"""Probe 2: unresolved provenance is UNKNOWN-NEEDS-PROBE, never ranked.

Independent of probe 1: re-runs scout, then checks the filesystem itself
(pathlib exists / missing) rather than trusting the scout's boolean.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import workflow_scout as S  # noqa: E402

UNKNOWN = "wf-public-unresolved-repair-oracle"
MISSING_REF = (
    "command-center/p2-wave/probes/WFA-0143/fixtures/anchors/"
    "DOES-NOT-EXIST-repair-oracle.md"
)
ANCHOR_RE = re.compile(r"^[\w./-]+\.json:\d+$")
ART = (
    REPO
    / "command-center/foundry/"
    / "WFA-0143-workflow-scout-executable-search-rank-and-provenance.json"
)


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0143-probe2 {msg}")
    return 1


def main() -> int:
    result = S.run_named_goal("known_existing")
    ranked = result.get("ranked") or []
    unknown = result.get("unknown_needs_probe") or []
    ranked_ids = [str(h.get("id")) for h in ranked]
    unknown_ids = [str(h.get("id")) for h in unknown]

    print(f"RANKED n={len(ranked)} ids={ranked_ids}")
    print(f"UNKNOWN n={len(unknown)} ids={unknown_ids}")

    if UNKNOWN in ranked_ids:
        return fail("unresolved hit was ranked")
    uhit = next((h for h in unknown if h.get("id") == UNKNOWN), None)
    if uhit is None:
        return fail("unresolved hit absent from unknown_needs_probe")

    missing_path = REPO / MISSING_REF
    print(f"FS missing_ref_exists={missing_path.is_file()} path={MISSING_REF}")
    if missing_path.is_file():
        return fail("planted-missing provenance file unexpectedly exists")

    for hit in ranked:
        hid = hit.get("id")
        prov = hit.get("provenance") or {}
        pref = prov.get("path")
        if not pref:
            return fail(f"ranked {hid} has empty provenance.path")
        p = REPO / str(pref)
        exists = p.is_file()
        print(f"FS ranked id={hid} path={pref} exists={exists}")
        if not exists:
            return fail(f"ranked {hid} provenance path does not exist")
        if prov.get("resolved") is not True:
            return fail(f"ranked {hid} provenance.resolved is not True")
        anchor = str(hit.get("evidence_anchor") or "")
        if not ANCHOR_RE.match(anchor):
            return fail(f"ranked {hid} evidence_anchor not file:line: {anchor}")
        apath, _, aline = anchor.rpartition(":")
        afile = REPO / apath
        if not afile.is_file():
            return fail(f"ranked {hid} evidence file missing {apath}")
        try:
            lineno = int(aline)
        except ValueError:
            return fail(f"ranked {hid} evidence line not int: {aline}")
        lines = afile.read_text(encoding="utf-8").splitlines()
        if lineno < 1 or lineno > len(lines):
            return fail(f"ranked {hid} evidence line out of range")
        if str(hid) not in lines[lineno - 1]:
            return fail(f"ranked {hid} evidence line does not name the id")

    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    answers = doc.get("answers") or {}
    blob = json.dumps(answers)
    if "UNKNOWN-NEEDS-PROBE" not in blob:
        return fail("artifact answers omit UNKNOWN-NEEDS-PROBE")

    print(
        "NEGATIVE CONTROL verbatim: pathlib confirms "
        f"{MISSING_REF} is absent; scout therefore lists {UNKNOWN} as "
        "UNKNOWN-NEEDS-PROBE and every ranked hit's provenance.path exists."
    )
    print("SUCCESS:WFA-0143-probe2 unresolved-provenance independent fs check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
