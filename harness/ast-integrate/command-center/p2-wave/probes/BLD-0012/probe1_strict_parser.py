#!/usr/bin/env python3
"""Named probe 1: strict-parser + unknown hook event.

Catalog tests:
  * replay recorded payload with an unknown extra field → loud degrade
  * replay recorded payload with a missing optional field → loud degrade
  * unknown hook event name → named error, never silent no-op
Both-states: the silent-swallow control must disagree with the shipped adapter.
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from adapter import parse_hook, silent_unknown_event  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0012.json"
RECORDED = HERE / "fixtures/recorded_pretooluse.json"


def fail(msg: str) -> int:
    print(f"FAILED:BLD-0012-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:BLD-0012" not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if doc.get("unit_id") != "BLD-0012":
        return fail(f"unit_id {doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    payload = json.loads(RECORDED.read_text(encoding="utf-8"))
    good = parse_hook(payload)
    if not good["ok"] or good["code"] != "OK":
        return fail(f"canonical recorded payload rejected {good}")

    extra = deepcopy(payload)
    extra["unexpected_host_field"] = "should-degrade"
    extra_res = parse_hook(extra)
    if extra_res["ok"] or extra_res["code"] != "UNKNOWN_FIELD" or not extra_res["message"]:
        return fail(f"extra field was not loud {extra_res}")

    missing = deepcopy(payload)
    missing.pop("prompt_id")
    miss_res = parse_hook(missing)
    if miss_res["ok"] or miss_res["code"] != "MISSING_OPTIONAL" or not miss_res["message"]:
        return fail(f"missing optional was not loud {miss_res}")

    unknown = deepcopy(payload)
    unknown["hook_event_name"] = "NotARealHookEvent"
    unk = parse_hook(unknown)
    silent = silent_unknown_event(unknown)
    if silent["ok"] and silent["code"] == "OK":
        pass  # control state: swallow
    else:
        return fail("silent-unknown control no longer swallows (control broken)")
    if unk["ok"] or unk["code"] != "UNKNOWN_EVENT" or not unk["message"]:
        return fail(f"unknown event was silent {unk}")
    if unk["ok"] == silent["ok"]:
        return fail("unknown-event adapter agrees with silent swallow (measures nothing)")

    print(
        json.dumps(
            {
                "probe": "probe1-strict-parser",
                "unit_id": "BLD-0012",
                "canonical_ok": True,
                "extra_field": extra_res["code"],
                "missing_optional": miss_res["code"],
                "unknown_event": unk["code"],
                "silent_control_ok": silent["ok"],
                "discriminates": unk["ok"] != silent["ok"],
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:BLD-0012-probe1 strict-parser extra/missing/unknown-event")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
