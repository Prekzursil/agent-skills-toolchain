#!/usr/bin/env python3
"""Live measurements for TST-0249: UTF-8 output on a legacy cp1252 console.

Does not patch tools/command-center. Production print() is observed, not rebuilt.
Declared catalog schema receipt.schema.json#/$defs/ux_report is absent; this
harness emits a local ux_report.
"""
from __future__ import annotations

import hashlib
import io
import json
import locale
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS_CC = REPO / "tools" / "command-center"
LIVE_CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
FIXTURE_REL = "command-center/p2-wave/probes/TST-0249/fixtures/nonascii-catalog.json"
CLOSE_REL = "tools/command-center/close.py"
UNIT = "TST-0249"
SENTINEL = "SUCCESS:TST-0249"
# Fallback that would satisfy "no exception and a legible fallback". Production
# does not configure stdout this way; recorded as recommended, not claimed.
RECOMMENDED_FALLBACK = "backslashreplace"
CP1252_HOLES = (0x81, 0x8D, 0x8F, 0x90, 0x9D)

if str(TOOLS_CC) not in sys.path:
    sys.path.insert(0, str(TOOLS_CC))
import catalog as cat  # noqa: E402
import close as cc_close  # noqa: E402


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def hex_preview(raw: bytes, n: int = 96) -> str:
    h = raw[:n].hex()
    return h if len(raw) <= n else h + "..."


def codepoints(text: str) -> list[str]:
    return [f"U+{ord(ch):04X}" for ch in text if ord(ch) > 127]


def expected_list_text(catalog_path: Path) -> str:
    catalog = cat.load(catalog_path)
    lines = cc_close.list_items(catalog, None, False)
    footer = (
        f"SUCCESS:cc-close listed open={len(cat.open_items(catalog))} "
        f"total={len(cat.items(catalog))}"
    )
    return "\n".join(list(lines) + [footer]) + "\n"


def emit_through_console(text: str, encoding: str, errors: str) -> dict[str, Any]:
    buf = io.BytesIO()
    wrapper = io.TextIOWrapper(buf, encoding=encoding, errors=errors, newline="\n")
    try:
        wrapper.write(text)
        wrapper.flush()
        raw = buf.getvalue()
        return {
            "ok": True,
            "encoding": encoding,
            "errors": errors,
            "exc_type": None,
            "exc_msg": None,
            "byte_count": len(raw),
            "sha256": sha256_bytes(raw),
            "hex_preview": hex_preview(raw),
            "raw": raw,
        }
    except UnicodeError as exc:
        try:
            wrapper.flush()
        except Exception:
            pass
        raw = buf.getvalue()
        return {
            "ok": False,
            "encoding": encoding,
            "errors": errors,
            "exc_type": type(exc).__name__,
            "exc_msg": str(exc),
            "byte_count": len(raw),
            "sha256": sha256_bytes(raw),
            "hex_preview": hex_preview(raw),
            "raw": raw,
        }
    finally:
        try:
            wrapper.detach()
        except Exception:
            pass


def run_close_list(catalog_rel: str, pythonioencoding: str | None) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if pythonioencoding is None:
        env.pop("PYTHONIOENCODING", None)
    else:
        env["PYTHONIOENCODING"] = pythonioencoding
    try:
        proc = subprocess.run(
            [sys.executable, "-B", str(REPO / CLOSE_REL), "--list", "--catalog", catalog_rel],
            cwd=str(REPO),
            env=env,
            capture_output=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return {
            "command": f"PYTHONIOENCODING={pythonioencoding} python3 -B {CLOSE_REL} --list --catalog {catalog_rel}",
            "pythonioencoding": pythonioencoding,
            "exit_code": 124,
            "stdout_byte_count": 0,
            "stdout_sha256": sha256_bytes(b""),
            "stdout_hex_preview": "",
            "stderr_preview": "TIMEOUT",
            "unicode_encode_error": False,
            "raw_stdout": b"",
        }
    stderr = (proc.stderr or b"").decode("utf-8", errors="replace")
    stdout = proc.stdout or b""
    return {
        "command": (
            f"PYTHONIOENCODING={pythonioencoding} python3 -B {CLOSE_REL} "
            f"--list --catalog {catalog_rel}"
        ),
        "pythonioencoding": pythonioencoding,
        "exit_code": proc.returncode,
        "stdout_byte_count": len(stdout),
        "stdout_sha256": sha256_bytes(stdout),
        "stdout_hex_preview": hex_preview(stdout),
        "stderr_preview": stderr[-800:],
        "unicode_encode_error": "UnicodeEncodeError" in stderr,
        "raw_stdout": stdout,
    }


def regression_seed(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    utf8_exc = None
    try:
        raw.decode("utf-8")
        utf8_ok = True
    except UnicodeDecodeError as exc:
        utf8_ok = False
        utf8_exc = str(exc)
    hole_offsets = {
        f"0x{b:02x}": raw.find(bytes([b])) for b in CP1252_HOLES if bytes([b]) in raw
    }
    first_hole = min((off for off in hole_offsets.values() if off >= 0), default=-1)
    seq_hex = None
    char_name = None
    if first_hole >= 2:
        seq = raw[first_hole - 2 : first_hole + 1]
        seq_hex = seq.hex()
        try:
            char_name = f"U+{ord(seq.decode('utf-8')):04X}"
        except UnicodeDecodeError:
            char_name = None
    cp_exc = None
    cp_ok = False
    try:
        raw.decode("cp1252")
        cp_ok = True
    except UnicodeDecodeError as exc:
        cp_exc = {
            "type": type(exc).__name__,
            "encoding": exc.encoding,
            "reason": exc.reason,
            "start": exc.start,
            "end": exc.end,
            "undefined_byte": f"0x{raw[exc.start]:02x}" if exc.start < len(raw) else None,
        }
    return {
        "path": path.relative_to(REPO).as_posix() if path.is_relative_to(REPO) else str(path),
        "byte_count": len(raw),
        "sha256": sha256_bytes(raw),
        "utf8_ok": utf8_ok,
        "utf8_exc": utf8_exc,
        "cp1252_ok": cp_ok,
        "cp1252_raises": (not cp_ok) and bool(cp_exc) and cp_exc["type"] == "UnicodeDecodeError",
        "cp1252_exc": cp_exc,
        "hole_first_offsets": hole_offsets,
        "utf8_sequence_at_hole_hex": seq_hex,
        "unicode_at_hole": char_name,
        "codec": "cp1252",
        "errors": "strict",
        "note": (
            "On this Linux box locale encoding is not cp1252; the seed names "
            "the cp1252 codec explicitly (the Windows cp1252-console default)."
        ),
    }


def public_capture(row: dict[str, Any]) -> dict[str, Any]:
    out = {k: v for k, v in row.items() if k != "raw"}
    return out


def public_proc(row: dict[str, Any]) -> dict[str, Any]:
    out = {k: v for k, v in row.items() if k != "raw_stdout"}
    return out


def measure() -> dict[str, Any]:
    fixture = REPO / FIXTURE_REL
    live = REPO / LIVE_CATALOG_REL
    payload = expected_list_text(fixture)
    utf8_a = emit_through_console(payload, "utf-8", "strict")
    utf8_b = emit_through_console(payload, "utf-8", "strict")
    encoded = payload.encode("utf-8")
    cp_strict = emit_through_console(payload, "cp1252", "strict")
    cp_fallback = emit_through_console(payload, "cp1252", RECOMMENDED_FALLBACK)
    proc_utf8_a = run_close_list(FIXTURE_REL, "utf-8")
    proc_utf8_b = run_close_list(FIXTURE_REL, "utf-8")
    proc_cp = run_close_list(FIXTURE_REL, "cp1252")
    seed = regression_seed(live)
    seed_fixture = regression_seed(fixture)

    utf8_byte_exact = (
        utf8_a["ok"]
        and utf8_b["ok"]
        and utf8_a["raw"] == utf8_b["raw"]
        and utf8_a["raw"] == encoded
    )
    proc_utf8_byte_exact = (
        proc_utf8_a["exit_code"] == 0
        and proc_utf8_b["exit_code"] == 0
        and proc_utf8_a["raw_stdout"] == proc_utf8_b["raw_stdout"]
        and proc_utf8_a["raw_stdout"] == encoded
    )
    production_no_exception = proc_cp["exit_code"] == 0 and not proc_cp["unicode_encode_error"]
    production_fallback = None  # close.py print() does not declare an error handler
    ux_pass = bool(
        production_no_exception
        and production_fallback
        and cp_fallback["ok"]
    )
    # backslashreplace of ≥ is b'\\u2265'; of ⭐ (BMP U+2B50) is b'\\u2b50'.
    fallback_legible = bool(
        cp_fallback["ok"]
        and b"\\u2265" in cp_fallback["raw"]
        and b"\\u2b50" in cp_fallback["raw"]
    )

    return {
        "unit_id": UNIT,
        "sentinel": SENTINEL,
        "environment": {
            "platform": sys.platform,
            "locale_preferredencoding": locale.getpreferredencoding(False),
            "parent_stdout_encoding": getattr(sys.stdout, "encoding", None),
            "simulated_console": "cp1252",
            "pythonioencoding_unset_would_be": getattr(sys.stdout, "encoding", None),
        },
        "subject": {
            "cli": CLOSE_REL,
            "argv": ["--list", "--catalog", FIXTURE_REL],
            "fixture": FIXTURE_REL,
            "live_catalog": LIVE_CATALOG_REL,
            "non_ascii_in_payload": codepoints(payload),
            "payload_sha256": sha256_bytes(payload.encode("utf-8")),
            "hud_rule": "rules/common/bash-hud-and-terminal-emit.md",
            "hud_rule_present": (REPO / "rules/common/bash-hud-and-terminal-emit.md").is_file(),
        },
        "both_states": {
            "check": "same list payload on a UTF-8 console is byte-exact across two captures and equals text.encode('utf-8')",
            "utf8_two_captures_identical": utf8_a["raw"] == utf8_b["raw"],
            "utf8_matches_encode": utf8_a["raw"] == encoded,
            "utf8_byte_exact": utf8_byte_exact,
            "utf8_sha256": utf8_a["sha256"],
            "utf8_byte_count": utf8_a["byte_count"],
            "utf8_hex_preview": utf8_a["hex_preview"],
            "subprocess_utf8_two_runs_identical": proc_utf8_a["raw_stdout"] == proc_utf8_b["raw_stdout"],
            "subprocess_utf8_matches_encode": proc_utf8_a["raw_stdout"] == encoded,
            "subprocess_utf8_byte_exact": proc_utf8_byte_exact,
            "subprocess_utf8_exit_a": proc_utf8_a["exit_code"],
            "subprocess_utf8_exit_b": proc_utf8_b["exit_code"],
            "subprocess_utf8_sha256": proc_utf8_a["stdout_sha256"],
        },
        "cp1252_console": {
            "in_process_strict": public_capture(cp_strict),
            "in_process_recommended_fallback": public_capture(cp_fallback),
            "subprocess": public_proc(proc_cp),
            "production_declares_fallback": production_fallback,
            "recommended_fallback": RECOMMENDED_FALLBACK,
            "recommended_fallback_ok": cp_fallback["ok"],
            "recommended_fallback_legible": fallback_legible,
        },
        "regression_seed": seed,
        "fixture_decode_seed": seed_fixture,
        "ux_pass": ux_pass,
        "production_no_exception": production_no_exception,
        "chosen_fallback": production_fallback,
        "controls": {
            "strict_cp1252_raises": (not cp_strict["ok"])
            and cp_strict["exc_type"] == "UnicodeEncodeError",
            "utf8_silent": utf8_byte_exact,
            "live_catalog_cp1252_decode_raises": seed["cp1252_raises"],
            "live_catalog_utf8_ok": seed["utf8_ok"],
        },
    }


def jsonable(measure_row: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(measure_row, sort_keys=True))


def main() -> int:
    row = jsonable(measure())
    print(json.dumps(row, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
