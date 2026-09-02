#!/usr/bin/env python3
"""Probe 1: live vendor reachability + mounted-server inventory (two signals).

READ-ONLY credential diagnosis. Never prints secret values.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import estate as E  # noqa: E402
from redact import PLANTED_SYNTHETIC, leak_hits, scanner_detects_plant  # noqa: E402

OUT = HERE / "probe1-reachability.raw.json"
DECLARED = ("anthropic", "openai")


def main() -> int:
    if not scanner_detects_plant():
        print("FAILED:CNL-0012-probe1 leak-scanner vacuous")
        return 1

    doc = E.measure()
    E.dump(OUT, doc)
    text = json.dumps(doc, sort_keys=True, ensure_ascii=True)
    hits = leak_hits(text)
    if hits:
        print("FAILED:CNL-0012-probe1 leak-names=" + ",".join(hits))
        return 1
    if PLANTED_SYNTHETIC in text:
        print("FAILED:CNL-0012-probe1 planted-synthetic leaked into measure")
        return 1

    vendors = doc.get("vendors") or {}
    missing = [v for v in DECLARED if v not in vendors]
    if missing:
        print("FAILED:CNL-0012-probe1 missing-declared-vendors=" + ",".join(missing))
        return 1

    for name in DECLARED:
        row = vendors[name]
        cred = row.get("credential") or {}
        if "present" not in cred or "prefix_class" not in cred:
            print("FAILED:CNL-0012-probe1 incomplete-credential-class " + name)
            return 1
        if "value" in cred or "secret" in cred or "token" in cred:
            print("FAILED:CNL-0012-probe1 credential-value-field " + name)
            return 1
        unauth = row.get("http_unauthenticated_models") or {}
        auth = row.get("http_authenticated_models") or {}
        net = row.get("network_tcp443") or {}
        if "ok" not in net:
            print("FAILED:CNL-0012-probe1 missing-tcp " + name)
            return 1
        if "status" not in unauth and "error" not in unauth:
            print("FAILED:CNL-0012-probe1 missing-http-unauth " + name)
            return 1
        if "status" not in auth and "error" not in auth:
            print("FAILED:CNL-0012-probe1 missing-http-auth " + name)
            return 1

    mcp = doc.get("mcp_inventory") or {}
    procs = doc.get("process_inventory") or {}
    if "server_names" not in mcp or "config_files" not in mcp:
        print("FAILED:CNL-0012-probe1 inventory-incomplete")
        return 1
    if "hits" not in procs:
        print("FAILED:CNL-0012-probe1 process-inventory-incomplete")
        return 1
    signals = doc.get("signals") or []
    if len(signals) < 2:
        print("FAILED:CNL-0012-probe1 need-two-signals")
        return 1

    print(
        "declared="
        + ",".join(DECLARED)
        + " anthropic_cred="
        + str(bool((vendors["anthropic"].get("credential") or {}).get("present")))
        + " openai_cred="
        + str(bool((vendors["openai"].get("credential") or {}).get("present")))
        + " anthropic_tcp="
        + str((vendors["anthropic"].get("network_tcp443") or {}).get("ok"))
        + " openai_tcp="
        + str((vendors["openai"].get("network_tcp443") or {}).get("ok"))
        + " anthropic_unauth="
        + str((vendors["anthropic"].get("http_unauthenticated_models") or {}).get("status"))
        + " openai_unauth="
        + str((vendors["openai"].get("http_unauthenticated_models") or {}).get("status"))
        + " anthropic_auth_err="
        + str((vendors["anthropic"].get("http_authenticated_models") or {}).get("error"))
        + " openai_auth_err="
        + str((vendors["openai"].get("http_authenticated_models") or {}).get("error"))
        + " mcp_servers="
        + str(len(mcp.get("server_names") or []))
        + " codex_mounted="
        + str(bool(mcp.get("codex_mounted")))
        + " session_vendor="
        + str((doc.get("session") or {}).get("vendor"))
        + " session_model="
        + str((doc.get("session") or {}).get("model_id"))
        + " leak_hits=0"
        + " signals="
        + "+".join(signals)
    )
    print("SUCCESS:CNL-0012-probe1 vendor reachability and mounted-server inventory")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
