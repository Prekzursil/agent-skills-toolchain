#!/usr/bin/env python3
"""IMP-0072 probe 2: middle-record tamper is named; re-chain residual is honest.

Signal 2 of the catalog evidence pair: after a single-field edit to seq=3
(deprecate.message), verification FAILS and names seq=3 — not merely that
"something changed".

Reviewer experiment: the same edit plus recompute of every downstream hash
verifies CLEAN. An unanchored chain cannot prove original authorship.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.event_chain import (  # noqa: E402
    build_demo_log,
    rechain_after_edit,
    tamper_field,
    verify_log,
)

RECEIPT = REPO / "command-center/receipts/IMP-0072.json"


def main() -> int:
    if not RECEIPT.is_file() or RECEIPT.stat().st_size < 200:
        print("FAILED:IMP-0072-probe2 receipt missing")
        return 1
    if "SUCCESS:IMP-0072" not in RECEIPT.read_text(encoding="utf-8"):
        print("FAILED:IMP-0072-probe2 sentinel absent")
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0072-p2-") as td:
        base = Path(td)
        genuine = base / "genuine.jsonl"
        tampered = base / "tampered.jsonl"
        rechained = base / "rechained.jsonl"

        records = build_demo_log(genuine)
        genuine.read_bytes()  # force a read independent of the builder return
        tampered.write_bytes(genuine.read_bytes())
        rechained.write_bytes(genuine.read_bytes())

        control = verify_log(genuine)
        if not control.ok:
            print("FAILED:IMP-0072-probe2 control genuine failed", control.as_dict())
            return 1

        tamper_field(tampered, 3, ("payload", "message"), "silently rewritten history")
        broken = verify_log(tampered)
        if broken.ok:
            print("FAILED:IMP-0072-probe2 tamper not detected")
            return 1
        if broken.first_bad_seq != 3:
            print("FAILED:IMP-0072-probe2 wrong localisation", broken.as_dict())
            return 1
        if not broken.named_record or broken.named_record.get("action") != "deprecate":
            print("FAILED:IMP-0072-probe2 did not name deprecate record", broken.as_dict())
            return 1
        if broken.expected_hash == broken.observed_hash:
            print("FAILED:IMP-0072-probe2 hashes did not diverge")
            return 1

        genuine_head = json.loads(genuine.read_text(encoding="utf-8").splitlines()[-1])[
            "record_hash"
        ]
        rechain_after_edit(
            rechained, 3, ("payload", "message"), "forged-after-the-fact"
        )
        forged = verify_log(rechained)
        if not forged.ok:
            print("FAILED:IMP-0072-probe2 rechain unexpectedly broken", forged.as_dict())
            return 1
        forged_head = json.loads(rechained.read_text(encoding="utf-8").splitlines()[-1])[
            "record_hash"
        ]
        if forged_head == genuine_head:
            print("FAILED:IMP-0072-probe2 rechain did not change head")
            return 1
        if not any("unanchored-chain-limit" in n for n in forged.notes):
            print("FAILED:IMP-0072-probe2 residual note missing")
            return 1

    payload = {
        "pass": True,
        "probe": "probe2-tamper-localise-and-rechain-honesty",
        "unit_id": "IMP-0072",
        "control_genuine_ok": True,
        "tamper_detected": True,
        "named_seq": 3,
        "named_action": "deprecate",
        "named_package_id": records[2]["package_id"],
        "rechain_verifies_clean": True,
        "rechain_detected": False,
        "honest_limit": (
            "An unanchored hash chain cannot distinguish a fully re-chained "
            "rewrite from original history. Detection of silent retroactive "
            "edits holds only when hashes are left stale, or when an external "
            "anchor (signed head, independent replica, WORM media) commits "
            "the head digest."
        ),
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"tamper_named_seq=3 action=deprecate rechain_detected=False "
        f"control_ok={control.ok}"
    )
    print("SUCCESS:IMP-0072-probe2 tamper named at seq=3; re-chain residual disclosed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
