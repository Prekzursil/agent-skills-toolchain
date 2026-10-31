#!/usr/bin/env python3
"""Executable tests for arg_marshalling (no pytest required)."""
from __future__ import annotations

import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN))
import arg_marshalling as am  # noqa: E402


def main() -> int:
    payload = am.make_over_limit_payload(40_000)
    rec = am.spawn_payload(payload)
    assert rec.returncode == 0, rec.stderr
    assert rec.transport == "payload-file"
    assert rec.child_reported_bytes == 40_000
    assert rec.child_source == "file"
    assert rec.cleaned is True
    assert rec.inline_cmdline_length > am.WINDOWS_CREATEPROCESS_LIMIT
    assert rec.argv_cmdline_length <= am.CONSERVATIVE_THRESHOLD
    raised = False
    try:
        am.spawn_payload(payload, force_inline=True)
    except OSError as exc:
        raised = True
        assert am.is_createprocess_206(exc)
    assert raised
    print("SUCCESS:test_arg_marshalling")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
