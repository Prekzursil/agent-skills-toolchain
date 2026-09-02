#!/usr/bin/env python3
"""Probe 1: resolver refusal + message (catalog signal a).

Looks only at ResolveResult.ok / code / message. Does not inspect dest
tree bytes — that is probe 2's independent signal.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import resolver as R  # noqa: E402
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/TST-0219.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def check_artifact() -> str | None:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return "artifact missing"
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0219" not in text:
        return "sentinel absent"
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return f"self-declared {st}"
    if doc.get("unit_id") != "TST-0219":
        return f"unit_id {doc.get('unit_id')}"
    return None


def main() -> int:
    art_err = check_artifact()
    if art_err:
        print(f"FAILED:TST-0219-probe1 {art_err}")
        return 1

    live = S.evaluate()
    priv = live["private_ok"]
    pub = live["public_offer"]
    unpin = live["unpinned_fail"]

    message_checks = {
        "names_code": R.CODE_DEPENDENCY_CONFUSION in pub["message"],
        "names_package": live["package"] in pub["message"],
        "names_public_origin": R.PUBLIC_ORIGIN in pub["message"],
        "names_private_origin": R.PRIVATE_ORIGIN in pub["message"],
        "names_integrity": live["private_integrity"] in pub["message"],
    }
    summary = {
        "probe": "probe1-origin-refusal",
        "unit_id": "TST-0219",
        "private_ok": priv["ok"],
        "private_code": priv["code"],
        "private_origin_used": priv["origin_used"],
        "public_ok": pub["ok"],
        "public_code": pub["code"],
        "public_message": pub["message"],
        "message_checks": message_checks,
        "unpinned_ok": unpin["ok"],
        "unpinned_code": unpin["code"],
        "both_states": live["both_states"],
        "negative_control": live["negative_control"],
        "pass": False,
    }
    fails = []
    if not priv["ok"] or priv["code"] != R.CODE_OK:
        fails.append("legitimate private origin did not resolve")
    if priv["origin_used"] != R.PRIVATE_ORIGIN:
        fails.append("private resolve did not use pinned origin")
    if pub["ok"]:
        fails.append("public mirror satisfied the private name")
    if pub["code"] != R.CODE_DEPENDENCY_CONFUSION:
        fails.append(f"public refusal code={pub['code']}")
    if not all(message_checks.values()):
        fails.append(f"refusal message incomplete {message_checks}")
    if unpin["ok"] or unpin["code"] != R.CODE_ORIGIN_PIN_MISSING:
        fails.append("unpinned lockfile did not fail ORIGIN_PIN_MISSING")
    if R.CODE_ORIGIN_PIN_MISSING not in unpin["message"]:
        fails.append("unpinned message does not name ORIGIN_PIN_MISSING")
    if not live["both_states"]:
        fails.append("both-states control failed")
    if not live["negative_control"]:
        fails.append("negative control failed")

    summary["pass"] = not fails
    print(json.dumps(summary, sort_keys=True))
    if fails:
        print("FAILED:TST-0219-probe1 " + "; ".join(fails))
        return 1
    print(
        "both-states: private origin resolved; public same-name refused; "
        "unpinned lockfile failed closed"
    )
    print("SUCCESS:TST-0219-probe1 resolver refusal and both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
