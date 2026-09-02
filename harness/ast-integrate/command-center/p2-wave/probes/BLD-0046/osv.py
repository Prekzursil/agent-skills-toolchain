"""Live OSV advisory query with one transient retry.

A second failure is NOT-CHECKED with the endpoint named, never folded into CLEAN.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from classify import iso, utcnow

OSV_QUERY = "https://api.osv.dev/v1/query"
USER_AGENT = "BLD-0046-decaying-green-inventory"


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
                "ids": ids,
                "count": len(ids),
                "attempt": i,
                "query_timestamp": iso(utcnow()),
                "errors": errors,
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
        "ids": [],
        "count": 0,
        "attempt": attempts,
        "query_timestamp": iso(utcnow()),
        "classification": "NOT-CHECKED",
        "errors": errors,
        "error": None if last_exc is None else f"{type(last_exc).__name__}: {last_exc}",
    }


def github_run(run_id: int, *, timeout: int = 20) -> dict[str, Any]:
    """Date a stored CI green by resolving its Actions run. Retry once."""
    url = (
        "https://api.github.com/repos/Prekzursil/agent-skills-toolchain"
        f"/actions/runs/{run_id}"
    )
    errors: list[str] = []
    for i in range(1, 3):
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": USER_AGENT,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            created = body.get("created_at") or body.get("updated_at")
            if isinstance(created, str) and created.endswith("+00:00"):
                created = created[:-6] + "Z"
            if isinstance(created, str) and len(created) >= 20 and created[10] == "T":
                created = created[:19] + "Z"
            return {
                "ok": True,
                "endpoint": url,
                "run_id": run_id,
                "created_at": created,
                "conclusion": body.get("conclusion"),
                "name": body.get("name"),
                "attempt": i,
                "errors": errors,
            }
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
            json.JSONDecodeError,
            OSError,
        ) as exc:
            errors.append(f"attempt {i}: {type(exc).__name__}: {exc}")
            if i < 2:
                time.sleep(0.5)
    return {
        "ok": False,
        "endpoint": url,
        "run_id": run_id,
        "created_at": None,
        "classification": "NOT-CHECKED",
        "errors": errors,
    }
