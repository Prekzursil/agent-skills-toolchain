#!/usr/bin/env python3
"""IMP-0476 probe1: verdict rendering over the fixture inventory.

A single-probe check and a two-same-method check MUST render NOT-CHECKED;
two independent probes that disagree MUST render DISAGREE, never OK; two
independent probes that agree render OK; two independent probes that both
fail render FAIL. The report must show zero checks whose status is OK
while the check could green from one probe alone."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures"
HC_PY = REPO / "tools" / "plugin" / "healthcheck.py"

spec = importlib.util.spec_from_file_location("imp0476_healthcheck", HC_PY)
H = importlib.util.module_from_spec(spec)
sys.modules["imp0476_healthcheck"] = H
spec.loader.exec_module(H)


def fail(msg):
    print("FAILED:IMP-0476-probe1 " + str(msg))
    return 1


def main() -> int:
    inventory = json.loads((FIXTURES / "inventory.json").read_text(encoding="utf-8"))
    report = H.render_report(FIXTURES, inventory)
    checks = {c["id"]: c for c in report["checks"]}

    # (a) single-probe check -> NOT-CHECKED, flagged as one-probe-capable.
    sans = checks.get("legacy.sansprobe")
    if not sans or sans["status"] != "NOT-CHECKED":
        return fail("single-probe check did not render NOT-CHECKED: %s" % json.dumps(sans))
    if not sans.get("can_green_from_one_probe"):
        return fail("single-probe check not flagged can_green_from_one_probe")
    if sans["status"] == "OK":
        return fail("single-probe check rendered OK - single-signal green")

    # (b) two probes, same method -> NOT independent -> NOT-CHECKED.
    same = checks.get("legacy.samemethod")
    if not same or same["status"] != "NOT-CHECKED":
        return fail("same-method check did not render NOT-CHECKED: %s" % json.dumps(same))
    if same.get("mechanically_independent"):
        return fail("same-method check flagged independent")

    # (c) disagreeing independent probes -> DISAGREE, never OK.
    router = checks.get("router.responding")
    if not router or router["status"] != "DISAGREE":
        return fail("disagreeing check did not render DISAGREE: %s" % json.dumps(router))

    # (d) positive control: genuinely healthy two-probe check -> OK.
    healthy = checks.get("control.healthy")
    if not healthy or healthy["status"] != "OK":
        return fail("positive control did not render OK: %s" % json.dumps(healthy))
    if not healthy.get("mechanically_independent"):
        return fail("positive control probes not independent")

    # (e) both-fail independent pair -> FAIL, and never OK.
    schemas = checks.get("schemas.parse")
    if not schemas or schemas["status"] != "FAIL":
        return fail("all-fail check did not render FAIL: %s" % json.dumps(schemas))

    # (f) no check is OK while greenable from one probe (the leak).
    leaked = [c["id"] for c in report["checks"] if c["status"] == "OK" and c.get("can_green_from_one_probe")]
    if leaked:
        return fail("single-signal OK leak: %s" % leaked)
    if report.get("two_signal_ok_from_one_probe_count") != 0:
        return fail("leak counter non-zero")

    one_probe_capable = [c["id"] for c in report["checks"] if c.get("can_green_from_one_probe")]
    statuses = {cid: c["status"] for cid, c in checks.items()}

    print(json.dumps({
        "probe": "probe1-verdicts",
        "unit_id": "IMP-0476",
        "statuses": statuses,
        "single_probe_green_capable_count": report.get("single_probe_green_capable_count"),
        "one_probe_capable_checks": one_probe_capable,
        "two_signal_ok_from_one_probe_count": report.get("two_signal_ok_from_one_probe_count"),
        "per_check_probes": {
            cid: [{"method": p["method"], "ok": p["ok"]} for p in c["probes"]]
            for cid, c in checks.items()
        },
        "sentinel": "SENTINEL:IMP-0476:HEALTH-TWO-SIGNAL",
    }, indent=2))
    print("SUCCESS:IMP-0476-probe1 single-probe and same-method render NOT-CHECKED; DISAGREE never OK; positive control OK; zero single-signal OK leaks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
