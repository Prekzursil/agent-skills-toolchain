#!/usr/bin/env python3
"""Named probe 1: vendor-surface diff against program routing/cost tables."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lib as L  # noqa: E402

ART = L.REPO / L.OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0015-probe1 {msg}")
    return 1


def main() -> int:
    m = L.measure()
    report = L.probe1_report(m)
    print(report, end="")
    sc = m["surface_controls"]
    if not sc["matching_ok"]:
        return fail("matching-row control did not stay green")
    if not sc["stale_ok"]:
        return fail("stale-row control did not go red")
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return fail("artifact-unparseable")
    if not isinstance(doc, dict):
        return fail("artifact-not-object")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")
    if L.catalog_sentinel() not in text:
        return fail("sentinel-absent")
    if L.PROBE1_NAME not in text:
        return fail("probe1-name-absent")
    raw = ""
    for p in doc.get("named_probes") or []:
        if isinstance(p, dict) and p.get("id") == "probe1":
            raw = str(p.get("raw_output") or "")
    if raw != report:
        return fail("named-probe1-raw-mismatch")
    live = {t["id"]: t["verdict"] for t in m["targets"]}
    seen: set[str] = set()
    for t in doc.get("targets") or []:
        if not isinstance(t, dict):
            continue
        tid = str(t.get("id") or "")
        if tid in seen:
            return fail(f"duplicate-target:{tid}")
        seen.add(tid)
        if t.get("verdict") not in L.LEGAL:
            return fail(f"illegal-verdict:{tid}")
        if tid in live and t.get("verdict") != live[tid]:
            return fail(f"verdict-drift:{tid}")
    if set(live) - seen:
        return fail("target-set-drift")
    if int((doc.get("counts") or {}).get("n_stale", -1)) != int(m["n_stale"]):
        return fail("n_stale-drift")
    print("SUCCESS:ADV-0015-probe1 vendor-surface-diff")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
