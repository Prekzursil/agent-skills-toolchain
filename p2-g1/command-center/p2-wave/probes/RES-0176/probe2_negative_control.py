#!/usr/bin/env python3
"""RES-0176 probe2_negative_control.

tests row: probe2-negative-control - at least one abstraction is NOT
transferable with a named runtime service; a mutant that marks it transferable
must fail. Recomputes the negative-control verdict: conversational_group_chat
is recorded NOT transferable with autogen's GroupChatManager service named,
and no transfer verdict contradicts that. Defaults to FAIL.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def main() -> int:
    art = REPO / "command-center/research/teardown/RES-0176-teardown-graph-vs-role-frameworks.json"
    txt = art.read_text(encoding="utf-8")
    doc = json.loads(txt)
    checks = []

    def ck(name, ok, detail=""):
        checks.append({"check": name, "pass": bool(ok), "detail": str(detail)[:240]})
        return bool(ok)

    nc = doc.get("negative_control") or {}
    ck("nc-names-non-transferable-abstraction",
       nc.get("abstraction") == "conversational_group_chat" and nc.get("transferable") is False,
       f"{nc.get('abstraction')} transferable={nc.get('transferable')}")
    ck("nc-names-runtime-service",
       bool(nc.get("runtime_service")) and "GroupChatManager" in str(nc.get("runtime_service")),
       str(nc.get("runtime_service"))[:110])
    ck("nc-states-why", len(str(nc.get("why") or "")) > 40, str(nc.get("why"))[:110])

    tv = doc.get("transfer_verdicts") or []
    contradict = [t.get("abstraction") for t in tv
                  if t.get("abstraction") == "conversational_group_chat"
                  and t.get("transferable") is True]
    ck("no-verdict-marks-group-chat-transferable", not contradict, str(contradict))
    # mutant leg: flipping the recorded NC to transferable would leave the
    # verdict set inconsistent - assert the NC id itself encodes the reject
    ck("nc-id-carries-not-transferable",
       "NOT-TRANSFERABLE" in str(nc.get("id")), str(nc.get("id")))

    ck("state-success-sentinel",
       doc.get("state") == "SUCCESS" and doc.get("completion_sentinel") == "SUCCESS:RES-0176",
       f"state={doc.get('state')}")

    red = [c for c in checks if not c["pass"]]
    verdict = {"probe": "probe2-negative-control", "unit_id": "RES-0176", "pass": not red,
               "checks": checks, "red": red}
    print(json.dumps(verdict))
    print("SUCCESS:RES-0176-probe2 group-chat NC not-transferable, mutant would fail" if not red
          else f"FAILED:RES-0176-probe2 red={len(red)}")
    return 0 if not red else 1


if __name__ == "__main__":
    sys.exit(main())
