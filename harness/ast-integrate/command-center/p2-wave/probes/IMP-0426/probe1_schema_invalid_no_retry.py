#!/usr/bin/env python3
"""Probe 1: schema-invalid is classified and NOT retried; valid payload passes.

Consumer is invoked only after the adapter-boundary gate accepts the payload.
A use-vs-mention control: retry policy for MCP interaction stays available,
but schema-invalid must still be zero-retry.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[3] / "tools" / "command-center"))

import output_schema_gate as gate  # noqa: E402
from scenario import run_schema_invalid, run_valid  # noqa: E402


def fail(reason: str) -> int:
    print(f"FAILED:IMP-0426-probe1 {reason}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0426-p1-") as tmp:
        root = Path(tmp)
        valid = run_valid(workdir=root / "valid")
        invalid = run_schema_invalid(workdir=root / "invalid")

    vg = valid["schema_gate"]
    ig = invalid["schema_gate"]
    ok = (
        valid["terminal_kind"] == "SUCCESS"
        and vg["classification"] == gate.CLASS_OK
        and vg["valid"] is True
        and vg["enforced"] is True
        and vg["retries_used"] == 0
        and vg["consumer_invoked"] is True
        and len(valid["consumer_payloads"]) == 1
        and valid["consumer_payloads"][0].get("answer") == "typed-output-path-ok"
        and invalid["terminal_kind"] == "FAILED"
        and ig["classification"] == gate.CLASS_SCHEMA_INVALID
        and ig["valid"] is False
        and ig["retries_used"] == 0
        and ig["consumer_invoked"] is False
        and len(invalid["consumer_payloads"]) == 0
        and len(invalid["attempts"]) == 1
        and gate.decide_retry(gate.CLASS_SCHEMA_INVALID, 0, False) is None
        and gate.decide_retry(gate.CLASS_MCP, 0, False) == "ignore-user-config"
        and gate.decide_retry(gate.CLASS_MCP, 1, False) is None
    )
    payload = {
        "probe": "probe1-schema-invalid-no-retry",
        "unit_id": "IMP-0426",
        "pass": ok,
        "valid_terminal": valid["terminal_kind"],
        "valid_classification": vg["classification"],
        "valid_consumer_invoked": vg["consumer_invoked"],
        "invalid_terminal": invalid["terminal_kind"],
        "invalid_classification": ig["classification"],
        "invalid_retries_used": ig["retries_used"],
        "invalid_attempts": len(invalid["attempts"]),
        "invalid_consumer_invoked": ig["consumer_invoked"],
        "invalid_errors": ig.get("errors"),
        "schema_invalid_retry_action": gate.decide_retry(
            gate.CLASS_SCHEMA_INVALID, 0, False
        ),
        "mcp_retry_action": gate.decide_retry(gate.CLASS_MCP, 0, False),
    }
    print(json.dumps(payload, sort_keys=True))
    if not ok:
        return fail(
            "valid-must-pass-and-reach-consumer; "
            "schema-invalid-must-not-retry-or-reach-consumer"
        )
    print(
        "SUCCESS:IMP-0426-probe1 valid payload accepted at adapter boundary; "
        "schema-invalid classified and not retried"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
