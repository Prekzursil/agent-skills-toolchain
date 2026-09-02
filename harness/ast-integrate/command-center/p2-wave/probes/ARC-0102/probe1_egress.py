#!/usr/bin/env python3
"""Probe 1: egress control.

Block network, assert the registry validator still passes, and prove the block
itself works by a known-network operation (local HTTP) that succeeds without
the block and fails with it. Online (egress allowed) and offline (egress
blocked) suite fingerprints must match.
"""
from __future__ import annotations

import json
import socket
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import schema_resolver as SR  # noqa: E402

OUT = HERE / "probe1-egress.raw.json"


class _OkHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *_args) -> None:
        return


class EgressGuard:
    """Fail closed at socket connect / DNS / create_connection."""

    def __init__(self) -> None:
        self._connect = socket.socket.connect
        self._connect_ex = socket.socket.connect_ex
        self._create_connection = socket.create_connection
        self._getaddrinfo = socket.getaddrinfo

    def __enter__(self) -> "EgressGuard":
        def blocked_connect(_self, _address, *_a, **_k):
            raise OSError(101, "ARC-0102 egress blocked")

        def blocked_connect_ex(_self, _address, *_a, **_k):
            return 101

        def blocked_cc(*_a, **_k):
            raise OSError(101, "ARC-0102 egress blocked")

        def blocked_dns(*_a, **_k):
            raise OSError(101, "ARC-0102 egress blocked")

        socket.socket.connect = blocked_connect  # type: ignore[method-assign]
        socket.socket.connect_ex = blocked_connect_ex  # type: ignore[method-assign]
        socket.create_connection = blocked_cc  # type: ignore[assignment]
        socket.getaddrinfo = blocked_dns  # type: ignore[assignment]
        return self

    def __exit__(self, *_exc) -> None:
        socket.socket.connect = self._connect  # type: ignore[method-assign]
        socket.socket.connect_ex = self._connect_ex  # type: ignore[method-assign]
        socket.create_connection = self._create_connection
        socket.getaddrinfo = self._getaddrinfo


def _http_get(url: str) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=2) as resp:
            body = resp.read()
        return True, body.decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001 — the control records whatever fails
        if isinstance(exc, urllib.error.URLError):
            return False, f"URLError:{exc.reason!r}"
        return False, f"{type(exc).__name__}:{exc}"


def main() -> int:
    pin = SR.assert_pin()
    store = SR.build_store()
    ids = SR.canonical_ids(store)

    online = SR.run_suite(store)
    refuse_online = SR.refuse_unregistered_ref(store)
    catalog = SR.catalog_output_schema_offline(store)

    server = HTTPServer(("127.0.0.1", 0), _OkHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}/"
    try:
        unblocked_ok, unblocked_body = _http_get(url)
        with EgressGuard():
            blocked_ok, blocked_err = _http_get(url)
            offline = SR.run_suite(store)
            refuse_offline = SR.refuse_unregistered_ref(store)
            catalog_blocked = SR.catalog_output_schema_offline(store)
        restored_ok, restored_body = _http_get(url)
    finally:
        server.shutdown()
        server.server_close()

    identical = online["fingerprint"] == offline["fingerprint"]
    block_works = unblocked_ok and (not blocked_ok) and restored_ok
    refuse_ok = bool(refuse_online.get("refused")) and bool(
        refuse_offline.get("refused")
    )
    catalog_identical = (
        catalog.get("ok") is True
        and catalog_blocked.get("ok") is True
        and catalog.get("resolved_url") == catalog_blocked.get("resolved_url")
    )

    doc = {
        "pin": pin,
        "canonical_ids": ids,
        "canonical_id_count": len(ids),
        "has_identity": SR.IDENTITY_ID in ids,
        "has_envelope": SR.ENVELOPE_ID in ids,
        "has_case": SR.CASE_ID in ids,
        "has_draft_2020_12": "https://json-schema.org/draft/2020-12/schema" in ids,
        "online": online,
        "offline": offline,
        "identical": identical,
        "refuse_unregistered_online": refuse_online,
        "refuse_unregistered_offline": refuse_offline,
        "catalog_output_schema_offline": catalog,
        "catalog_output_schema_offline_blocked": catalog_blocked,
        "catalog_identical": catalog_identical,
        "block_control": {
            "url": url,
            "unblocked_ok": unblocked_ok,
            "unblocked_body": unblocked_body,
            "blocked_ok": blocked_ok,
            "blocked_error": blocked_err,
            "restored_ok": restored_ok,
            "restored_body": restored_body,
            "block_discriminates": block_works,
        },
    }
    OUT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    if not online["ok"] or not offline["ok"]:
        print("FAILED:ARC-0102-probe1 suite mismatches", online["mismatches"], offline["mismatches"])
        return 1
    if not identical:
        print("FAILED:ARC-0102-probe1 online/offline fingerprints differ")
        return 1
    if not block_works:
        print("FAILED:ARC-0102-probe1 egress block does not discriminate")
        print(json.dumps(doc["block_control"]))
        return 1
    if not refuse_ok:
        print("FAILED:ARC-0102-probe1 unregistered $ref was not refused")
        return 1
    if SR.ENVELOPE_ID not in ids or SR.CASE_ID not in ids:
        print("FAILED:ARC-0102-probe1 canonical ids missing")
        return 1
    if not catalog.get("ok") or not catalog_identical:
        print("FAILED:ARC-0102-probe1 catalog output_schema did not resolve offline")
        print(json.dumps({k: catalog.get(k) for k in (
            "ok", "garbage_rejected", "empty_rejected", "looks_like_receipt_core",
            "empty_messages", "resolved_url",
        )}))
        print("catalog_identical", catalog_identical)
        return 1

    print(
        "canonical_ids="
        + str(len(ids))
        + " identical="
        + str(identical)
        + " block_discriminates="
        + str(block_works)
        + " refuse_unregistered="
        + str(refuse_ok)
        + " suite_ok="
        + str(online["ok"])
        + " catalog_offline="
        + str(catalog.get("ok"))
        + " catalog_identical="
        + str(catalog_identical)
    )
    print("SUCCESS:ARC-0102-probe1 egress control offline-equals-online")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
