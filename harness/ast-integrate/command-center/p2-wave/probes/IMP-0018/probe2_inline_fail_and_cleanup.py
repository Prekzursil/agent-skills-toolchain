#!/usr/bin/env python3
"""Named probe 2: independent reviewer of inline 206 + tempfile permissions/cleanup.

Signal 2 of IMP-0018. The SAME 40,000-character payload forced inline must raise
OS error 206 (CreateProcess cap) in this run. Restrictive 0600/0700 modes and
deletion on the injected-failure path are confirmed here, not only in probe 1.
"""
from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

import arg_marshalling as am  # noqa: E402

ART = REPO / "command-center" / "receipts" / "IMP-0018.json"
PAYLOAD_N = 40_000


def _boom(*_a, **_k):
    raise RuntimeError("injected-spawn-failure")


def _receipt_ok() -> str | None:
    if not ART.is_file() or ART.stat().st_size < 200:
        return "receipt missing"
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return f"receipt unparseable {exc}"
    if not isinstance(doc, dict):
        return "receipt not an object"
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return f"self-declared {doc.get('state')}"
    if "SUCCESS:IMP-0018" not in text:
        return "sentinel absent"
    notes = json.dumps(doc.get("reviewer") or {}) + text
    lowered = notes.lower()
    if "restrictive" not in lowered and "0600" not in notes and "0o600" not in notes:
        return "receipt does not name restrictive temp-file permissions"
    return None


def main() -> int:
    bad = _receipt_ok()
    if bad:
        print(f"FAILED:IMP-0018-probe2 {bad}")
        return 1

    payload = am.make_over_limit_payload(PAYLOAD_N)
    inline_len = am.windows_cmdline_length(am.default_prefix() + [payload])
    if inline_len <= am.WINDOWS_CREATEPROCESS_LIMIT:
        print(f"FAILED:IMP-0018-probe2 inline length {inline_len} not over cap")
        return 1

    marshalled = am.spawn_payload(payload)
    if marshalled.returncode != 0 or marshalled.child_reported_bytes != PAYLOAD_N:
        print("FAILED:IMP-0018-probe2 marshalled control did not round-trip")
        return 1

    raised = False
    errno = None
    winerror = None
    try:
        am.spawn_payload(payload, force_inline=True)
    except OSError as exc:
        raised = True
        errno = exc.errno
        winerror = getattr(exc, "winerror", None)
        if not am.is_createprocess_206(exc):
            print(f"FAILED:IMP-0018-probe2 wrong OSError {exc!r}")
            return 1
    if not raised:
        print("FAILED:IMP-0018-probe2 inline path did not fail")
        return 1

    marshaller = am.ArgMarshaller()
    prepared = marshaller.prepare(am.default_prefix(), payload)
    path = prepared.payload_path
    directory = prepared.payload_dir
    if not path or not os.path.isfile(path) or not directory:
        print("FAILED:IMP-0018-probe2 expected a live payload file before spawn")
        prepared.close()
        return 1
    file_mode = stat.S_IMODE(os.stat(path).st_mode)
    dir_mode = stat.S_IMODE(os.stat(directory).st_mode)
    world_bits = file_mode & 0o077
    if file_mode != 0o600 or world_bits != 0 or dir_mode != 0o700:
        prepared.close()
        print(
            f"FAILED:IMP-0018-probe2 modes file={oct(file_mode)} dir={oct(dir_mode)}"
        )
        return 1
    exploded = False
    try:
        marshaller.run(prepared, spawn=_boom)
    except RuntimeError as exc:
        exploded = True
        if "injected-spawn-failure" not in str(exc):
            print(f"FAILED:IMP-0018-probe2 unexpected spawn error {exc}")
            return 1
    if not exploded:
        print("FAILED:IMP-0018-probe2 injected spawn failure did not fire")
        return 1
    if os.path.exists(path) or os.path.isdir(directory):
        print("FAILED:IMP-0018-probe2 temp file survived the failure path")
        return 1

    payload_out = {
        "cleanup_on_failure": True,
        "dir_mode": dir_mode,
        "file_mode": file_mode,
        "inline_cmdline_length": inline_len,
        "inline_errno": errno,
        "inline_raised_206": True,
        "inline_winerror": winerror,
        "marshalled_bytes": marshalled.child_reported_bytes,
        "pass": True,
        "probe": "probe2-inline-fail-and-cleanup",
        "restrictive_permissions": True,
        "unit_id": "IMP-0018",
        "world_bits": world_bits,
    }
    print(json.dumps(payload_out, sort_keys=True))
    print(
        f"inline_206=True errno={errno} winerror={winerror} "
        f"file_mode={oct(file_mode)} dir_mode={oct(dir_mode)} "
        f"cleanup_on_failure=True"
    )
    print("SUCCESS:IMP-0018-probe2 inline 206 and tempfile cleanup confirmed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
