#!/usr/bin/env python3
"""Probe 1: both-states — genuine JSON accepted; HTML 200 interstitial rejected.

Rejection is content-type + schema, not HTTP status. The error names the
unexpected content-type. The on-disk index mtime/bytes are unchanged.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(HERE))

from marketplace.http_registry import (  # noqa: E402
    RegistryFetchClient,
    SchemaValidationError,
    UnexpectedContentTypeError,
)
from harness import (  # noqa: E402
    FixtureServer,
    error_names_content_type,
    index_unchanged,
    seed_index,
    stat_index,
)

ART = REPO / "command-center/receipts/TST-0134.json"
SENTINEL = "SUCCESS:TST-0134"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0134-probe1 {msg}")
    return 1


def main() -> int:
    client = RegistryFetchClient()
    srv = FixtureServer()
    err_text = ""
    err_type = ""
    before: dict = {}
    try:
        with tempfile.TemporaryDirectory(prefix="tst0134-p1-") as tmp:
            genuine_path = Path(tmp) / "genuine.json"
            ok = client.fetch_index(srv.genuine_url, genuine_path)
            if ok.status != 200 or not genuine_path.is_file():
                return fail("genuine JSON was not accepted")
            if not ok.payload.get("ok") or "items" not in ok.payload:
                return fail("genuine payload missing registry fields")

            interstitial_path = Path(tmp) / "index.json"
            before = seed_index(interstitial_path)
            rejected = False
            try:
                client.fetch_index(srv.interstitial_url, interstitial_path)
            except UnexpectedContentTypeError as exc:
                rejected = True
                err_text = str(exc)
                err_type = type(exc).__name__
                if not error_names_content_type(exc):
                    return fail(f"error did not name content-type: {err_text}")
                if "text/html" not in err_text.lower() and "text/html" not in (
                    exc.content_type or ""
                ).lower():
                    return fail(f"error did not name text/html: {err_text}")
            except Exception as exc:  # noqa: BLE001
                return fail(
                    f"interstitial raised {type(exc).__name__} instead of "
                    f"UnexpectedContentTypeError: {exc}"
                )
            after = stat_index(interstitial_path)
            if not rejected:
                return fail("interstitial HTTP 200 HTML was accepted")
            if not index_unchanged(before, after):
                return fail(f"index mutated on reject before={before} after={after}")

            schema_hit = False
            try:
                client.fetch_index(srv.bad_schema_url, Path(tmp) / "schema.json")
            except SchemaValidationError:
                schema_hit = True
            except Exception as exc:  # noqa: BLE001
                return fail(f"bad-schema unexpected {type(exc).__name__}: {exc}")
            if not schema_hit:
                return fail("schema layer silent on HTTP 200 JSON that fails index_page")
    finally:
        srv.close()

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel absent")

    out = {
        "genuine_accepted": True,
        "interstitial_rejected": True,
        "error_type": err_type,
        "error": err_text,
        "index_mtime_unchanged": True,
        "index_sha256_unchanged": True,
        "schema_layer_fired": True,
        "pass": True,
        "probe": "probe1-both-states",
        "unit_id": "TST-0134",
    }
    print(json.dumps(out, sort_keys=True))
    print(f"genuine accepted interstitial rejected err={err_type}")
    print(f"index unchanged mtime_ns={before.get('mtime_ns')}")
    print("SUCCESS:TST-0134-probe1 both-states content-type rejection")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
