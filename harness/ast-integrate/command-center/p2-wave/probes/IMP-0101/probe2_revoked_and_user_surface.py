#!/usr/bin/env python3
"""Named probe 2: revoked is refused; warning survives to the user channel.

Signal 2 of the catalog evidence requirement, plus the reviewer check that the
warning is not only written to a log nobody reads. Negative control: a
successor pointer to a missing package is rejected at deprecation time.
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
    SUCCESSOR_VER,
    DeprecationRegistry,
    SuccessorDoesNotExist,
    run_catalog_evidence,
    seed_catalog_registry,
)
from marketplace.warning_channel import USER_CHANNEL_SOURCE  # noqa: E402

RECEIPT = REPO / "command-center/receipts/IMP-0101.json"
SENTINEL = "SUCCESS:IMP-0101"


def _check_receipt() -> None:
    if not RECEIPT.is_file() or RECEIPT.stat().st_size < 200:
        raise SystemExit("FAILED:IMP-0101-probe2 receipt missing")
    text = RECEIPT.read_text(encoding="utf-8")
    if SENTINEL not in text:
        raise SystemExit("FAILED:IMP-0101-probe2 sentinel absent")
    doc = json.loads(text)
    state = str(doc.get("state") or "").upper()
    if state in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        raise SystemExit(f"FAILED:IMP-0101-probe2 self-declared:{state}")


def main() -> int:
    _check_receipt()
    with tempfile.TemporaryDirectory(prefix="imp0101-p2-") as tmp:
        root = Path(tmp) / "pair"
        evidence = run_catalog_evidence(root)
        rev = evidence["revoked"]
        if rev.get("ok") is not False or rev.get("state") != "revoked":
            print("FAILED:IMP-0101-probe2 revoked not refused", rev)
            return 1
        if evidence["deprecated_install"].get("ok") is not True:
            print("FAILED:IMP-0101-probe2 pair missing deprecated success")
            return 1

        user_root = Path(tmp) / "user"
        first = seed_catalog_registry(user_root)
        discarded = first.install(PKG, DEPRECATED_VER)
        del discarded
        later = DeprecationRegistry(user_root)
        hc = later.health_check()
        successor = f"{PKG}@{SUCCESSOR_VER}"
        if hc.get("source") != USER_CHANNEL_SOURCE:
            print("FAILED:IMP-0101-probe2 health-check read the log, not the user channel", hc)
            return 1
        if hc.get("degraded") is not True or hc.get("warning_count", 0) < 1:
            print("FAILED:IMP-0101-probe2 warning did not survive to the user", hc)
            return 1
        messages = hc.get("messages") or []
        if not any(successor in (m.get("message") or "") for m in messages):
            print("FAILED:IMP-0101-probe2 user message does not name successor", messages)
            return 1
        if not all(m.get("visible") is True and m.get("channel") == "user" for m in messages):
            print("FAILED:IMP-0101-probe2 messages not user-visible", messages)
            return 1

        neg = DeprecationRegistry(Path(tmp) / "neg")
        neg.publish(PKG, DEPRECATED_VER, payload="v1")
        refused = False
        try:
            neg.deprecate(
                PKG,
                DEPRECATED_VER,
                reason="gone",
                successor="acme.does-not-exist",
            )
        except SuccessorDoesNotExist:
            refused = True
        if not refused:
            print("FAILED:IMP-0101-probe2 negative control did not reject missing successor")
            return 1
        if neg.get(PKG, DEPRECATED_VER)["state"] != "current":
            print("FAILED:IMP-0101-probe2 negative control mutated state")
            return 1

        payload = {
            "pass": True,
            "probe": "probe2-revoked-and-user-surface",
            "unit_id": "IMP-0101",
            "revoked_refused": True,
            "deprecated_ok_same_run": True,
            "user_channel": USER_CHANNEL_SOURCE,
            "user_warning_survived": True,
            "successor_named_to_user": True,
            "negative_control_refused": True,
        }
        print(json.dumps(payload, sort_keys=True))
        print(
            "revoked_refused=True user_warning_survived=True "
            "negative_control_refused=True"
        )
        print("SUCCESS:IMP-0101-probe2 revoked refused; warning reaches the user")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
