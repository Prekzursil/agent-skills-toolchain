#!/usr/bin/env python3
"""Named probe 1: bind result per live manifest entry, captured from the dispatcher.

Independent of emit.py's narrative. Re-imports dispatch.py and binds
hooks/_dispatch/manifest.json. Requires the receipt to exist and carry SUCCESS:TST-0042.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from suite import LIVE, load_dispatch  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0042.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:TST-0042-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:TST-0042-probe1 receipt unparseable {exc}")
        return 1
    if not isinstance(doc, dict):
        print("FAILED:TST-0042-probe1 receipt not an object")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:TST-0042-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:TST-0042" not in text:
        print("FAILED:TST-0042-probe1 sentinel absent")
        return 1
    if doc.get("unit_id") != "TST-0042":
        print(f"FAILED:TST-0042-probe1 unit_id {doc.get('unit_id')}")
        return 1

    mod = load_dispatch()
    live = mod.load_and_bind(LIVE, REPO)
    binds = live.get("binds") or []
    if not live.get("ok") or live.get("rejected"):
        print("FAILED:TST-0042-probe1 live manifest rejected at load")
        print(json.dumps(live, sort_keys=True)[:2000])
        return 1
    if not binds:
        print("FAILED:TST-0042-probe1 live manifest has zero hooks (vacuous bind)")
        return 1
    unbound = [b for b in binds if not b.get("bound")]
    if unbound:
        print("FAILED:TST-0042-probe1 dispatcher did not bind every entry")
        print(json.dumps(unbound, sort_keys=True)[:2000])
        return 1
    required = ("event", "matcher", "interpreter", "interpreter_resolved", "argv")
    for b in binds:
        missing = [k for k in required if not b.get(k)]
        if missing:
            print(f"FAILED:TST-0042-probe1 bind row {b.get('id')} missing {missing}")
            return 1
        if b.get("event") not in mod.CLIENT_EVENT_VOCABULARY:
            print(f"FAILED:TST-0042-probe1 bound unknown event {b.get('event')}")
            return 1

    payload = {
        "all_bound": True,
        "bind_ids": [b["id"] for b in binds],
        "count": len(binds),
        "events": [b["event"] for b in binds],
        "interpreters": [b["interpreter_resolved"] for b in binds],
        "pass": True,
        "probe": "probe1-bind",
        "unit_id": "TST-0042",
    }
    print(json.dumps(payload, sort_keys=True))
    print(f"bound={len(binds)} ids={payload['bind_ids']}")
    print("SUCCESS:TST-0042-probe1 dispatcher bind result per live manifest entry")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
