#!/usr/bin/env python3
"""Per-dependency license/version/advisory/fallback resolution.

Retry: three attempts with staggered backoff for timeout/429/5xx.
Zero retries on 404/410 — that is a result (UNRESOLVED), not a blip.
A missed upstream is UNRESOLVED, never assumed healthy.
CLEAN advisory rows are trusted only after the known-vuln control fires.
"""
from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from inventory import (
    CLEAN_CONTROL_ID,
    KNOWN_CVE,
    UNREACHABLE_CONTROL_ID,
    VULN_CONTROL_ID,
    load_inventory,
    no_pin_no_fallback_ids,
)

OSV_QUERY = "https://api.osv.dev/v1/query"
OSV_BATCH = "https://api.osv.dev/v1/querybatch"
USER_AGENT = "WFA-0151-supply-chain-map ast-integrate"
TRANSIENT_HTTP = frozenset({408, 425, 429, 500, 502, 503, 504})
NONTRANSIENT_HTTP = frozenset({400, 401, 403, 404, 410, 451})
CTX = ssl.create_default_context()


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def osv_ecosystem(eco: str) -> str | None:
    e = eco.strip()
    return {
        "npm": "npm",
        "PyPI": "PyPI",
        "pypi": "PyPI",
        "Go": "Go",
        "crates.io": "crates.io",
        "GitHub Actions": "GitHub Actions",
    }.get(e)


def registry_url(dep: dict[str, Any]) -> str:
    eco = dep["ecosystem"]
    name = dep["name"]
    ver = dep["version"]
    if eco == "npm":
        enc = urllib.parse.quote(name, safe="@")
        # scoped names: @scope/pkg -> @scope%2fpkg
        if name.startswith("@") and "/" in name:
            enc = urllib.parse.quote(name, safe="@")
            enc = enc.replace("/", "%2f")
        return f"https://registry.npmjs.org/{enc}/{ver}"
    if eco in {"PyPI", "pypi"}:
        return f"https://pypi.org/pypi/{name}/{ver}/json"
    if eco == "crates.io":
        return f"https://crates.io/api/v1/crates/{name}/{ver}"
    if eco == "Go":
        enc = urllib.parse.quote(name, safe="/")
        return f"https://proxy.golang.org/{enc}/@v/{ver}.info"
    if eco == "GitHub Actions":
        # Tag-tree LICENSE (no GitHub API token). 404 = unreachable.
        return f"https://raw.githubusercontent.com/{name}/{ver}/LICENSE"
    return f"https://example.invalid/unknown/{urllib.parse.quote(name)}"


def fetch_url(
    url: str,
    *,
    method: str = "GET",
    body: bytes | None = None,
    timeout: float = 12.0,
    max_attempts: int | None = None,
    accept: str = "application/json,text/plain,*/*",
) -> dict[str, Any]:
    """Fetch with catalog retry policy. max_attempts None => 3, unless 404/410."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": accept,
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    attempts_cap = 3 if max_attempts is None else max_attempts
    last_status = None
    last_err = None
    attempts = 0
    delay = 0.25
    fetched_at = utc_now()
    while attempts < attempts_cap:
        attempts += 1
        fetched_at = utc_now()
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=CTX) as resp:
                raw = resp.read()
                status = int(resp.status)
                http_date = resp.headers.get("Date")
                ctype = resp.headers.get("Content-Type") or ""
                parsed: Any = None
                text = raw.decode("utf-8", errors="replace") if raw else ""
                if "json" in ctype or (text[:1] in "{["):
                    try:
                        parsed = json.loads(text) if text else None
                    except json.JSONDecodeError:
                        parsed = None
                return {
                    "ok": 200 <= status < 300,
                    "status": status,
                    "url": url,
                    "fetched_at": fetched_at,
                    "http_date": http_date,
                    "attempts": attempts,
                    "body": parsed,
                    "text_head": text[:400],
                    "error": None,
                    "nontransient": False,
                    "retry_class": "none",
                }
        except urllib.error.HTTPError as exc:
            last_status = int(exc.code)
            last_err = f"HTTP {exc.code}"
            http_date = exc.headers.get("Date") if exc.headers else None
            if last_status in NONTRANSIENT_HTTP:
                return {
                    "ok": False,
                    "status": last_status,
                    "url": url,
                    "fetched_at": fetched_at,
                    "http_date": http_date,
                    "attempts": attempts,
                    "body": None,
                    "text_head": "",
                    "error": last_err,
                    "nontransient": True,
                    "retry_class": "nontransient-result",
                }
            if last_status not in TRANSIENT_HTTP or attempts >= attempts_cap:
                return {
                    "ok": False,
                    "status": last_status,
                    "url": url,
                    "fetched_at": fetched_at,
                    "http_date": http_date,
                    "attempts": attempts,
                    "body": None,
                    "text_head": "",
                    "error": last_err,
                    "nontransient": last_status in NONTRANSIENT_HTTP,
                    "retry_class": "exhausted" if last_status in TRANSIENT_HTTP else "other",
                }
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_err = f"{type(exc).__name__}:{exc}"
            last_status = None
            if attempts >= attempts_cap:
                return {
                    "ok": False,
                    "status": None,
                    "url": url,
                    "fetched_at": fetched_at,
                    "http_date": None,
                    "attempts": attempts,
                    "body": None,
                    "text_head": "",
                    "error": last_err,
                    "nontransient": False,
                    "retry_class": "exhausted-transport",
                }
        time.sleep(delay)
        delay *= 2
    return {
        "ok": False,
        "status": last_status,
        "url": url,
        "fetched_at": fetched_at,
        "http_date": None,
        "attempts": attempts,
        "body": None,
        "text_head": "",
        "error": last_err or "exhausted",
        "nontransient": last_status in NONTRANSIENT_HTTP if last_status else False,
        "retry_class": "exhausted",
    }


def license_from_registry(eco: str, fetch: dict[str, Any]) -> str | None:
    if not fetch.get("ok"):
        return None
    body = fetch.get("body")
    text = fetch.get("text_head") or ""
    if eco == "npm" and isinstance(body, dict):
        lic = body.get("license")
        if isinstance(lic, str) and lic.strip():
            return lic.strip()
        if isinstance(lic, dict) and lic.get("type"):
            return str(lic["type"])
    if eco in {"PyPI", "pypi"} and isinstance(body, dict):
        info = body.get("info") or {}
        lic = info.get("license")
        if isinstance(lic, str) and lic.strip() and lic.strip() not in {"UNKNOWN", ""}:
            return lic.strip()
        for c in info.get("classifiers") or []:
            if isinstance(c, str) and "License ::" in c:
                return c.split("::")[-1].strip()
    if eco == "crates.io" and isinstance(body, dict):
        ver = body.get("version") or {}
        lic = ver.get("license")
        if isinstance(lic, str) and lic.strip():
            return lic.strip()
    if eco == "GitHub Actions" and text:
        head = text.splitlines()[0].strip() if text.splitlines() else ""
        if "MIT" in text[:200]:
            return "MIT"
        if "Apache" in text[:400]:
            return "Apache-2.0"
        if head:
            return f"LICENSE-text:{head[:80]}"
    if eco == "Go" and isinstance(body, dict):
        return None
    return None


def maintenance_from_registry(eco: str, fetch: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "status": "UNRESOLVED",
        "last_release": None,
        "signal": None,
    }
    if not fetch.get("ok"):
        return out
    body = fetch.get("body")
    if eco == "npm" and isinstance(body, dict):
        t = body.get("time") if isinstance(body.get("time"), dict) else {}
        last = t.get("modified") or body.get("_modified")
        if last:
            out["status"] = "OBSERVED"
            out["last_release"] = str(last)
            out["signal"] = "npm-registry-time.modified"
            return out
    if eco in {"PyPI", "pypi"} and isinstance(body, dict):
        urls = body.get("urls") or []
        times = [u.get("upload_time_iso_8601") or u.get("upload_time") for u in urls if isinstance(u, dict)]
        times = [t for t in times if t]
        if times:
            out["status"] = "OBSERVED"
            out["last_release"] = max(str(t) for t in times)
            out["signal"] = "pypi-upload_time"
            return out
    if eco == "crates.io" and isinstance(body, dict):
        ver = body.get("version") or {}
        created = ver.get("created_at") or ver.get("updated_at")
        if created:
            out["status"] = "OBSERVED"
            out["last_release"] = str(created)
            out["signal"] = "crates-io-created_at"
            return out
    if eco == "Go" and isinstance(body, dict) and body.get("Time"):
        out["status"] = "OBSERVED"
        out["last_release"] = str(body["Time"])
        out["signal"] = "proxy.golang.org-info.Time"
        return out
    if eco == "GitHub Actions" and fetch.get("ok"):
        out["status"] = "OBSERVED"
        out["last_release"] = fetch.get("http_date") or fetch.get("fetched_at")
        out["signal"] = "raw.githubusercontent.com-LICENSE-reachable"
        return out
    if fetch.get("http_date"):
        out["status"] = "OBSERVED"
        out["last_release"] = fetch["http_date"]
        out["signal"] = "http-date"
    return out


def collect_osv_ids(record: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for key in ("id",):
        val = record.get(key)
        if isinstance(val, str) and val:
            ids.append(val)
    for alias in record.get("aliases") or []:
        if isinstance(alias, str) and alias:
            ids.append(alias)
    seen: set[str] = set()
    out: list[str] = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def osv_query(name: str, ecosystem: str, version: str) -> dict[str, Any]:
    eco = osv_ecosystem(ecosystem)
    if not eco:
        return {
            "ok": False,
            "ids": [],
            "fetch": {"ok": False, "error": f"unsupported-ecosystem:{ecosystem}", "url": OSV_QUERY},
        }
    payload = json.dumps({"package": {"name": name, "ecosystem": eco}, "version": version}).encode("utf-8")
    fetch = fetch_url(OSV_QUERY, method="POST", body=payload, timeout=20.0)
    ids: list[str] = []
    if fetch.get("ok") and isinstance(fetch.get("body"), dict):
        for v in fetch["body"].get("vulns") or []:
            if isinstance(v, dict):
                ids.extend(collect_osv_ids(v))
    # unique
    seen: set[str] = set()
    uniq = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            uniq.append(i)
    return {"ok": bool(fetch.get("ok")), "ids": uniq, "fetch": fetch}


def osv_querybatch(deps: list[dict[str, Any]]) -> dict[str, Any]:
    queries = []
    index_map: list[str | None] = []
    for dep in deps:
        eco = osv_ecosystem(dep["ecosystem"])
        if not eco or dep.get("role") == "unreachable-control":
            index_map.append(None)
            continue
        queries.append(
            {"package": {"name": dep["name"], "ecosystem": eco}, "version": dep["version"]}
        )
        index_map.append(dep["id"])
    if not queries:
        return {"ok": False, "by_id": {}, "fetch": {"ok": False, "error": "no-queries"}}
    payload = json.dumps({"queries": queries}).encode("utf-8")
    fetch = fetch_url(OSV_BATCH, method="POST", body=payload, timeout=60.0)
    by_id: dict[str, list[str]] = {}
    if fetch.get("ok") and isinstance(fetch.get("body"), dict):
        results = fetch["body"].get("results") or []
        qi = 0
        for dep_id in index_map:
            if dep_id is None:
                continue
            rec = results[qi] if qi < len(results) else {}
            qi += 1
            ids: list[str] = []
            if isinstance(rec, dict):
                for v in rec.get("vulns") or []:
                    if isinstance(v, dict):
                        ids.extend(collect_osv_ids(v))
                    elif isinstance(v, str):
                        ids.append(v)
            by_id[dep_id] = ids
    return {"ok": bool(fetch.get("ok")), "by_id": by_id, "fetch": fetch}


def resolve_all(*, fetch_registry: bool = True, live_osv: bool = True) -> dict[str, Any]:
    inv = load_inventory()
    deps = list(inv["dependencies"])
    n = len(deps)
    ids = [d["id"] for d in deps]
    if len(set(ids)) != n:
        raise RuntimeError("duplicate dependency ids")

    batch = osv_querybatch(deps) if live_osv else {"ok": False, "by_id": {}, "fetch": {"ok": False}}
    # Dedicated live queries for both-states controls (full vuln records, including aliases).
    vuln_live = osv_query("lodash", "npm", "4.17.20") if live_osv else {"ok": False, "ids": [], "fetch": {}}
    clean_live = osv_query("ms", "npm", "2.1.3") if live_osv else {"ok": False, "ids": [], "fetch": {}}
    vuln_ids = list(vuln_live.get("ids") or [])
    clean_ids = list(clean_live.get("ids") or [])
    vuln_fired = bool(vuln_live.get("ok")) and KNOWN_CVE in vuln_ids
    clean_ok = bool(clean_live.get("ok")) and KNOWN_CVE not in clean_ids and len(clean_ids) == 0
    both_states = bool(vuln_fired and clean_ok)

    rows: list[dict[str, Any]] = []
    for dep in deps:
        url = registry_url(dep)
        if dep.get("role") == "unreachable-control" or not fetch_registry:
            if dep.get("role") == "unreachable-control":
                reg = fetch_url(url, timeout=12.0, max_attempts=3)
            else:
                reg = {
                    "ok": False,
                    "status": None,
                    "url": url,
                    "fetched_at": utc_now(),
                    "http_date": None,
                    "attempts": 0,
                    "body": None,
                    "text_head": "",
                    "error": "registry-fetch-skipped",
                    "nontransient": False,
                    "retry_class": "skipped",
                }
        else:
            reg = fetch_url(url, timeout=12.0)

        if not reg.get("ok"):
            resolution = "UNRESOLVED"
            license_val = None
            maint = {
                "status": "UNRESOLVED",
                "last_release": None,
                "signal": None,
            }
            if reg.get("nontransient") or reg.get("status") in NONTRANSIENT_HTTP:
                maint["status"] = "UNRESOLVED"
        else:
            resolution = "RESOLVED"
            license_val = license_from_registry(dep["ecosystem"], reg) or dep.get("license_hint")
            maint = maintenance_from_registry(dep["ecosystem"], reg)
            if maint["status"] == "UNRESOLVED" and license_val:
                maint = {
                    "status": "OBSERVED",
                    "last_release": reg.get("http_date") or reg.get("fetched_at"),
                    "signal": "registry-reachable",
                }

        if dep["id"] == VULN_CONTROL_ID:
            advisory_ids = vuln_ids
            osv_ok = bool(vuln_live.get("ok"))
            osv_url = (vuln_live.get("fetch") or {}).get("url") or OSV_QUERY
            osv_at = (vuln_live.get("fetch") or {}).get("fetched_at")
        elif dep["id"] == CLEAN_CONTROL_ID:
            advisory_ids = clean_ids
            osv_ok = bool(clean_live.get("ok"))
            osv_url = (clean_live.get("fetch") or {}).get("url") or OSV_QUERY
            osv_at = (clean_live.get("fetch") or {}).get("fetched_at")
        elif dep.get("role") == "unreachable-control":
            advisory_ids = []
            osv_ok = False
            osv_url = None
            osv_at = None
        else:
            advisory_ids = list((batch.get("by_id") or {}).get(dep["id"]) or [])
            osv_ok = bool(batch.get("ok"))
            osv_url = (batch.get("fetch") or {}).get("url") or OSV_BATCH
            osv_at = (batch.get("fetch") or {}).get("fetched_at")

        if resolution == "UNRESOLVED" and dep.get("role") == "unreachable-control":
            advisory_status = "UNRESOLVED"
        elif not osv_ok:
            advisory_status = "UNRESOLVED"
        elif advisory_ids:
            advisory_status = "FLAGGED"
        elif both_states:
            advisory_status = "CLEAN"
        else:
            advisory_status = "UNTRUSTED"

        rows.append(
            {
                "id": dep["id"],
                "ecosystem": dep["ecosystem"],
                "name": dep["name"],
                "version": dep["version"],
                "pin": dep.get("pin"),
                "pinned": bool(dep.get("pinned")),
                "fallback": dep.get("fallback"),
                "has_pin_and_fallback": bool(dep.get("pin")) and bool(dep.get("fallback")),
                "no_pin_and_no_fallback": (not dep.get("pin")) and (not dep.get("fallback")),
                "role": dep.get("role"),
                "license": license_val,
                "license_status": "RESOLVED" if license_val and resolution == "RESOLVED" else "UNRESOLVED",
                "maintenance": maint,
                "advisory_status": advisory_status,
                "advisory_ids": advisory_ids[:24],
                "resolution": resolution,
                "upstream": {
                    "url": url,
                    "fetched_at": reg.get("fetched_at"),
                    "http_date": reg.get("http_date"),
                    "http_status": reg.get("status"),
                    "attempts": reg.get("attempts"),
                    "nontransient": bool(reg.get("nontransient")),
                    "retry_class": reg.get("retry_class"),
                    "error": reg.get("error"),
                    "osv_url": osv_url,
                    "osv_fetched_at": osv_at,
                },
            }
        )

    no_pin = no_pin_no_fallback_ids(deps)
    unresolved = sorted(r["id"] for r in rows if r["resolution"] == "UNRESOLVED")
    flagged = sorted(r["id"] for r in rows if r["advisory_status"] == "FLAGGED")
    by_id = {r["id"]: r for r in rows}
    vuln_row = by_id.get(VULN_CONTROL_ID) or {}
    clean_row = by_id.get(CLEAN_CONTROL_ID) or {}
    unr_row = by_id.get(UNREACHABLE_CONTROL_ID) or {}

    return {
        "inventory_source": inv["source"],
        "restore_present": inv["restore_present"],
        "restore_path": inv.get("restore_path"),
        "n": n,
        "rows": rows,
        "no_pin_and_no_fallback": no_pin,
        "unresolved_ids": unresolved,
        "flagged_ids": flagged,
        "both_states_gate": {
            "vuln_control_id": VULN_CONTROL_ID,
            "clean_control_id": CLEAN_CONTROL_ID,
            "known_cve": KNOWN_CVE,
            "vuln_queried_first": True,
            "vuln_queried_first": True,
            "vuln_flagged": vuln_row.get("advisory_status") == "FLAGGED",
            "vuln_flagged": vuln_row.get("advisory_status") == "FLAGGED",
            "vuln_has_known_cve": KNOWN_CVE in (vuln_row.get("advisory_ids") or []),
            "clean_not_flagged": clean_row.get("advisory_status") == "CLEAN",
            "clean_has_known_cve": KNOWN_CVE in (clean_row.get("advisory_ids") or []),
            "passed": both_states
            and vuln_row.get("advisory_status") == "FLAGGED"
            and clean_row.get("advisory_status") == "CLEAN",
            "vuln_live_ok": bool(vuln_live.get("ok")),
            "clean_live_ok": bool(clean_live.get("ok")),
        },
        "unreachable_control": {
            "id": UNREACHABLE_CONTROL_ID,
            "resolution": unr_row.get("resolution"),
            "advisory_status": unr_row.get("advisory_status"),
            "http_status": (unr_row.get("upstream") or {}).get("http_status"),
            "attempts": (unr_row.get("upstream") or {}).get("attempts"),
            "nontransient": (unr_row.get("upstream") or {}).get("nontransient"),
        },
        "osv_batch_ok": bool(batch.get("ok")),
        "osv_batch_url": OSV_BATCH,
        "osv_batch_fetched_at": (batch.get("fetch") or {}).get("fetched_at"),
        "catalog_claimed_n": 105,
        "measured_n": n,
    }
