#!/usr/bin/env python
"""postmodelswitch-ledger/log.py — PostModelSwitch hook: durable ledger of every model switch.

Implements sota-2026-09.md Tier-3 (HEAVY): "PostModelSwitch (v2.1.251) logs every safeguard
switch to the event ledger". PostModelSwitch DOES fire for safeguard-initiated switches
(unlike PreModelSwitch, which does not) — this is the labelled-downgrade dataset the
classifier research lacked. Inject-only; never blocks; fail-open on every error.
"""
import sys, os, json, datetime, pathlib

LEDGER = pathlib.Path(os.environ.get(
    "PMODELSWITCH_LEDGER",
    str(pathlib.Path.home() / ".claude" / "hooks" / "postmodelswitch-ledger" / "switches.jsonl")))

def main():
    try:
        raw = sys.stdin.read()
        p = json.loads(raw) if raw.strip() else {}
    except Exception:
        return 0
    row = {
        "ts": datetime.datetime.now().astimezone().isoformat(),
        "fromModel": p.get("fromModel") or p.get("currentModel"),
        "toModel": p.get("toModel") or p.get("newModel"),
        "session_id": p.get("session_id") or p.get("sessionId"),
        "reason": p.get("reason") or p.get("switchReason"),
        "keys": sorted(p.keys()),
    }
    try:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
