#!/usr/bin/env python3
"""TST-0249 probe 1: both-states UTF-8 byte-exactness.

The non-ASCII list payload rendered on a UTF-8 console must (a) exit 0, (b)
be byte-exact across two captures, and (c) equal payload.encode('utf-8') —
i.e. no mojibake, no lossy rewrite. Also asserts the >= and STAR glyphs
survive as their canonical UTF-8 sequences (mojibake would replace them).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURE = HERE / "fixtures" / "nonascii-catalog.json"


def utf8_run() -> tuple[bytes, int]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    p = subprocess.run(
        [sys.executable, "-B", str(REPO / "tools" / "command-center" / "close.py"),
         "--list", "--catalog", str(FIXTURE)],
        capture_output=True,
        env=env,
        timeout=300,
    )
    return p.stdout, p.returncode


def main() -> int:
    checks: dict[str, bool] = {}
    bytes_a, rc_a = utf8_run()
    bytes_b, rc_b = utf8_run()
    checks["utf8_exit_0"] = rc_a == 0 and rc_b == 0
    checks["two_captures_identical"] = bytes_a == bytes_b
    text = bytes_a.decode("utf-8", errors="replace")
    checks["bytes_equal_utf8_encode"] = bytes_a == text.encode("utf-8")
    checks["nonascii_survives"] = "≥" in text and "⭐" in text
    checks["canonical_sequences"] = (
        b"\xe2\x89\xa5" in bytes_a and b"\xe2\xad\x90" in bytes_a
    )
    checks["fixture_nonempty"] = FIXTURE.is_file() and FIXTURE.stat().st_size > 0

    out = {
        "probe": "probe1_both_states",
        "unit": "TST-0249",
        "signal": "(b) byte-level capture of the emitted output on a UTF-8 console",
        "utf8_byte_count": len(bytes_a),
        "utf8_sha256": __import__("hashlib").sha256(bytes_a).hexdigest(),
        "utf8_hex_preview": bytes_a[:64].hex(),
        "checks": checks,
        "ok": all(checks.values()),
    }
    (HERE / "probe1-both-states.raw.txt").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
