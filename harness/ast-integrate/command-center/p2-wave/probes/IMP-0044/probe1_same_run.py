#!/usr/bin/env python3
"""Probe 1: same-run evidence. Always-OK is UNTRUSTWORTHY; genuine is TRUSTED."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "plugin"))

from both_states_harness import (  # noqa: E402
    TRUSTED,
    UNTRUSTWORTHY,
    same_run_catalog_evidence,
)

ART = REPO / "command-center" / "receipts" / "IMP-0044.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0044-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0044" not in text:
        print("FAILED:IMP-0044-probe1 sentinel absent")
        return 1
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:IMP-0044-probe1 self-declared", doc.get("state"))
        return 1

    report = same_run_catalog_evidence()
    by_id = report.by_id()
    useless = by_id["always-ok"]
    genuine = by_id["content-marker"]
    ok = (
        report.same_run is True
        and useless.trust == UNTRUSTWORTHY
        and genuine.trust == TRUSTED
        and useless.skipped is False
        and genuine.skipped is False
        and genuine.broken_class == "FIRED"
        and genuine.good_class == "SILENT"
    )
    payload = {
        "probe": "probe1-same-run",
        "unit_id": "IMP-0044",
        "same_run": report.same_run,
        "always_ok_trust": useless.trust,
        "always_ok_reason": useless.reason,
        "genuine_trust": genuine.trust,
        "genuine_reason": genuine.reason,
        "trusted_count": report.trusted_count,
        "untrustworthy_count": report.untrustworthy_count,
        "pass": ok,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"always_ok={useless.trust} genuine={genuine.trust} "
        f"same_run={report.same_run}"
    )
    if not ok:
        print("FAILED:IMP-0044-probe1 same-run evidence")
        return 1
    print("SUCCESS:IMP-0044-probe1 always-ok UNTRUSTWORTHY and genuine TRUSTED in one run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
