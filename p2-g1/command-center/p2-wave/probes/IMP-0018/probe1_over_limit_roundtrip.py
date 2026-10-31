#!/usr/bin/env python3
"""Named probe 1: 40,000-character payload round-trips through the marshaller.

Signal 1 of IMP-0018. The child process reports the received byte count.
The same payload's inline command-line length is recorded as exceeding 32,767.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

import arg_marshalling as am  # noqa: E402

ART = REPO / "command-center" / "receipts" / "IMP-0018.json"
PAYLOAD_N = 40_000


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
    if doc.get("unit_id") != "IMP-0018":
        return f"unit_id {doc.get('unit_id')}"
    return None


def main() -> int:
    bad = _receipt_ok()
    if bad:
        print(f"FAILED:IMP-0018-probe1 {bad}")
        return 1

    payload = am.make_over_limit_payload(PAYLOAD_N)
    data = payload.encode("utf-8")
    want_sha = hashlib.sha256(data).hexdigest()
    result = am.spawn_payload(payload)
    if result.returncode != 0:
        print(
            f"FAILED:IMP-0018-probe1 child rc={result.returncode} err={result.stderr!r}"
        )
        return 1
    if result.transport != "payload-file":
        print(f"FAILED:IMP-0018-probe1 expected payload-file got {result.transport}")
        return 1
    if result.child_reported_bytes != PAYLOAD_N:
        print(
            "FAILED:IMP-0018-probe1 child reported "
            f"{result.child_reported_bytes} want {PAYLOAD_N}"
        )
        return 1
    if result.child_source != "file":
        print(f"FAILED:IMP-0018-probe1 child source {result.child_source}")
        return 1
    if result.child_sha256 != want_sha:
        print("FAILED:IMP-0018-probe1 sha256 mismatch")
        return 1
    if result.inline_cmdline_length <= am.WINDOWS_CREATEPROCESS_LIMIT:
        print(
            "FAILED:IMP-0018-probe1 inline length "
            f"{result.inline_cmdline_length} not over cap"
        )
        return 1
    if result.argv_cmdline_length > am.CONSERVATIVE_THRESHOLD:
        print(
            "FAILED:IMP-0018-probe1 marshalled argv still long "
            f"{result.argv_cmdline_length}"
        )
        return 1
    if not result.cleaned or result.payload_path_exists_after:
        print("FAILED:IMP-0018-probe1 temp file leaked after success")
        return 1

    payload_out = {
        "argv_cmdline_length": result.argv_cmdline_length,
        "child_reported_bytes": result.child_reported_bytes,
        "child_sha256": result.child_sha256,
        "child_source": result.child_source,
        "cleaned": result.cleaned,
        "file_mode": result.file_mode,
        "inline_cmdline_length": result.inline_cmdline_length,
        "pass": True,
        "payload_chars": PAYLOAD_N,
        "probe": "probe1-over-limit-roundtrip",
        "threshold": am.CONSERVATIVE_THRESHOLD,
        "transport": result.transport,
        "unit_id": "IMP-0018",
        "windows_createprocess_limit": am.WINDOWS_CREATEPROCESS_LIMIT,
    }
    print(json.dumps(payload_out, sort_keys=True))
    print(
        f"roundtrip_bytes={result.child_reported_bytes} "
        f"transport={result.transport} "
        f"inline_len={result.inline_cmdline_length} "
        f"argv_len={result.argv_cmdline_length} "
        f"cleaned={result.cleaned}"
    )
    print("SUCCESS:IMP-0018-probe1 over-limit payload round-trips via payload-file")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
