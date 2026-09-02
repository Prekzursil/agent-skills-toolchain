#!/usr/bin/env python3
"""Probe 2: a GUARANTEED unit must FAIL LOUDLY on a vendor missing a capability.

Both-states:
  * anthropic lacks tools.mcp.codex -> REFUSED DOWNGRADE-REFUSED
  * openai has tools.mcp.codex -> ALLOWED
  * portable GUARANTEED unit -> ALLOWED on both vendors
  * empty leak declaration -> INVALID-ADAPTER
  * silent_shim is not the live negotiate() path
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from contract import VENDORS  # noqa: E402
from negotiate import (  # noqa: E402
    ALLOWED,
    DEGRADED,
    INVALID,
    REFUSED,
    negotiate,
    silent_shim,
    validate_adapter,
)

GUARANTEED_CODEX = {
    "id": "ARC-0038-probe2-guaranteed-codex",
    "min_tier": "GUARANTEED",
    "capability_needs": [
        "artifact.json_schema",
        "artifact.completion_sentinel",
        "dispatch.blocking_foreground",
        "tools.mcp.codex",
    ],
}

PORTABLE = {
    "id": "ARC-0038-probe2-portable",
    "min_tier": "GUARANTEED",
    "capability_needs": [
        "artifact.json_schema",
        "artifact.completion_sentinel",
        "dispatch.blocking_foreground",
        "transport.prompt_by_file",
        "tools.fs.read",
    ],
}


def main() -> int:
    v_anth = validate_adapter("anthropic")
    v_oai = validate_adapter("openai")
    print(f"adapter_anthropic={v_anth['status']} adapter_openai={v_oai['status']}")

    empty = copy.deepcopy(VENDORS["anthropic"])
    empty["leaks"] = []
    empty_check = validate_adapter("anthropic-empty", empty)
    print(f"empty_leaks status={empty_check['status']} marker={empty_check['marker']}")
    empty_ok = (
        empty_check["status"] == INVALID and "empty-leak" in empty_check["reason"]
    )

    bad = negotiate(GUARANTEED_CODEX, "anthropic")
    good = negotiate(GUARANTEED_CODEX, "openai")
    print(f"guaranteed_codex anthropic status={bad['status']} marker={bad['marker']}")
    print(f"guaranteed_codex openai status={good['status']} marker={good['marker']}")
    refuse_ok = (
        bad["status"] == REFUSED
        and "DOWNGRADE-REFUSED" in bad["marker"]
        and "tools.mcp.codex" in bad["marker"]
        and bad["status"] != DEGRADED
        and not str(bad["marker"]).startswith("SUCCESS:")
        and not str(bad["marker"]).startswith("NEGOTIATED:")
    )
    allow_ok = good["status"] == ALLOWED and good["missing"] == []

    p_a = negotiate(PORTABLE, "anthropic")
    p_o = negotiate(PORTABLE, "openai")
    print(f"portable anthropic status={p_a['status']} marker={p_a['marker']}")
    print(f"portable openai status={p_o['status']} marker={p_o['marker']}")
    portable_ok = p_a["status"] == ALLOWED and p_o["status"] == ALLOWED

    shim = silent_shim(GUARANTEED_CODEX, "anthropic")
    print(f"silent_shim status={shim['status']} marker={shim['marker']}")
    shim_caught = shim["status"] != REFUSED and bad["status"] == REFUSED

    fired_on_bad = refuse_ok and empty_ok
    silent_on_good = allow_ok and portable_ok
    print(
        f"fired_on_bad={fired_on_bad} silent_on_good={silent_on_good} "
        f"shim_caught={shim_caught} empty_ok={empty_ok}"
    )
    if not (fired_on_bad and silent_on_good and shim_caught):
        print("FAILED:ARC-0038-probe2 downgrade-refusal")
        return 1
    print("SUCCESS:ARC-0038-probe2 GUARANTEED missing capability FAIL LOUDLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
