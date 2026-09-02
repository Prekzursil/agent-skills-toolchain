#!/usr/bin/env python3
"""Probe 2: deny-filter exclusion, corrupt-blob fail-closed, owner reachability gate."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0106.json"


def main() -> int:
    live = S.run_filter_and_corrupt()
    gated = S.ast_public_bind_is_gated()
    printable = {k: live[k] for k in sorted(live) if k != "pass"}
    printable["ast_gate"] = gated
    print(json.dumps(printable, sort_keys=True, default=str)[:4000])
    if not live.get("pass"):
        print("FAILED:IMP-0106-probe2 filter/corrupt/owner-gate scenario failed")
        return 1
    if not live.get("deny_excludes_entirely"):
        print("FAILED:IMP-0106-probe2 denied package was not excluded entirely")
        return 1
    if not live.get("corrupt_did_not_propagate"):
        print("FAILED:IMP-0106-probe2 corrupted blob propagated")
        return 1
    owner = live.get("owner_gate") or {}
    if not owner.get("unapproved_public_blocked"):
        print("FAILED:IMP-0106-probe2 public bind without owner approval was allowed")
        return 1
    if not gated.get("pass") or not gated.get("no_socket_bind"):
        print("FAILED:IMP-0106-probe2 public bind is not gated in source")
        return 1
    if not ART.is_file():
        print("FAILED:IMP-0106-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:IMP-0106-probe2 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:IMP-0106" not in text:
        print("FAILED:IMP-0106-probe2 sentinel absent")
        return 1
    print("SUCCESS:IMP-0106-probe2 deny-filter, corrupt fail-closed, owner gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
