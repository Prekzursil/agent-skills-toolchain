#!/usr/bin/env python3
"""Named probe 1: deprecated install succeeds and persists a warning.

Signal 1 of the catalog evidence requirement. The same run also installs a
revoked version and asserts refusal, proving the two states are not aliases.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.deprecation import (  # noqa: E402
    DEPRECATED_VER,
    PKG,
    REVOKED_VER,
    SUCCESSOR_VER,
    run_catalog_evidence,
)

RECEIPT = REPO / "command-center/receipts/IMP-0101.json"
SENTINEL = "SUCCESS:IMP-0101"


def _check_receipt() -> None:
    if not RECEIPT.is_file() or RECEIPT.stat().st_size < 200:
        raise SystemExit("FAILED:IMP-0101-probe1 receipt missing")
    text = RECEIPT.read_text(encoding="utf-8")
    if SENTINEL not in text:
        raise SystemExit("FAILED:IMP-0101-probe1 sentinel absent")
    doc = json.loads(text)
    state = str(doc.get("state") or "").upper()
    if state in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        raise SystemExit(f"FAILED:IMP-0101-probe1 self-declared:{state}")


def main() -> int:
    _check_receipt()
    with tempfile.TemporaryDirectory(prefix="imp0101-p1-") as tmp:
        evidence = run_catalog_evidence(Path(tmp))
        dep = evidence["deprecated_install"]
        rev = evidence["revoked"]
        successor = f"{PKG}@{SUCCESSOR_VER}"
        if dep.get("ok") is not True or dep.get("installed") is not True:
            print("FAILED:IMP-0101-probe1 deprecated install did not succeed", dep)
            return 1
        if dep.get("state") != "deprecated":
            print("FAILED:IMP-0101-probe1 state not deprecated", dep)
            return 1
        warning = dep.get("warning") or {}
        if warning.get("successor") != successor or successor not in (warning.get("message") or ""):
            print("FAILED:IMP-0101-probe1 successor not named", warning)
            return 1
        if not evidence.get("warning_persisted"):
            print("FAILED:IMP-0101-probe1 warning not persisted")
            return 1
        if not evidence.get("still_listed"):
            print("FAILED:IMP-0101-probe1 deprecation silently removed the version")
            return 1
        if rev.get("ok") is not False or rev.get("installed") is not False:
            print("FAILED:IMP-0101-probe1 revoked was not refused in the same run", rev)
            return 1
        if evidence.get("states_are_aliases"):
            print("FAILED:IMP-0101-probe1 deprecated and revoked behaved as aliases")
            return 1
        payload = {
            "pass": True,
            "probe": "probe1-deprecated-installs-with-warning",
            "unit_id": "IMP-0101",
            "deprecated_ok": True,
            "warning_persisted": True,
            "successor_named": True,
            "revoked_refused_same_run": True,
            "states_are_aliases": False,
            "package_id": PKG,
            "deprecated_version": DEPRECATED_VER,
            "revoked_version": REVOKED_VER,
            "successor": successor,
        }
        print(json.dumps(payload, sort_keys=True))
        print(
            "deprecated_ok=True warning_persisted=True "
            "revoked_refused_same_run=True states_are_aliases=False"
        )
        print("SUCCESS:IMP-0101-probe1 deprecated installs with warning")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
