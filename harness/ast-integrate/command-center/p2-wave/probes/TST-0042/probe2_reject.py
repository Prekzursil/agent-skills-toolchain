#!/usr/bin/env python3
"""Named probe 2: invented event rejected at load; both-states in one process.

The conforming fixture must load+bind while the invented-event fixture must be
rejected at load with UNKNOWN_EVENT. A bind-time miss is not this control.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from suite import FIX, load_dispatch  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0042.json"
INVENTED = "DefinitelyNotAClientEvent_TST0042"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:TST-0042-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:TST-0042-probe2 receipt unparseable {exc}")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:TST-0042-probe2 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:TST-0042" not in text:
        print("FAILED:TST-0042-probe2 sentinel absent")
        return 1

    mod = load_dispatch()
    good = mod.load_and_bind(FIX / "conforming.json", REPO)
    bad = mod.try_load(FIX / "invented-event.json", REPO)
    # Bind path must not be used for the invented event: load rejects first.
    if bad.get("ok") or not bad.get("rejected"):
        print("FAILED:TST-0042-probe2 invented event was not rejected at load")
        print(json.dumps(bad, sort_keys=True)[:2000])
        return 1
    if bad.get("code") != "UNKNOWN_EVENT":
        print(f"FAILED:TST-0042-probe2 expected UNKNOWN_EVENT got {bad.get('code')}")
        return 1
    if bad.get("event") != INVENTED:
        # try_load records the invented name on LoadRejected.event
        print(f"FAILED:TST-0042-probe2 rejected event {bad.get('event')!r} != {INVENTED!r}")
        return 1
    if INVENTED in mod.CLIENT_EVENT_VOCABULARY:
        print("FAILED:TST-0042-probe2 invented name is in the vocabulary")
        return 1
    if not (good.get("ok") and good.get("all_bound")):
        print("FAILED:TST-0042-probe2 conforming fixture did not bind")
        print(json.dumps(good, sort_keys=True)[:2000])
        return 1

    payload = {
        "both_states": True,
        "conforming_bound": True,
        "invented_code": bad.get("code"),
        "invented_event": bad.get("event"),
        "invented_rejected_at_load": True,
        "pass": True,
        "probe": "probe2-reject",
        "same_process": True,
        "unit_id": "TST-0042",
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "conforming_bound=True invented_rejected_at_load=True "
        f"code={bad.get('code')} event={bad.get('event')}"
    )
    print("SUCCESS:TST-0042-probe2 invented event rejected at load (both-states)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
