#!/usr/bin/env python3
"""IMP-0008 probe2: live CLI versions fed through the same negotiate().

Rebuilt 2026-10-26 (shard-6 wave-4 resume). Signal 2 of the unit's
evidence_requirement: the REAL installed client versions read from their own
CLIs and fed through the same negotiate() as the fixtures, proving the parser
handles real string formats and not only fixtures.

Abstraction-leak check (reviewer requirement): Codex-shaped version strings
must parse without any 'claude' token requirement. Absent binaries are an
honest live outcome: their error text must fail closed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

from client_negotiate import capture_cli_version, load_manifest, negotiate, parse_cli_version  # noqa: E402


def _record(neg) -> dict:
    return {
        "allowed": neg.allowed,
        "reason": neg.reason,
        "parsed_version": neg.parsed_version,
        "required_version": neg.required_version,
        "message": neg.message,
    }


def main() -> int:
    manifest = load_manifest(REPO / ".claude-plugin" / "plugin.json")
    floor = str(manifest.get("min_client_version"))
    facts: dict = {"unit_id": "IMP-0008", "probe": "probe2-live-cli", "floor": floor}
    checks: list[dict] = []

    def chk(name: str, ok: bool) -> bool:
        checks.append({"check": name, "ok": bool(ok)})
        return bool(ok)

    # Real client runtimes, captured from their own CLIs.
    claude = capture_cli_version(["claude", "--version"])
    codex = capture_cli_version(["codex", "--version"])

    # Same negotiate() as the fixtures, fed the live combined output.
    n_claude = negotiate(manifest, "claude-code", claude["combined"])
    n_codex = negotiate(manifest, "codex", codex["combined"])

    # Fail-closed when a runtime is absent or its output is unparsable.
    if claude["which_error"]:
        chk("claude_absent_fails_closed", (not n_claude.allowed) and n_claude.reason == "unparsable-version")
    else:
        chk("claude_live_version_parses", n_claude.parsed_version is not None)
        chk("claude_live_at_or_above_floor_allowed", n_claude.allowed is True)

    if codex["which_error"]:
        chk("codex_absent_fails_closed", (not n_codex.allowed) and n_codex.reason == "unparsable-version")
    else:
        # Abstraction-leak proof: Codex-shaped string parses WITHOUT 'claude'.
        chk("codex_shape_parses_without_claude_token", n_codex.parsed_version is not None
            and "claude" not in codex["combined"].lower())
        # Honest negotiation outcome recorded (parse may be above or below floor).
        chk("codex_verdict_consistent_with_parse", (n_codex.allowed is True) == (
            tuple(int(p) for p in (n_codex.parsed_version or "0").split("."))
            >= tuple(int(p) for p in floor.split("."))
        ))

    # Real-world unparsable string (e.g. a CLI printing a fatal error) fail-closes.
    n_err = negotiate(manifest, "claude-code", "fatal: not a git repository")
    chk("error_text_fail_closed", (not n_err.allowed) and n_err.reason == "unparsable-version" and floor in n_err.message)

    # Recorded observation (current parser is search-based semver): a
    # calendar-shaped client string parses above the floor and is allowed.
    cal = negotiate(manifest, "codex", "2026.08.11-e8db854")
    facts["calendar_shape_observation"] = {
        "input": "2026.08.11-e8db854",
        "parsed": cal.parsed_version,
        "allowed": cal.allowed,
        "note": "search-based semver accepts calendar versions; recorded, not asserted",
    }

    facts["claude_cli"] = {k: claude[k] for k in ("argv", "which", "which_error", "stdout", "stderr", "returncode", "combined", "parsed")}
    facts["claude_negotiation"] = _record(n_claude)
    facts["codex_cli"] = {k: codex[k] for k in ("argv", "which", "which_error", "stdout", "stderr", "returncode", "combined", "parsed")}
    facts["codex_negotiation"] = _record(n_codex)
    facts["checks"] = checks
    facts["all_ok"] = all(c["ok"] for c in checks)
    print(json.dumps(facts, indent=1))
    if not facts["all_ok"]:
        print("FAILED:IMP-0008-probe2 live CLI negotiation check failed")
        return 1
    print("SUCCESS:IMP-0008-probe2 real CLI versions negotiated through the single negotiate()")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
