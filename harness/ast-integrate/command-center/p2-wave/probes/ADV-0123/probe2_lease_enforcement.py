#!/usr/bin/env python3
"""Named probe 2: lease acquire then conflicting write (not the git-index oracle)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import race as R  # noqa: E402

ART = R.REPO / R.OUTPUT_REL
LEGAL = R.LEGAL


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0123-probe2 {msg}")
    return 1


def main() -> int:
    m = R.measure()
    report = R.probe2_report(m)
    print(report, end="")
    ctrl = m["controls"]
    if not ctrl["lease_both_states_ok"]:
        return fail("consult-fixture both-states control did not calibrate")
    lease = m["probe2"]["lease"]
    cw = lease["conflicting_write"]
    if cw["disposition"] != "silently-allowed" or cw["blocked"] or not cw["wrote"]:
        return fail("unconsulted conflicting write was not silently allowed")
    if lease["lease_prevented_overlap"]:
        return fail("lease_prevented_overlap true without a shipped control")
    if not lease["lease_is_documentation"]:
        return fail("expected absent shipped file-lease API on this worktree")
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
    if R.catalog_sentinel() not in text:
        return fail("sentinel-absent")
    if R.PROBE2_NAME not in text:
        return fail("probe2-name-absent")
    errs = R.schema_errors(doc)
    if errs:
        return fail(f"schema:{errs[0]}")
    raw = ""
    for p in doc.get("named_probes") or []:
        if isinstance(p, dict) and p.get("id") == "probe2":
            raw = str(p.get("raw_output") or "")
    if raw != report:
        return fail("named-probe2-raw-mismatch")
    live = {t["target_id"]: t["verdict"] for t in m["targets"]}
    for t in doc.get("targets") or []:
        if not isinstance(t, dict):
            continue
        tid = t.get("target_id")
        if t.get("verdict") not in LEGAL:
            return fail(f"illegal-verdict:{tid}")
        if live.get(tid) != t.get("verdict"):
            return fail(f"verdict-drift:{tid}")
    if live.get("TARGET-LEASE-PREVENTS-CONFLICTING-WRITE") != "REFUTED":
        return fail("lease-prevent-target-not-refuted")
    if live.get("TARGET-LEASE-IS-CONSULTED-CONTROL") != "REFUTED":
        return fail("lease-control-target-not-refuted")
    art_disp = (
        ((doc.get("probe2") or {}).get("lease") or {}).get("conflicting_write") or {}
    ).get("disposition")
    if art_disp != cw["disposition"]:
        return fail("artifact-disposition-drift")
    print("SUCCESS:ADV-0123-probe2 lease-enforcement")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
