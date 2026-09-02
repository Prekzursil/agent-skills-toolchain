#!/usr/bin/env python3
"""Probe 1: OSV over lockfiles; known-present advisory must be reported."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from inventory import CONTROL_LOCK, inventory  # noqa: E402
from snapshot import COMPLETION_SENTINEL, OUT, report_of  # noqa: E402
from sources import (  # noqa: E402
    CONTROL_ADVISORY,
    CONTROL_ECOSYSTEM,
    CONTROL_PACKAGE,
    CONTROL_VERSION,
    osv_query,
    osv_scanner_binary,
)

ART = REPO / OUT


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0023-probe1 {msg}")
    return 1


def main() -> int:
    binary = osv_scanner_binary()
    inv = inventory()
    admitted = [row["path"] for row in inv["admitted"]]
    if CONTROL_LOCK not in admitted:
        return fail(f"control lockfile not admitted: {CONTROL_LOCK}")
    live = osv_query(CONTROL_PACKAGE, CONTROL_VERSION, CONTROL_ECOSYSTEM)
    ids = set(live.get("ids") or []) | set(live.get("osv_ids") or [])
    reported = CONTROL_ADVISORY in ids
    payload = {
        "probe": "probe1-osv-lockfiles",
        "instrument": "api.osv.dev/v1/query",
        "osv_scanner_binary": binary,
        "osv_ok": bool(live.get("ok")),
        "osv_http": live.get("http_status"),
        "control_advisory": CONTROL_ADVISORY,
        "osv_reported": reported,
        "osv_ids": live.get("ids") or [],
        "admitted_lockfiles": admitted,
    }
    print(json.dumps(payload, sort_keys=True))
    if not live.get("ok"):
        return fail(f"OSV query http={live.get('http_status')}")
    if not reported:
        return fail(f"{CONTROL_ADVISORY} absent from OSV for lodash@4.17.20")
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"artifact state={doc.get('state')}")
    if COMPLETION_SENTINEL not in ART.read_text(encoding="utf-8"):
        return fail("completion sentinel absent")
    rep = report_of(doc)
    ctrl = rep.get("known_present_control") or doc.get("known_present_control") or {}
    if ctrl.get("osv_reported") is not True:
        return fail("artifact osv_reported is not true")
    if CONTROL_ADVISORY not in set(ctrl.get("osv_ids") or []):
        return fail("artifact missing control advisory in osv_ids")
    decay = rep.get("decay") or doc.get("decay") or {}
    expires = decay.get("must_requery_after")
    queried = decay.get("query_timestamp")
    if not expires or not queried:
        return fail("decay timestamps missing")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if expires <= queried:
        return fail("must_requery_after is not after query_timestamp")
    if expires <= now:
        return fail("stored result has decayed; re-query required")
    if decay.get("ttl_hours") != 24:
        return fail("ttl_hours is not 24")
    src = ((rep.get("sources") or doc.get("sources") or {}).get("osv")) or {}
    if src.get("queried") is not True:
        return fail("sources.osv.queried is not true")
    print(
        "SUCCESS:AUD-0023-probe1 "
        f"osv_reported={reported} expires={expires}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
