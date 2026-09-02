"""Independent advisory sources for AUD-0023: OSV and GitHub Advisory (via npm bulk)."""
from __future__ import annotations

import json
import os
import re
import shutil
import urllib.error
import urllib.request
from typing import Any

USER_AGENT = "AUD-0023-vuln-posture (ast-integrate local probe)"
OSV_QUERY = "https://api.osv.dev/v1/query"
OSV_BATCH = "https://api.osv.dev/v1/querybatch"
NPM_BULK = "https://registry.npmjs.org/-/npm/v1/security/advisories/bulk"
GHSA_RE = re.compile(r"GHSA-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}", re.I)

CONTROL_PACKAGE = "lodash"
CONTROL_VERSION = "4.17.20"
CONTROL_GOOD_VERSION = "4.17.21"
CONTROL_ECOSYSTEM = "npm"
CONTROL_ADVISORY = "GHSA-35jh-r3h4-6jhm"
ECOSYSTEM_MAP = {"npm": "npm", "pypi": "PyPI", "crates": "crates.io", "go": "Go"}


def http_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict | None = None,
    headers: dict | None = None,
    timeout: int = 45,
) -> tuple[int, Any, str]:
    hdrs = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(raw), raw[:8000]
            except json.JSONDecodeError:
                return resp.status, None, raw[:8000]
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace") if exc.fp else str(exc)
        parsed: Any = None
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = None
        return exc.code, parsed, raw[:2000]
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return 0, None, f"{type(exc).__name__}: {exc}"


def ghsa_ids_from_text(*parts: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for part in parts:
        if not part:
            continue
        for match in GHSA_RE.findall(part):
            body = match.split("GHSA-", 1)[-1].lower()
            gid = f"GHSA-{body}"
            if gid not in seen:
                seen.add(gid)
                found.append(gid)
    return found


def _parse_osv_vulns(status: int, vulns: Any, raw: str) -> dict:
    if not isinstance(vulns, list):
        vulns = []
    ids: list[str] = []
    severities: list[str] = []
    for vuln in vulns:
        if not isinstance(vuln, dict):
            continue
        blob = json.dumps(vuln)
        ids.extend(ghsa_ids_from_text(str(vuln.get("id") or ""), blob))
        extra = vuln.get("aliases") or []
        if isinstance(extra, list):
            ids.extend(ghsa_ids_from_text(*[str(x) for x in extra]))
        sev = vuln.get("severity") or []
        if isinstance(sev, list):
            for item in sev:
                if isinstance(item, dict) and item.get("score"):
                    severities.append(str(item.get("score")))
        database = vuln.get("database_specific") or {}
        if isinstance(database, dict) and database.get("severity"):
            severities.append(str(database["severity"]))
    uniq: list[str] = []
    seen: set[str] = set()
    for gid in ids:
        if gid not in seen:
            seen.add(gid)
            uniq.append(gid)
    return {
        "ok": status == 200,
        "http_status": status,
        "ids": uniq,
        "osv_ids": [
            str(v.get("id"))
            for v in vulns
            if isinstance(v, dict) and v.get("id")
        ],
        "severities": severities,
        "vuln_count": len(vulns),
        "raw_head": raw[:2000],
    }


def osv_query(name: str, version: str, ecosystem: str) -> dict:
    eco = ECOSYSTEM_MAP.get(ecosystem, ecosystem)
    status, body, raw = http_json(
        OSV_QUERY,
        method="POST",
        payload={"package": {"name": name, "ecosystem": eco}, "version": version},
    )
    vulns = []
    if isinstance(body, dict):
        vulns = body.get("vulns") or []
    return _parse_osv_vulns(status, vulns, raw)


def osv_querybatch(
    items: list[tuple[str, str, str]], *, chunk_size: int = 200
) -> dict[tuple[str, str, str], dict]:
    """Batch OSV queries. items are (ecosystem, name, version)."""
    out: dict[tuple[str, str, str], dict] = {}
    uniq: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        uniq.append(item)
    for i in range(0, len(uniq), chunk_size):
        chunk = uniq[i : i + chunk_size]
        queries = []
        for ecosystem, name, version in chunk:
            eco = ECOSYSTEM_MAP.get(ecosystem, ecosystem)
            queries.append(
                {"package": {"name": name, "ecosystem": eco}, "version": version}
            )
        status, body, raw = http_json(
            OSV_BATCH,
            method="POST",
            payload={"queries": queries},
            timeout=120,
        )
        results = body.get("results") if isinstance(body, dict) else None
        if status != 200 or not isinstance(results, list) or len(results) != len(chunk):
            for ecosystem, name, version in chunk:
                out[(ecosystem, name, version)] = osv_query(name, version, ecosystem)
            continue
        for key, item in zip(chunk, results):
            vulns = []
            if isinstance(item, dict):
                vulns = item.get("vulns") or []
            out[key] = _parse_osv_vulns(status, vulns, raw)
    return out


def npm_bulk_query(packages: dict[str, list[str]], *, chunk_size: int = 80) -> dict:
    """GitHub Advisory Database as consumed by npm audit / Dependabot npm.

    Independent of api.osv.dev. Unauthenticated GitHub REST is rate-limited
    on this host (remaining=0); this endpoint is the reachable GHSA path.
    """
    names = list(packages.keys())
    by_pkg: dict[str, list[dict]] = {}
    last_status = 0
    raw_head = ""
    ok = True
    if not names:
        return {
            "ok": False,
            "http_status": 0,
            "by_package": {},
            "raw_head": "no-npm-packages",
        }
    for i in range(0, len(names), chunk_size):
        chunk = {name: packages[name] for name in names[i : i + chunk_size]}
        status, body, raw = http_json(NPM_BULK, method="POST", payload=chunk)
        last_status = status
        raw_head = raw[:2000]
        if status != 200:
            ok = False
            continue
        if isinstance(body, dict):
            for name, rows in body.items():
                hits = []
                if isinstance(rows, list):
                    for row in rows:
                        if not isinstance(row, dict):
                            continue
                        ids = ghsa_ids_from_text(
                            str(row.get("id") or ""),
                            str(row.get("url") or ""),
                            json.dumps(row),
                        )
                        hits.append(
                            {
                                "ghsa_ids": ids,
                                "severity": row.get("severity"),
                                "title": row.get("title"),
                                "url": row.get("url"),
                                "vulnerable_versions": row.get("vulnerable_versions"),
                                "npm_id": row.get("id"),
                            }
                        )
                by_pkg[name] = hits
    return {
        "ok": ok and last_status == 200,
        "http_status": last_status,
        "by_package": by_pkg,
        "raw_head": raw_head,
    }


def ghsa_ids_for_npm(name: str, bulk: dict) -> list[str]:
    hits = (bulk.get("by_package") or {}).get(name) or []
    ids: list[str] = []
    seen: set[str] = set()
    for hit in hits:
        for gid in hit.get("ghsa_ids") or []:
            if gid not in seen:
                seen.add(gid)
                ids.append(gid)
    return ids


def try_dependabot_alerts() -> dict:
    """Repo Dependabot alert list. Requires auth; do not print secrets."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    gh = shutil.which("gh")
    if not token and not gh:
        return {
            "checked": False,
            "status": "NOT-CHECKED",
            "reason": (
                "no GITHUB_TOKEN/GH_TOKEN and gh CLI absent; unauthenticated "
                "api.github.com rate-limit remaining was 0 on this host"
            ),
            "alert_count": None,
        }
    # Authenticated call only if a token exists. Never log the token.
    if token:
        status, body, raw = http_json(
            "https://api.github.com/rate_limit",
            headers={
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        del token
        remaining = None
        if isinstance(body, dict):
            remaining = ((body.get("resources") or {}).get("core") or {}).get(
                "remaining"
            )
        return {
            "checked": False,
            "status": "NOT-CHECKED",
            "reason": (
                "token present but this worktree has no GitHub origin for "
                "Dependabot alerts; GHSA is queried via npm bulk instead. "
                f"rate_limit_http={status} remaining={remaining}"
            ),
            "alert_count": None,
            "raw_head": raw[:200] if raw else "",
        }
    return {
        "checked": False,
        "status": "NOT-CHECKED",
        "reason": "gh present but unused: no origin Dependabot target",
        "alert_count": None,
    }


def osv_scanner_binary() -> dict:
    path = shutil.which("osv-scanner")
    return {
        "present": bool(path),
        "path": path,
        "note": (
            "osv-scanner binary absent; probe 1 uses api.osv.dev /v1/query, "
            "the same advisory corpus osv-scanner queries"
            if not path
            else "osv-scanner on PATH"
        ),
    }
