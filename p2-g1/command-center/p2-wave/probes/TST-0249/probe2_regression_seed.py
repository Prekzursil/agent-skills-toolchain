#!/usr/bin/env python3
"""TST-0249 probe 2: cp1252 console exit status + the UTF-8 decode regression seed.

Signal (a): the production ``close.py --list`` under ``PYTHONIOENCODING=cp1252``
must RAISE (UnicodeEncodeError, exit 1, empty stdout) — the receipt's recorded
finding is that production declares no console error handler. The regression
seed re-proves the byte-level fact behind the unit: the live UTF-8
WORK-UNIT-CATALOG.json raises UnicodeDecodeError under the cp1252 codec at the
undefined byte 0x90 (from the U+2B50 sequence e2 ad 90), while utf-8 reads it
clean. Detector control: strict cp1252 ENCODE of a non-ASCII payload raises.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURE = HERE / "fixtures" / "nonascii-catalog.json"
LIVE_CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"


def cp1252_run() -> tuple[bytes, bytes, int]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "cp1252"
    p = subprocess.run(
        [sys.executable, "-B", str(REPO / "tools" / "command-center" / "close.py"),
         "--list", "--catalog", str(FIXTURE)],
        capture_output=True,
        env=env,
        timeout=300,
    )
    return p.stdout, p.stderr, p.returncode


def main() -> int:
    checks: dict[str, bool] = {}
    out_bytes, err_bytes, rc = cp1252_run()
    checks["cp1252_exit_1"] = rc == 1
    checks["cp1252_stdout_empty"] = len(out_bytes) == 0
    err_text = err_bytes.decode("utf-8", errors="replace")
    checks["cp1252_unicode_encode_error"] = "UnicodeEncodeError" in err_text
    checks["cp1252_charmap_undefined"] = "character maps to <undefined>" in err_text

    # Regression seed: live catalog decodes utf-8 clean, cp1252 raises at 0x90.
    raw = LIVE_CATALOG.read_bytes()
    utf8_ok, cp1252_raises = True, False
    undefined_byte = None
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        utf8_ok = False
    try:
        raw.decode("cp1252")
    except UnicodeDecodeError as exc:
        cp1252_raises = True
        undefined_byte = format(exc.object[exc.start], "04x")
    checks["live_catalog_utf8_ok"] = utf8_ok
    checks["live_catalog_cp1252_raises"] = cp1252_raises
    checks["live_catalog_undefined_byte_0x90"] = undefined_byte == "0090"

    # Same behavior on the fixture (smaller scale, byte-level record).
    fx = FIXTURE.read_bytes()
    fx_raises = False
    fx_undefined = None
    try:
        fx.decode("cp1252")
    except UnicodeDecodeError as exc:
        fx_raises = True
        fx_undefined = format(exc.object[exc.start], "04x")
    checks["fixture_cp1252_decode_raises"] = fx_raises
    checks["fixture_undefined_byte_0x90"] = fx_undefined == "0090"

    # Detector control: strict cp1252 ENCODE of a non-ASCII payload must raise,
    # so the UTF-8 identity test is not ASCII-only.
    payload = "R-T01 OPEN (the ≥ unit) ⭐\n"
    strict_raises = False
    try:
        io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict").write(payload)
    except UnicodeEncodeError:
        strict_raises = True
    checks["strict_cp1252_encode_raises"] = strict_raises

    out = {
        "probe": "probe2_regression_seed",
        "unit": "TST-0249",
        "signal": "(a) process exit status on a cp1252 console + decode seed",
        "cp1252_exit_code": rc,
        "cp1252_stdout_byte_count": len(out_bytes),
        "stderr_preview": err_text[-260:],
        "live_catalog_bytes": len(raw),
        "live_catalog_undefined_byte": undefined_byte,
        "fixture_bytes": len(fx),
        "fixture_sha256": hashlib.sha256(fx).hexdigest(),
        "fixture_undefined_byte": fx_undefined,
        "checks": checks,
        "ok": all(checks.values()),
    }
    (HERE / "probe2-regression-seed.raw.txt").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
