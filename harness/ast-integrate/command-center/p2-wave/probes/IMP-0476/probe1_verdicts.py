#!/usr/bin/env python3
"""Probe 1: two-signal verdicts on the installed-component inventory.

Single-probe (and cloned-method) checks must render NOT-CHECKED, never OK.
Disagreeing independent probes must render DISAGREE, never OK.
Positive controls on genuinely healthy components must render OK.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from fixtures import COMPONENTS, ensure_fixtures  # noqa: E402
from tools.plugin.healthcheck import render_report  # noqa: E402

ART = REPO / "command-center" / "receipts" / "IMP-0476.json"
EXPECT_CAPABLE = ("hooks.loaded", "skills.registered", "mcp.reachable")
EXPECT_OK = ("ledger.writable", "deploy.in_sync")
EXPECT_DISAGREE = "router.responding"
EXPECT_FAIL = "cache.valid"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0476-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "IMP-0476":
        return fail(f"unit_id {doc.get('unit_id')}")
    text = json.dumps(doc)
    if "SENTINEL:IMP-0476:HEALTH-TWO-SIGNAL" not in text:
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    inventory = ensure_fixtures()
    live = render_report(COMPONENTS, inventory)
    by_id = {c["id"]: c for c in live["checks"]}

    for cid in EXPECT_CAPABLE:
        row = by_id.get(cid)
        if not row:
            return fail(f"missing check {cid}")
        if row["status"] != "NOT-CHECKED":
            return fail(f"{cid} status={row['status']} want NOT-CHECKED")
        if row["status"] == "OK":
            return fail(f"{cid} greened from insufficient probes")
        if not row.get("can_green_from_one_probe"):
            return fail(f"{cid} not flagged as single-probe-green-capable")
        if len(row.get("probes") or []) < 1:
            return fail(f"{cid} missing probe listing")

    for cid in EXPECT_OK:
        row = by_id.get(cid)
        if not row:
            return fail(f"missing positive control {cid}")
        if row["status"] != "OK":
            return fail(f"{cid} status={row['status']} want OK")
        if not row.get("mechanically_independent"):
            return fail(f"{cid} OK without independent probes")
        if len(row.get("probes") or []) < 2:
            return fail(f"{cid} did not list both probes")
        if not all(p.get("ran") and p.get("ok") for p in row["probes"]):
            return fail(f"{cid} listed a non-ok probe under OK")

    disagree = by_id.get(EXPECT_DISAGREE)
    if not disagree:
        return fail("missing disagree check")
    if disagree["status"] != "DISAGREE":
        return fail(f"router status={disagree['status']} want DISAGREE")
    if disagree["status"] == "OK":
        return fail("disagreeing probes rendered OK")
    oks = [p["ok"] for p in disagree["probes"]]
    if not (any(oks) and not all(oks)):
        return fail(f"router probes not mixed ok={oks}")

    failed = by_id.get(EXPECT_FAIL)
    if not failed:
        return fail("missing fail check")
    if failed["status"] != "FAIL":
        return fail(f"cache status={failed['status']} want FAIL")

    if live["single_probe_green_capable_count"] != 3:
        return fail(
            f"capable_count={live['single_probe_green_capable_count']} want=3"
        )
    if live["two_signal_ok_from_one_probe_count"] != 0:
        return fail("two-signal command leaked an OK from one probe")
    if int(doc.get("exact_question_answer") or -1) != 3:
        return fail(f"artifact answer {doc.get('exact_question_answer')} != live 3")

    listed = {c.get("id"): c for c in (doc.get("checks") or []) if isinstance(c, dict)}
    for cid, row in by_id.items():
        got = listed.get(cid)
        if not got:
            return fail(f"artifact missing check {cid}")
        if got.get("status") != row["status"]:
            return fail(f"artifact {cid} status drift {got.get('status')} vs {row['status']}")
        art_probes = got.get("probes") or []
        if len(art_probes) != len(row["probes"]):
            return fail(f"artifact {cid} probe listing length drift")
        if len(art_probes) < 1:
            return fail(f"artifact {cid} has no probe outputs")
        if cid in EXPECT_CAPABLE and len(art_probes) < 1:
            return fail(f"artifact {cid} single-probe listing empty")
        if cid in EXPECT_OK and len(art_probes) < 2:
            return fail(f"artifact {cid} did not list BOTH probes")

    out = {
        "probe": "probe1-verdicts",
        "unit_id": "IMP-0476",
        "single_probe_not_checked": list(EXPECT_CAPABLE),
        "positive_ok": list(EXPECT_OK),
        "disagree": EXPECT_DISAGREE,
        "fail": EXPECT_FAIL,
        "single_probe_green_capable_count": 3,
        "two_signal_ok_from_one_probe_count": 0,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "single_not_checked="
        + ",".join(EXPECT_CAPABLE)
        + " positive_ok="
        + ",".join(EXPECT_OK)
        + " disagree="
        + EXPECT_DISAGREE
        + " fail="
        + EXPECT_FAIL
        + " capable=3 leaked_ok=0"
    )
    print("SUCCESS:IMP-0476-probe1 two-signal verdicts NOT-CHECKED DISAGREE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
