#!/usr/bin/env python3
"""Live OSV advisory scanner for CNF-0112 (stdlib urllib; no secrets)."""
from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

OSV_QUERY = "https://api.osv.dev/v1/query"
OSV_BATCH = "https://api.osv.dev/v1/querybatch"
UA = "CNF-0112-advisory-rescan/1.0"
KNOWN_ADVISORY_PKG = ("lodash", "4.17.11", "npm")
MISSING_TOOL_CODE = 127


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def classify_scanner_exit(code: int | None, *, not_found: bool = False) -> str:
    """Exit 127 / missing binary is scanner-not-installed, never a clean scan."""
    if not_found or code == MISSING_TOOL_CODE:
        return "scanner-not-installed"
    if code == 0:
        return "clean-or-success"
    if code == 1:
        return "findings-or-error"
    if code is None:
        return "not-run"
    return f"other-{code}"


def run_missing_scanner() -> dict[str, Any]:
    """Negative control: a binary that is not on PATH must classify as 127, not clean."""
    try:
        proc = subprocess.run(
            ["cnf0112-osv-scanner-not-installed"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        code = proc.returncode
        not_found = False
    except FileNotFoundError:
        code = MISSING_TOOL_CODE
        not_found = True
    klass = classify_scanner_exit(code, not_found=not_found)
    return {
        "exit_code": code,
        "classification": klass,
        "not_found": not_found,
        "distinguished_from_clean": klass == "scanner-not-installed"
        and classify_scanner_exit(0) != klass,
    }


def packages_from_npm_lock(path: Path) -> list[dict[str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    packages = data.get("packages") or {}
    if not isinstance(packages, dict):
        return rows
    for key, meta in packages.items():
        if not isinstance(meta, dict):
            continue
        if key in ("", "."):
            continue
        version = str(meta.get("version") or "").strip()
        if not version:
            continue
        name = str(meta.get("name") or "").strip()
        if not name:
            rel = str(key).rsplit("node_modules/", 1)[-1].strip("/")
            name = rel
        if not name or name.startswith("node_modules/"):
            continue
        ident = (name, version)
        if ident in seen:
            continue
        seen.add(ident)
        rows.append(
            {
                "name": name,
                "version": version,
                "ecosystem": "npm",
                "lockfile": str(path),
            }
        )
    return rows


def _post_json(url: str, payload: dict[str, Any], timeout: int = 45) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "User-Agent": UA,
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        tail = exc.read()[:500].decode("utf-8", "replace") if exc.fp else ""
        raise RuntimeError(f"osv-http-{exc.code}:{tail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"osv-unreachable:{exc.reason}") from exc
    doc = json.loads(raw) if raw.strip() else {}
    if not isinstance(doc, dict):
        raise RuntimeError("osv-non-object")
    return doc


def query_one(name: str, version: str, ecosystem: str = "npm") -> dict[str, Any]:
    return _post_json(
        OSV_QUERY,
        {"package": {"name": name, "ecosystem": ecosystem}, "version": version},
    )


def query_batch(pkgs: list[dict[str, str]]) -> list[dict[str, Any]]:
    if not pkgs:
        return []
    out: list[dict[str, Any]] = []
    chunk = 40
    for i in range(0, len(pkgs), chunk):
        part = pkgs[i : i + chunk]
        payload = {
            "queries": [
                {
                    "package": {
                        "name": p["name"],
                        "ecosystem": p.get("ecosystem") or "npm",
                    },
                    "version": p["version"],
                }
                for p in part
            ]
        }
        doc = _post_json(OSV_BATCH, payload, timeout=60)
        results = doc.get("results") or []
        if not isinstance(results, list):
            raise RuntimeError("osv-batch-shape")
        if len(results) != len(part):
            raise RuntimeError(f"osv-batch-length want={len(part)} got={len(results)}")
        for pkg, res in zip(part, results):
            vulns = []
            if isinstance(res, dict):
                vulns = res.get("vulns") or []
            out.append({"package": pkg, "vulns": vulns if isinstance(vulns, list) else []})
    return out


def empty_cache_lookup(name: str, version: str, ecosystem: str = "npm") -> list[Any]:
    """Local empty advisory index: silence is not absence on a live DB."""
    del name, version, ecosystem
    return []


def flatten_findings(batch_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in batch_rows:
        pkg = row.get("package") or {}
        name = str(pkg.get("name") or "")
        version = str(pkg.get("version") or "")
        for vuln in row.get("vulns") or []:
            if not isinstance(vuln, dict):
                continue
            vid = str(vuln.get("id") or "").strip()
            if not vid:
                continue
            key = (vid, name, version)
            if key in seen:
                continue
            seen.add(key)
            sev = "UNKNOWN"
            for item in vuln.get("severity") or []:
                if isinstance(item, dict) and item.get("score"):
                    sev = str(item.get("type") or "CVSS") + ":" + str(item["score"])
                    break
            findings.append(
                {
                    "id": vid,
                    "severity": sev,
                    "package": name,
                    "version": version,
                    "source": "osv.dev",
                    "summary": str(vuln.get("summary") or vuln.get("details") or "")[:240],
                    "modified": str(vuln.get("modified") or ""),
                }
            )
    findings.sort(key=lambda r: (r["id"], r["package"], r["version"]))
    return findings


def snapshot_date_from(findings: list[dict[str, Any]], control_modified: str) -> str:
    dates = [str(f.get("modified") or "") for f in findings if f.get("modified")]
    if control_modified:
        dates.append(control_modified)
    dates = [d for d in dates if d]
    return max(dates) if dates else ""


def finding_keys(findings: list[dict[str, Any]]) -> set[tuple[str, str, str]]:
    return {(f["id"], f["package"], f["version"]) for f in findings}


def diff_findings(
    stored: list[dict[str, Any]], fresh: list[dict[str, Any]]
) -> dict[str, Any]:
    old = finding_keys(stored)
    new = finding_keys(fresh)
    added = sorted(new - old)
    removed = sorted(old - new)
    return {
        "added": [{"id": a, "package": b, "version": c} for a, b, c in added],
        "removed": [{"id": a, "package": b, "version": c} for a, b, c in removed],
        "added_count": len(added),
        "removed_count": len(removed),
        "unchanged_count": len(old & new),
    }


def load_stored(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {
            "present": False,
            "timestamp": None,
            "database_version": None,
            "database_snapshot_date": None,
            "findings": [],
            "verdict": "ABSENT",
            "live_or_cached": "unknown",
            "comparable": False,
        }
    doc = json.loads(path.read_text(encoding="utf-8"))
    ts = doc.get("timestamp") or doc.get("query_timestamp")
    dbv = doc.get("database_version") or doc.get("database_snapshot_date")
    comparable = bool(ts) and bool(dbv)
    return {
        "present": True,
        "timestamp": ts,
        "database_version": doc.get("database_version"),
        "database_snapshot_date": doc.get("database_snapshot_date"),
        "findings": doc.get("findings") or [],
        "verdict": doc.get("verdict") or "UNKNOWN",
        "live_or_cached": doc.get("live_or_cached") or "unknown",
        "comparable": comparable,
        "reconstructed": bool(doc.get("reconstructed")),
        "source": doc.get("source"),
        "notes": doc.get("notes"),
    }
