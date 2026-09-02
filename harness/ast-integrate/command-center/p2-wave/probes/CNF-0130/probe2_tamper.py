#!/usr/bin/env python3
"""Probe 2: tamper verification + adversarial conclusion leak via quoted test name."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from dispatcher import dispatch, verify  # noqa: E402
from scenario import (  # noqa: E402
    LEAK_NAME_NEEDLE,
    RECEIPT_NEEDLE,
    build_tree,
    inject_innocent_named_receipt_test,
    inject_quoted_test_name_leak,
)

ART = REPO / "command-center/receipts/CNF-0130.json"


def _need(cond: bool, msg: str) -> None:
    if not cond:
        raise SystemExit(f"FAILED:CNF-0130-probe2 {msg}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="cnf0130-p2-") as tmp:
        root = build_tree(Path(tmp) / "tree")
        rec = dispatch(root, exclusion_enabled=True)
        payload = rec["payload"].encode("utf-8")
        _need(verify(payload, rec["attestation"]), "fresh payload failed verification")

        tampered = payload + b"\n# TAMPER: implementer conclusion smuggled after attest\n"
        _need(not verify(tampered, rec["attestation"]), "tamper did not fail verification")
        _need(verify(payload, rec["attestation"]), "verify is not stable on original bytes")
        _need(
            not verify(payload, "0" * 64),
            "verify accepted a wrong same-length hash",
        )

        leak = inject_quoted_test_name_leak(root)
        rec_leak = dispatch(root, exclusion_enabled=True)
        _need(LEAK_NAME_NEEDLE not in rec_leak["payload"], "quoted test name leak survived")
        _need(RECEIPT_NEEDLE not in rec_leak["payload"], "leak file body survived")
        _need(
            any(leak.name in e["path"] for e in rec_leak["excluded"]),
            "quoted-test-name file not excluded",
        )
        _need(
            verify(rec_leak["payload"].encode("utf-8"), rec_leak["attestation"]),
            "leak-attempt dispatch attestation does not verify",
        )

        innocent = inject_innocent_named_receipt_test(root)
        rec_body = dispatch(root, exclusion_enabled=True)
        _need(RECEIPT_NEEDLE not in rec_body["payload"], "innocent-named receipt test leaked")
        _need(
            any(innocent.name in e["path"] for e in rec_body["excluded"]),
            "content-shaped test receipt not excluded",
        )

        poisoned = Path(tmp) / "poisoned"
        build_tree(poisoned, poisoned_statement=True)
        rec_stmt = dispatch(poisoned, exclusion_enabled=True)
        _need(
            LEAK_NAME_NEEDLE not in rec_stmt["payload"],
            "statement still quotes the conclusion-bearing test name",
        )
        _need("src/mod.py:add returns the integer sum" in rec_stmt["payload"], "clean statement dropped")

        attack_passed = (
            LEAK_NAME_NEEDLE in rec_leak["payload"] or RECEIPT_NEEDLE in rec_leak["payload"]
        )
        _need(not attack_passed, "reviewer constructed a verifying payload that still leaks")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        _need(doc.get("state") not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}, "receipt blocked")
        _need("SUCCESS:CNF-0130" in json.dumps(doc), "receipt sentinel")

    print(
        json.dumps(
            {
                "probe": "probe2-tamper-and-leak",
                "unit_id": "CNF-0130",
                "pass": True,
                "tamper_fails_verify": True,
                "quoted_test_name_excluded": True,
                "content_receipt_test_excluded": True,
                "poisoned_statement_redacted": True,
                "reviewer_leak_attack": "FAIL-CLOSED",
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNF-0130-probe2 tamper and adversarial leak")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
