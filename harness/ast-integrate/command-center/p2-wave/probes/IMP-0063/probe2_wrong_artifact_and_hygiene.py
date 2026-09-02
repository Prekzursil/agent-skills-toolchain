#!/usr/bin/env python3
"""Named probe 2 (IMP-0063): negative control + key hygiene + receipt honesty.

- An attestation for a DIFFERENT artifact must not verify against this one.
- Unsigned (missing envelope) is UNSIGNED, never valid-by-absence.
- Producer source has no key-generation calls (planted control proves the grep is live).
- No private-key PEM is stored in unit artifacts (planted PEM proves the scanner is live).
- Catalog receipt is present, non-BLOCKED, and carries SUCCESS:IMP-0063.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HARNESS = REPO / "tools" / "plugin" / "tests"
sys.path.insert(0, str(HARNESS))
import harness as H  # noqa: E402

RECEIPT = REPO / "command-center" / "receipts" / "IMP-0063.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def main() -> int:
    cross = H.different_artifact_control()
    print(json.dumps({"negative_control": cross}, sort_keys=True))
    if not cross.get("matched_ok"):
        print("FAILED:IMP-0063-probe2 matched artifacts did not verify")
        return 1
    if not cross.get("cross_fails"):
        print("FAILED:IMP-0063-probe2 different-artifact attestation verified")
        return 1
    if cross.get("unsigned_code") != "UNSIGNED":
        print(f"FAILED:IMP-0063-probe2 unsigned code={cross.get('unsigned_code')}")
        return 1

    missing = H.missing_key_fails_closed()
    if not missing.get("raised") or missing.get("code") != "OWNER_KEY_REQUIRED":
        print(f"FAILED:IMP-0063-probe2 missing owner key not fail-closed: {missing}")
        return 1

    audit = H.keygen_audit()
    print(json.dumps({"keygen_audit": audit}, sort_keys=True))
    if not audit.get("planted_found"):
        print("FAILED:IMP-0063-probe2 keygen detector is vacuous")
        return 1
    if not audit.get("production_clean"):
        print(f"FAILED:IMP-0063-probe2 producer has key-lifecycle calls: {audit.get('production_hits')}")
        return 1

    hygiene = H.private_key_hygiene()
    print(json.dumps({"hygiene": hygiene}, sort_keys=True))
    if not hygiene.get("planted_control_fired"):
        print("FAILED:IMP-0063-probe2 PEM detector is vacuous")
        return 1
    if not hygiene.get("clean"):
        print(f"FAILED:IMP-0063-probe2 private key material present: {hygiene.get('findings')}")
        return 1

    if not RECEIPT.is_file() or RECEIPT.stat().st_size <= 0:
        print("FAILED:IMP-0063-probe2 catalog receipt absent")
        return 1
    text = RECEIPT.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:IMP-0063-probe2 receipt unparseable: {exc}")
        return 1
    state = str(doc.get("state") or "").upper()
    if state in NOT_DELIVERING:
        print(f"FAILED:IMP-0063-probe2 self-declared {state}")
        return 1
    if "SUCCESS:IMP-0063" not in text:
        print("FAILED:IMP-0063-probe2 sentinel absent")
        return 1

    print(
        "cross_fails=True unsigned=UNSIGNED keygen_clean=True "
        f"hygiene_clean=True receipt_state={state}"
    )
    print("SUCCESS:IMP-0063-probe2 wrong-artifact-and-hygiene")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
