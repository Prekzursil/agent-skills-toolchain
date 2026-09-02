#!/usr/bin/env python3
"""Probe 1: lease expiry and renew-extends.

Expiry: a non-holder write during TTL logs a conflict; the same write after
TTL does not. Renew: extending the lease keeps conflict logging past the
original expiry; an unrenewed twin does not.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

RECEIPT = S.REPO / "command-center" / "receipts" / "IMP-0410.json"


def check_receipt() -> str | None:
    if not RECEIPT.is_file():
        return None
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"receipt self-declared {doc.get('state')}"
    if "SENTINEL:IMP-0410:LEASES-ADVISORY-LOGGED" not in RECEIPT.read_text(
        encoding="utf-8"
    ):
        return "sentinel-absent"
    tests = doc.get("tests") or {}
    for key in ("expiry", "renew_extends"):
        row = tests.get(key) or {}
        if row.get("pass") is not True or row.get("result") != "PASS":
            return f"receipt test {key} not PASS"
    return None


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0410-p1-") as td:
        tmp = Path(td)
        expiry = S.run_expiry(tmp)
        renew = S.run_renew_extends(tmp)
    print(json.dumps({"expiry": expiry, "renew_extends": renew}, sort_keys=True))
    print(
        f"expiry pass={expiry['pass']} mid_conflict={expiry['before_expiry_conflict']} "
        f"post_conflict={expiry['after_expiry_conflict']} refused_mid={expiry['before_expiry_refused']}"
    )
    print(
        f"renew pass={renew['pass']} late_conflict={renew['late_write_conflict']} "
        f"control_conflict={renew['unrenewed_control_conflict']} "
        f"expires={renew['renewed_expires_at']}"
    )
    if not expiry["pass"]:
        print("FAILED:IMP-0410-probe1 expiry")
        return 1
    if not renew["pass"]:
        print("FAILED:IMP-0410-probe1 renew-extends")
        return 1
    rec_err = check_receipt()
    if rec_err:
        print(f"FAILED:IMP-0410-probe1 receipt {rec_err}")
        return 1
    print("SUCCESS:IMP-0410-probe1 expiry and renew-extends")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
