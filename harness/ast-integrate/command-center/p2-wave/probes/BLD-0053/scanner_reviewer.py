"""Independent reviewer: re-query OSV via purl, not package+ecosystem.

Catalog reviewer_requirement: an Anthropic-vendor reviewer re-runs the
scanner against the known-vulnerable fixture. This module is the second
query path (purl) so the overlap is not a same-call replay.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from scanner import OSV_QUERY, USER_AGENT, iso_now

KNOWN_VULN_PURL = "pkg:npm/lodash@4.17.20"


def query_osv_purl(
    purl: str = KNOWN_VULN_PURL,
    *,
    attempts: int = 2,
    timeout: int = 20,
) -> dict[str, Any]:
    payload = json.dumps({"package": {"purl": purl}}).encode("utf-8")
    errors: list[str] = []
    last_exc: Exception | None = None
    for i in range(1, attempts + 1):
        req = urllib.request.Request(
            OSV_QUERY,
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT + "-reviewer",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            vulns = body.get("vulns") or []
            ids = sorted(
                {
                    str(v.get("id"))
                    for v in vulns
                    if isinstance(v, dict) and v.get("id")
                }
            )
            return {
                "ok": True,
                "endpoint": OSV_QUERY,
                "purl": purl,
                "method": "purl",
                "finding_ids": ids,
                "finding_count": len(ids),
                "ids": ids,
                "count": len(ids),
                "attempt": i,
                "query_timestamp": iso_now(),
                "errors": errors,
                "status": "OK",
                "live": True,
            }
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
            json.JSONDecodeError,
            OSError,
        ) as exc:
            last_exc = exc
            errors.append(f"attempt {i}: {type(exc).__name__}: {exc}")
            if i < attempts:
                time.sleep(0.5)
    return {
        "ok": False,
        "endpoint": OSV_QUERY,
        "purl": purl,
        "method": "purl",
        "finding_ids": [],
        "finding_count": 0,
        "ids": [],
        "count": 0,
        "attempt": attempts,
        "query_timestamp": iso_now(),
        "classification": "NOT-CHECKED",
        "errors": errors,
        "error": None if last_exc is None else f"{type(last_exc).__name__}: {last_exc}",
        "status": "NOT-CHECKED",
        "live": False,
    }
