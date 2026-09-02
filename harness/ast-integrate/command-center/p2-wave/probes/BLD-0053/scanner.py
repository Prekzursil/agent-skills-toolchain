"""Invoke a scanner binary; missing executable is exit 127, never CLEAN.

Author query uses OSV package+ecosystem+version (not purl). The independent
reviewer in scanner_reviewer.py re-queries the same fixture via purl.
"""
from __future__ import annotations

import errno
import json
import time
import urllib.error
import urllib.request
from typing import Any

from classify import classify_scanner_exit, naive_scanner_exit

MISSING_SCANNER = "osv-scanner-not-installed-bld0053"
OSV_QUERY = "https://api.osv.dev/v1/query"
USER_AGENT = "BLD-0053-supply-chain-gap-census"


def iso_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def invoke_scanner(binary: str, args: list[str] | None = None, timeout: int = 10) -> int:
    import subprocess

    try:
        proc = subprocess.run(
            [binary, *(args or ["--version"])],
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return int(proc.returncode)
    except FileNotFoundError:
        return 127
    except OSError as exc:
        if exc.errno == errno.ENOENT:
            return 127
        raise


def classify_missing_scanner(binary: str = MISSING_SCANNER) -> dict[str, Any]:
    code = invoke_scanner(binary)
    author = classify_scanner_exit(code)
    naive = naive_scanner_exit(code)
    return {
        "binary": binary,
        "returncode": code,
        "author": author,
        "naive": naive,
        "not_clean": author != "CLEAN",
        "pass": code == 127 and author == "TOOL-MISSING" and naive == "CLEAN",
    }


def query_osv(
    name: str,
    ecosystem: str,
    version: str,
    *,
    attempts: int = 2,
    timeout: int = 20,
) -> dict[str, Any]:
    payload = json.dumps(
        {"package": {"name": name, "ecosystem": ecosystem}, "version": version}
    ).encode("utf-8")
    errors: list[str] = []
    last_exc: Exception | None = None
    for i in range(1, attempts + 1):
        req = urllib.request.Request(
            OSV_QUERY,
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
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
                "package": name,
                "ecosystem": ecosystem,
                "version": version,
                "method": "package-version",
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
        "package": name,
        "ecosystem": ecosystem,
        "version": version,
        "method": "package-version",
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
