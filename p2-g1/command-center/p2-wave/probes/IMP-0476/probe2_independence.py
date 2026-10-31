#!/usr/bin/env python3
"""IMP-0476 probe2: independence audit of three checks.

For ledger.writable / router.responding / skills.registered the auditor
re-runs BOTH probes by a mechanically different method than the health
renderer (raw os.stat size + string-level key regex instead of the
renderer's pathlib stat + json.loads), re-derives the verdict itself, and
asserts the renderer's verdict equals the auditor's derivation - plus the
leak gate: no check is OK while greenable from one probe."""
from __future__ import annotations

import importlib.util
import json
import os
import re
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


def probe1_style_stat(path: Path) -> bool:
    """Mechanically different probe A: raw os.path.getsize."""
    try:
        return os.path.getsize(path) >= 20
    except OSError:
        return False


def probe1_style_keys(path: Path, required: list) -> bool:
    """Mechanically different probe B: string-level regex, not json.loads."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return all(re.search(r'"%s"' % re.escape(k), text) for k in required)


def fail(msg):
    print("FAILED:IMP-0476-probe2 " + str(msg))
    return 1


def audit_check(report_checks: dict, inventory: dict, check_id: str) -> dict:
    inventory_checks = {c["id"]: c for c in inventory.get("checks") or []}
    inv = inventory_checks[check_id]
    rendered = report_checks[check_id]
    probes = inv.get("probes") or []
    methods = [str(p.get("method") or "") for p in probes]
    independent = len(set(methods)) >= 2
    audit_rows = []
    oks = []
    for p in probes:
        rel = str(p.get("path") or "")
        path = FIXTURES / rel
        method = str(p.get("method") or "")
        if method == "file-stat":
            ok = probe1_style_stat(path)
        elif method == "json-keys":
            ok = probe1_style_keys(path, [str(x) for x in (p.get("required") or [])])
        elif method == "content-hash":
            want = str(p.get("sha256") or "")
            import hashlib
            live = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""
            ok = bool(want) and live == want
        else:
            ok = False
        oks.append(ok)
        audit_rows.append({"id": p.get("id"), "method": method, "ok": ok})
    if len(probes) == 0:
        derived = "NOT-CHECKED"
    elif len(probes) == 1:
        derived = "NOT-CHECKED"
    elif not independent:
        derived = "NOT-CHECKED"
    elif all(oks):
        derived = "OK"
    elif not any(oks):
        derived = "FAIL"
    else:
        derived = "DISAGREE"
    match = derived == rendered["status"]
    return {
        "check_id": check_id,
        "rendered": rendered["status"],
        "auditor_derived": derived,
        "match": match,
        "methods": methods,
        "methods_differ": len(set(methods)) >= 2,
        "audit_rows": audit_rows,
    }


def main() -> int:
    inventory = json.loads((FIXTURES / "inventory.json").read_text(encoding="utf-8"))
    report = H.render_report(FIXTURES, inventory)
    report_checks = {c["id"]: c for c in report["checks"]}

    audits = []
    for check_id in ("ledger.writable", "router.responding", "skills.registered"):
        audit = audit_check(report_checks, inventory, check_id)
        audits.append(audit)
        if not audit["match"]:
            return fail("auditor disagreed with renderer on %s: rendered=%s derived=%s" % (
                check_id, audit["rendered"], audit["auditor_derived"]))
        if not audit["methods_differ"]:
            return fail("check %s probes are not mechanically independent (methods: %s)" % (
                check_id, audit["methods"]))

    # Leak gate over the whole report: no OK while one-probe-capable.
    leaked = [c["id"] for c in report["checks"] if c["status"] == "OK" and c.get("can_green_from_one_probe")]
    if leaked:
        return fail("single-signal OK leak: %s" % leaked)

    print(json.dumps({
        "probe": "probe2-independence-audit",
        "unit_id": "IMP-0476",
        "audited_checks": [a["check_id"] for a in audits],
        "audits": audits,
        "leaked_single_signal_ok": leaked,
        "method": "auditor re-derivation via os.stat + regex (mechanically different from renderer)",
        "sentinel": "SENTINEL:IMP-0476:HEALTH-TWO-SIGNAL",
    }, indent=2))
    print("SUCCESS:IMP-0476-probe2 three checks audited with mechanically different probes; renderer verdicts reproduced; zero single-signal OK leaks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
