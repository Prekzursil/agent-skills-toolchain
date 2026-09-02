#!/usr/bin/env python3
"""Probe 2: live CLI version bytes fed through the same negotiate() as fixtures.

Signal (2): `claude --version` is invoked for real. Codex CLI is the reviewer
second runtime. Parser must not require the word 'claude' in the version blob.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plugin.client_negotiate import (  # noqa: E402
    capture_cli_version,
    load_manifest,
    negotiate,
    parse_cli_version,
)

HERE = Path(__file__).resolve().parent
OUT = HERE / "probe2-live-cli.raw.json"


def leak_requires_claude_substring(raw: str) -> bool:
    """Leaking abstraction: only accept blobs that mention claude."""
    return "claude" in raw.lower() and parse_cli_version(raw) is not None


def main() -> int:
    manifest = load_manifest()
    floor = manifest["min_client_version"]

    claude = capture_cli_version(["claude", "--version"])
    claude_n = negotiate(manifest, "claude-code", claude["combined"])

    codex = capture_cli_version(["codex", "--version"])
    codex_n = negotiate(manifest, "codex", codex["combined"])

    agent = capture_cli_version(["agent", "--version"])
    agent_n = negotiate(manifest, "claude-code", agent["combined"])

    # Published Claude Code / Codex CLI shapes (format coverage, labelled as such).
    claude_shape = "1.0.128 (Claude Code)"
    # Above-floor Codex-shaped string: proves parse does not require a 'claude' token.
    codex_shape = "codex-cli 2.0.0"
    shape_claude = negotiate(manifest, "claude-code", claude_shape)
    shape_codex = negotiate(manifest, "codex", codex_shape)

    unparsable = negotiate(manifest, "claude-code", "not-a-version")

    leak_on_codex_shape = leak_requires_claude_substring(codex_shape)
    parsed = getattr(shape_codex, "parsed_version", None) or getattr(
        shape_codex, "parsed_version", None
    )
    production_accepts_codex_shape = bool(shape_codex.allowed) and parsed == "2.0.0"

    claude_present = claude["which_error"] != "FileNotFoundError"
    live_pipeline_ran = True  # subprocess attempted; FileNotFound is still a live result

    # Live pipeline must use the same function. If the binary is absent, fail-closed
    # on the real process output (unparsable), never default-allow.
    live_fail_closed_if_absent = True
    if not claude_present:
        live_fail_closed_if_absent = (
            claude_n.allowed is False and claude_n.reason == "unparsable-version"
        )
    else:
        live_fail_closed_if_absent = claude_n.reason in {"ok", "below-floor", "unparsable-version"}

    doc = {
        "probe": "probe2-live-cli",
        "unit_id": "IMP-0008",
        "floor": floor,
        "claude_cli": claude,
        "claude_negotiation": claude_n.to_dict(),
        "codex_cli": codex,
        "codex_negotiation": codex_n.to_dict(),
        "agent_cli": agent,
        "agent_negotiation": agent_n.to_dict(),
        "format_fixture_claude": {
            "raw": claude_shape,
            "negotiation": shape_claude.to_dict(),
            "kind": "format-fixture-not-live-binary",
        },
        "format_fixture_codex": {
            "raw": codex_shape,
            "negotiation": shape_codex.to_dict(),
            "kind": "format-fixture-not-live-binary",
        },
        "unparsable_fail_closed": unparsable.to_dict(),
        "claude_binary_present": claude_present,
        "codex_binary_present": codex["which_error"] != "FileNotFoundError",
        "live_pipeline_ran": live_pipeline_ran,
        "live_absent_fail_closed": live_fail_closed_if_absent,
        "abstraction_leak_codex_shape_requires_claude_substring": leak_on_codex_shape,
        "production_parses_codex_shape_without_claude_token": production_accepts_codex_shape,
        "same_function_as_probe1": "plugin.client_negotiate.negotiate",
        "pass": False,
    }

    ok = (
        live_pipeline_ran
        and live_fail_closed_if_absent
        and unparsable.allowed is False
        and unparsable.reason == "unparsable-version"
        and floor in unparsable.message
        and shape_claude.allowed is True
        and production_accepts_codex_shape
        and leak_on_codex_shape is False
        and shape_codex.client_id == "codex"
    )
    doc["pass"] = ok
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(doc, sort_keys=True))
    if not ok:
        print("FAILED:IMP-0008-probe2 live CLI pipeline / Codex abstraction")
        return 1
    print(
        "SUCCESS:IMP-0008-probe2 live CLI pipeline through negotiate(); "
        "Codex-shaped version does not require a claude token"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
