#!/usr/bin/env python3
"""Live advisory-database client for CNF-0153.

osv-scanner is not installed on this worktree (measured exit 127). Queries go
to api.osv.dev. A second source (api.github.com/advisories) is the reviewer
egress. HTTP 429 backs off with jitter; HTTP 529 does not self-throttle.
Two strikes on the same unreachable source raise BlockedExternal.
"""
from __future__ import annotations

import json
import random
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
OSV_QUERY = "https://api.osv.dev/v1/query"
OSV_BATCH = "https://api.osv.dev/v1/querybatch"
GHSA_URL = "https://api.github.com/advisories"
UA = "CNF-0153-advisory-reprobe/1.0"


class BlockedExternal(RuntimeError):
    def __init__(self, message: str, prerequisite: str) -> None:
        super().__init__(message)
        self.prerequisite = prerequisite


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def classify_exit(returncode: int) -> str:
    if returncode == 127:
        return "tool-not-installed"
    if returncode == 0:
        return "clean"
    if returncode == 1:
        return "findings"
    return f"other:{returncode}"


def missing_osv_scanner_exit() -> int:
    p = subprocess.run(
        "osv-scanner --version",
        shell=True,
        capture_output=True,
        text=True,
    )
    return int(p.returncode)


def findings_to_exit(n_findings: int) -> int:
    return 1 if n_findings else 0


def _http_json(
    url: str,
    payload: dict | None = None,
    extra_headers: dict | None = None,
    timeout: float = 30.0,
) -> tuple[Any, dict]:
    headers = {
        "User-Agent": UA,
        "Accept": "application/json",
    }
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            meta = {
                "status": int(resp.status),
                "http_date": resp.headers.get("Date") or "",
                "url": url,
                "ratelimit_remaining": resp.headers.get("X-RateLimit-Remaining"),
            }
            return json.loads(raw.decode("utf-8") or "null"), meta
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        err = urllib.error.HTTPError(exc.url, exc.code, exc.reason, exc.headers, None)
        err._cnf_body = body  # type: ignore[attr-defined]
        raise err from None


def fetch_with_policy(do_fetch, source: str) -> tuple[Any, dict]:
    strikes = 0
    last: Exception | None = None
    while strikes < 2:
        try:
            return do_fetch()
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code == 429:
                time.sleep(0.4 + random.random() * 0.8)
                strikes += 1
                continue
            if exc.code == 529:
                # vendor-side; must NOT self-throttle
                strikes += 1
                continue
            raise
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            last = exc
            strikes += 1
            time.sleep(0.2 + random.random() * 0.4)
    raise BlockedExternal(
        f"two strikes on unreachable source {source}: {type(last).__name__}: {last}",
        prerequisite=source,
    )


def parse_npm_lockfile(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    packages = data.get("packages") or {}
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for key, meta in packages.items():
        if not isinstance(meta, dict):
            continue
        if meta.get("link"):
            continue
        version = meta.get("version")
        if not version:
            continue
        if key == "" or not str(key).startswith("node_modules/"):
            continue
        name = str(key).split("node_modules/")[-1]
        ident = (name, str(version))
        if ident in seen:
            continue
        seen.add(ident)
        out.append(
            {
                "name": name,
                "version": str(version),
                "ecosystem": "npm",
                "lockfile": str(path),
            }
        )
    return out


def _severity_from_osv(vuln: dict) -> str:
    db = vuln.get("database_specific") or {}
    raw = str(db.get("severity") or "").upper()
    if raw in {"CRITICAL", "HIGH", "MEDIUM", "MODERATE", "LOW"}:
        return "MEDIUM" if raw == "MODERATE" else raw
    for row in vuln.get("severity") or []:
        if not isinstance(row, dict):
            continue
        score = str(row.get("score") or "")
        try:
            # CVSS vector or numeric
            if score.startswith("CVSS:"):
                continue
            n = float(score.split("/")[0])
        except ValueError:
            continue
        if n >= 9.0:
            return "CRITICAL"
        if n >= 7.0:
            return "HIGH"
        if n >= 4.0:
            return "MEDIUM"
        return "LOW"
    return "UNKNOWN"


def _finding(vuln: dict, pkg: dict, source: str) -> dict:
    vid = str(vuln.get("id") or vuln.get("ghsa_id") or "")
    return {
        "id": vid,
        "severity": _severity_from_osv(vuln) if source == "osv" else str(vuln.get("severity") or "UNKNOWN").upper(),
        "affected_artifact": f"{pkg['name']}@{pkg['version']}",
        "package": pkg["name"],
        "version": pkg["version"],
        "ecosystem": pkg.get("ecosystem") or "npm",
        "lockfile": pkg.get("lockfile") or "",
        "summary": str(vuln.get("summary") or "")[:240],
        "source": source,
        "aliases": list(vuln.get("aliases") or ([vuln["cve_id"]] if vuln.get("cve_id") else [])),
        "withdrawn": bool(vuln.get("withdrawn")),
    }


def query_osv_one(name: str, version: str, ecosystem: str = "npm") -> tuple[list[dict], dict]:
    pkg = {"name": name, "version": version, "ecosystem": ecosystem, "lockfile": ""}

    def _do() -> tuple[Any, dict]:
        return _http_json(
            OSV_QUERY,
            payload={"package": {"name": name, "ecosystem": ecosystem}, "version": version},
        )

    data, meta = fetch_with_policy(_do, source="api.osv.dev")
    vulns = list((data or {}).get("vulns") or [])
    findings = [_finding(v, pkg, "osv") for v in vulns if isinstance(v, dict)]
    meta = dict(meta)
    meta["query_timestamp_utc"] = utc_now()
    meta["package"] = f"{name}@{version}"
    return findings, meta


def query_osv_batch(packages: list[dict], chunk: int = 80) -> tuple[list[dict], dict]:
    if not packages:
        return [], {
            "status": 200,
            "http_date": "",
            "url": OSV_BATCH,
            "query_timestamp_utc": utc_now(),
            "n_queries": 0,
        }
    all_findings: list[dict] = []
    last_meta: dict = {}
    for i in range(0, len(packages), chunk):
        batch = packages[i : i + chunk]
        payload = {
            "queries": [
                {
                    "package": {"name": p["name"], "ecosystem": p.get("ecosystem") or "npm"},
                    "version": p["version"],
                }
                for p in batch
            ]
        }

        def _do(pl=payload) -> tuple[Any, dict]:
            return _http_json(OSV_BATCH, payload=pl)

        data, meta = fetch_with_policy(_do, source="api.osv.dev")
        last_meta = dict(meta)
        results = list((data or {}).get("results") or [])
        for pkg, res in zip(batch, results):
            if not isinstance(res, dict):
                continue
            for v in res.get("vulns") or []:
                if isinstance(v, dict) and v.get("id"):
                    all_findings.append(_finding(v, pkg, "osv"))
    last_meta["query_timestamp_utc"] = utc_now()
    last_meta["n_queries"] = len(packages)
    last_meta["n_findings"] = len(all_findings)
    return all_findings, last_meta


def query_ghsa(name: str, version: str, ecosystem: str = "npm") -> tuple[list[dict], dict]:
    eco = {"npm": "npm", "PyPI": "pip", "Go": "go"}.get(ecosystem, ecosystem.lower())
    url = f"{GHSA_URL}?ecosystem={eco}&affects={name}@{version}&per_page=100"
    pkg = {"name": name, "version": version, "ecosystem": ecosystem, "lockfile": ""}

    def _do() -> tuple[Any, dict]:
        return _http_json(
            url,
            extra_headers={"Accept": "application/vnd.github+json"},
        )

    data, meta = fetch_with_policy(_do, source="api.github.com/advisories")
    rows = data if isinstance(data, list) else []
    findings = []
    for v in rows:
        if not isinstance(v, dict):
            continue
        item = _finding(v, pkg, "ghsa")
        item["severity"] = str(v.get("severity") or "UNKNOWN").upper()
        item["cve_id"] = v.get("cve_id")
        item["withdrawn"] = bool(v.get("withdrawn_at"))
        findings.append(item)
    meta = dict(meta)
    meta["query_timestamp_utc"] = utc_now()
    meta["package"] = f"{name}@{version}"
    return findings, meta


def snapshot_id(meta: dict) -> str:
    """OSV query has no monotonic snapshot token; HTTP Date + UTC clock is the decay id."""
    http_date = str(meta.get("http_date") or "").strip()
    ts = str(meta.get("query_timestamp_utc") or utc_now())
    if http_date:
        return f"osv.dev/http-date:{http_date}|query:{ts}"
    return f"osv.dev/query:{ts}"
