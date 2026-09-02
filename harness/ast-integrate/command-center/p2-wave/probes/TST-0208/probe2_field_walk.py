#!/usr/bin/env python3
"""Probe 2: independent field-by-field walk of nested token + base64 blob.

Starts from a freshly minted payload, not the receipt narrative. After
structured redaction, every sensitive key must equal the marker and no
canary may remain in the object or in a decoded base64 JSON blob.
"""
from __future__ import annotations

import json
import secrets
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.lib import security as G  # noqa: E402

ART = REPO / "command-center/receipts/TST-0208.json"
SENTINEL = "SUCCESS:TST-0208"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0208-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel-absent")

    tok = f"tst0208-p2-tok-{secrets.token_hex(8)}-not-a-secret"
    inner = f"tst0208-p2-b64-{secrets.token_hex(8)}-not-a-secret"
    api = f"tst0208-p2-api-{secrets.token_hex(8)}-not-a-secret"
    pw = f"tst0208-p2-pw-{secrets.token_hex(8)}-not-a-secret"
    canaries = [tok, inner, api, pw]

    blob = G._b64_json({"password": inner, "scope": "probe2"})
    payload = {
        "username": "alice",
        "password": pw,
        "session": {"token": tok, "user": "bob"},
        "blob": blob,
        "items": [{"api_key": api, "id": 7}],
        "note": "innocuous text without credentials",
    }
    redacted = G.redact_structured(payload)
    walk = G.field_walk(redacted, canaries)
    sensitive = [r for r in walk if r.get("sensitive")]
    retaining = [r for r in walk if r.get("retains_secret")]
    if retaining:
        return fail(f"walk retained secret at {[r.get('path') for r in retaining]}")
    if len(sensitive) < 4:
        return fail(f"too few sensitive keys: {len(sensitive)}")
    if not all(r.get("is_redacted") for r in sensitive):
        return fail("a sensitive key was not the marker")
    if redacted.get("username") != "alice":
        return fail("username dropped")
    if (redacted.get("session") or {}).get("user") != "bob":
        return fail("nested user dropped")
    decoded = G._try_b64_utf8(redacted.get("blob") or "")
    inner_obj = G._try_json(decoded) if decoded else None
    if not isinstance(inner_obj, dict) or inner_obj.get("password") != G.REDACTED:
        return fail(f"base64 inner not redacted: {inner_obj!r}")
    if inner_obj.get("scope") != "probe2":
        return fail("base64 non-sensitive field dropped")
    if any(c in text for c in canaries):
        return fail("receipt contains probe canary")
    regex_blob = G.redact_raw_text(json.dumps(payload, separators=(",", ":")))
    regex_parsed = json.loads(regex_blob)
    regex_decoded = G._try_json(G._try_b64_utf8(regex_parsed.get("blob") or "") or "")
    if not isinstance(regex_decoded, dict) or regex_decoded.get("password") != inner:
        return fail("regex-only base64 bypass seed silent")

    live = G.run_required_controls()
    fails = G.control_failures(live)
    if fails:
        return fail("; ".join(fails))
    live_walk = live.get("field_walk") or {}
    if live_walk.get("n_retaining_secret") != 0:
        return fail("live field walk retaining")
    if not live_walk.get("all_sensitive_redacted"):
        return fail("live field walk incomplete")

    receipt_walk = (doc.get("live_controls") or {}).get("field_walk") or {}
    if receipt_walk.get("all_sensitive_redacted") is not True:
        return fail("receipt field_walk drift")
    if receipt_walk.get("n_retaining_secret") != 0:
        return fail("receipt field_walk retaining")
    receipt_blob = (doc.get("live_controls") or {}).get("base64_blob") or {}
    if receipt_blob.get("inner_password_redacted") is not True:
        return fail("receipt base64 inner not redacted")
    if receipt_blob.get("regex_only_retains_secret") is not True:
        return fail("receipt missing base64 regex-only bypass")

    out = {
        "probe": "probe2-field-walk",
        "unit_id": "TST-0208",
        "pass": True,
        "n_sensitive": len(sensitive),
        "n_retaining_secret": 0,
        "all_sensitive_redacted": True,
        "nested_token_redacted": True,
        "base64_inner_redacted": True,
        "regex_only_base64_bypass": True,
        "receipt_matches_live": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"sensitive={len(sensitive)} retaining=0 nested=redacted "
        "b64_inner=redacted regex_b64_bypass=yes"
    )
    print(
        "SUCCESS:TST-0208-probe2 field-by-field walk: no sensitive key retains "
        "its value; nested token and base64 blob redacted"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
