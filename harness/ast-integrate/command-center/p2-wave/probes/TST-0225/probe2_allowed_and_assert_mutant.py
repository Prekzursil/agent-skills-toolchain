#!/usr/bin/env python3
"""TST-0225 probe 2: detector control + assertion-only negative control.

The same connect canary MUST succeed for a unit declaring network access,
proving the probe reaches the network. An env-flag-only 'network: none'
must also succeed, proving a documented assertion is not enforcement.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "lib"))

import workspace as ws  # noqa: E402


def main() -> int:
    with ws.ephemeral_listener() as (host, port):
        allowed = ws.run_canary(
            network="allowed", host=host, port=port, timeout=1.5
        )
        mutant = ws.assertion_only_canary(host, port, timeout=1.5)
        js = _node_canary("allowed", host, port)
        unit_ok = (allowed.get("unit") or {}).get("connected") is True
        mutant_ok = (mutant.get("unit") or {}).get("connected") is True
        js_ok = bool(js.get("ok")) and (js.get("unit") or {}).get("connected") is True
        # Both-states: re-run none against the same listener; must fail.
        denied = ws.run_canary(network="none", host=host, port=port, timeout=1.5)
        denied_unit = denied.get("unit") or {}
        logged = ws.blocked_attempt_logged(denied, host, port)
        both_states = (
            unit_ok
            and (not denied_unit.get("connected"))
            and ws.network_layer_failure(denied_unit)
            and logged["ok"]
        )
        doc = {
            "probe": "probe2-allowed-and-assert-mutant",
            "unit_id": "TST-0225",
            "host": host,
            "port": port,
            "allowed": allowed,
            "assertion_only": mutant,
            "workspace_mjs": js,
            "denied_on_same_listener": {
                "connected": denied_unit.get("connected"),
                "result": denied_unit.get("result"),
                "errno": denied_unit.get("errno"),
                "oob_hits": logged["count"],
            },
            "detector_control_reaches_network": unit_ok,
            "assertion_only_does_not_block": mutant_ok,
            "both_states": both_states,
        }
        ok = unit_ok and mutant_ok and js_ok and both_states
        doc["pass"] = bool(ok)
        print(json.dumps(doc, indent=2, sort_keys=True, default=str))
        if not ok:
            print("FAILED:TST-0225-probe2 detector control or assertion mutant")
            return 1
        print(
            "SUCCESS:TST-0225-probe2 allowed connect succeeded; "
            "assertion-only mutant still reached the listener"
        )
        return 0


def _node_canary(network: str, host: str, port: int) -> dict:
    import os
    import subprocess

    repo = REPO
    script = (
        "import { runCanary } from './tools/lib/workspace.mjs';"
        f"const r = runCanary({{ network: {network!r}, host: {host!r}, port: {int(port)} }});"
        "process.stdout.write(JSON.stringify(r));"
    )
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=20,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if proc.returncode != 0:
        return {
            "ok": False,
            "rc": proc.returncode,
            "stderr": (proc.stderr or "")[-800:],
        }
    try:
        parsed = json.loads((proc.stdout or "").strip() or "{}")
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": str(exc), "stdout": (proc.stdout or "")[-800:]}
    parsed["ok"] = True
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
