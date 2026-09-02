"""Dated-cut advisory scanner over pinned live OSV + GitHub captures.

Live osv-scanner / pip-audit binaries are not installed on this worktree.
Those tools query OSV; this module uses the same OSV querybatch/vuln API
bodies fetched 2026-08-24, plus GitHub Advisory REST as a second published-at
rail. A checkpoint T sees a hit iff the live query still matches the frozen
pin AND published <= T.

Alias clusters (GHSA + PYSEC + CVE) are collapsed so a late PYSEC encoding
is not a second flip.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CAPTURES = HERE / "captures"

REQ_RE = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s#]+)")


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    if "." in text:
        head, rest = text.split(".", 1)
        sign_at = None
        for i, ch in enumerate(rest):
            if ch in "+-" and i > 0:
                sign_at = i
                break
        if sign_at is None:
            digits, tz = rest, "+00:00"
        else:
            digits, tz = rest[:sign_at], rest[sign_at:]
        digits = "".join(ch for ch in digits if ch.isdigit())[:6].ljust(6, "0")
        text = f"{head}.{digits}{tz}"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


parse_ts = parse_ts


def utc_date(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).date().isoformat()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_npm_lock(path: Path) -> list[dict[str, str]]:
    doc = load_json(path)
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for key, meta in (doc.get("packages") or {}).items():
        if not key:
            continue
        name = key.split("node_modules/")[-1]
        ver = str((meta or {}).get("version") or "")
        if not name or not ver:
            continue
        ident = (name, ver)
        if ident in seen:
            continue
        seen.add(ident)
        out.append({"name": name, "version": ver, "ecosystem": "npm"})
    return out


def parse_requirements(path: Path) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        m = REQ_RE.match(text)
        if not m:
            continue
        name = m.group(1)
        if name.lower() == "jinja2":
            name = "jinja2"
        out.append({"name": name, "version": m.group(2), "ecosystem": "PyPI"})
    return out


class UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def add(self, x: str) -> None:
        self.parent.setdefault(x, x)

    def find(self, x: str) -> str:
        self.add(x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


class CaptureDB:
    def __init__(self) -> None:
        self.query_index = load_json(CAPTURES / "osv-querybatch-index.json")
        self.vuln_index = load_json(CAPTURES / "osv-vulns-index.json")
        self.github_index = load_json(CAPTURES / "github-advisories-index.json")
        self.vulns: dict[str, dict[str, Any]] = {}
        for rec in self.vuln_index.get("records") or []:
            rel = rec.get("relpath") or rec.get("relpath")
            body = load_json(HERE / rel)
            vid = str(body.get("id") or rec["id"])
            self.vulns[rec["id"]] = body
            self.vulns[vid] = body
        self.github: dict[str, dict[str, Any]] = {}
        for rec in self.github_index.get("records") or []:
            if int(rec.get("http_status") or rec.get("http_status") or 0) != 200:
                continue
            rel = rec.get("relpath") or rec.get("relpath")
            body = load_json(HERE / rel)
            gid = str(
                body.get("ghsa_id")
                or body.get("ghsa_id")
                or rec.get("canonical_ghsa")
                or rec.get("canonical_ghsa")
                or rec["id"]
            )
            self.github[rec["id"]] = body
            self.github[gid] = body
        self.hits: dict[tuple[str, str, str], list[str]] = {}
        for row in self.query_index.get("results") or []:
            pkg = row.get("package") or {}
            eco = str(pkg.get("ecosystem") or "")
            name = str(pkg.get("name") or "")
            ver = str(pkg.get("version") or "")
            ids = []
            for v in row.get("vulns") or []:
                vid = v.get("id") if isinstance(v, dict) else None
                if vid:
                    ids.append(str(vid))
            self.hits[(eco, name, ver)] = ids
            self.hits[(eco, name.lower(), ver)] = ids

    def lookup_ids(self, eco: str, name: str, version: str) -> list[str]:
        for key in (
            (eco, name, version),
            (eco, name.lower(), version),
            ("PyPI", name, version),
            ("PyPI", name.lower(), version),
            ("npm", name, version),
        ):
            if key in self.hits:
                return list(self.hits[key])
        return []


def cluster_ids(db: CaptureDB, ids: list[str]) -> list[dict[str, Any]]:
    uf = UnionFind()
    docs: dict[str, dict[str, Any]] = {}
    for vid in ids:
        body = db.vulns.get(vid)
        if not body:
            continue
        canonical = str(body.get("id") or vid)
        docs[canonical] = body
        uf.add(canonical)
        uf.add(vid)
        uf.union(canonical, vid)
        for alias in body.get("aliases") or []:
            uf.add(str(alias))
            uf.union(canonical, str(alias))
    groups: dict[str, list[str]] = {}
    for canonical in docs:
        groups.setdefault(uf.find(canonical), []).append(canonical)
    clusters: list[dict[str, Any]] = []
    for members in groups.values():
        published_map: dict[str, datetime] = {}
        aliases: set[str] = set()
        for mid in members:
            body = docs[mid]
            ts = parse_ts(body.get("published"))
            if ts:
                published_map[mid] = ts
            aliases.add(mid)
            for a in body.get("aliases") or []:
                aliases.add(str(a))
        if not published_map:
            continue
        first_id = min(published_map, key=lambda k: published_map[k])
        first_ts = published_map[first_id]
        ghsa = sorted(m for m in members if m.startswith("GHSA-"))
        cves = sorted(a for a in aliases if a.startswith("CVE-"))
        clusters.append(
            {
                "member_ids": sorted(members),
                "aliases": sorted(aliases),
                "first_id": first_id,
                "first_published": first_ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "first_published_dt": first_ts,
                "ghsa_ids": ghsa,
                "cve_ids": cves,
            }
        )
    clusters.sort(key=lambda c: c["first_published"])
    return clusters


def visible_clusters(
    db: CaptureDB, pkg: dict[str, str], when: datetime
) -> list[dict[str, Any]]:
    ids = db.lookup_ids(pkg["ecosystem"], pkg["name"], pkg["version"])
    out = []
    for cl in cluster_ids(db, ids):
        if cl["first_published_dt"] <= when:
            out.append(cl)
    return out


def package_verdict(
    db: CaptureDB, pkg: dict[str, str], when: datetime
) -> dict[str, Any]:
    vis = visible_clusters(db, pkg, when)
    ids = [c["first_id"] for c in vis]
    return {
        "name": pkg["name"],
        "version": pkg["version"],
        "ecosystem": pkg["ecosystem"],
        "verdict": "RED" if vis else "GREEN",
        "cluster_count": len(vis),
        "advisory_ids": ids,
        "clusters": [
            {
                "first_id": c["first_id"],
                "first_published": c["first_published"],
                "ghsa_ids": c["ghsa_ids"],
                "cve_ids": c["cve_ids"],
                "member_ids": c["member_ids"],
            }
            for c in vis
        ],
    }


def lockfile_verdict(
    db: CaptureDB, packages: list[dict[str, str]], when: datetime
) -> dict[str, Any]:
    rows = [package_verdict(db, pkg, when) for pkg in packages]
    red = [r for r in rows if r["verdict"] == "RED"]
    ids: list[str] = []
    for r in red:
        for aid in r["advisory_ids"]:
            if aid not in ids:
                ids.append(aid)
    return {
        "verdict": "RED" if red else "GREEN",
        "red_package_count": len(red),
        "package_count": len(rows),
        "advisory_ids": ids,
        "red_packages": [
            {
                "name": r["name"],
                "version": r["version"],
                "ecosystem": r["ecosystem"],
                "advisory_ids": r["advisory_ids"],
            }
            for r in red
        ],
    }


def github_published(db: CaptureDB, ghsa_id: str) -> dict[str, Any] | None:
    body = db.github.get(ghsa_id)
    if not body:
        return None
    ts = parse_ts(body.get("published_at"))
    return {
        "ghsa_id": body.get("ghsa_id") or body.get("ghsa_id") or ghsa_id,
        "cve_id": body.get("cve_id") or body.get("cve_id"),
        "published_at": body.get("published_at"),
        "published_dt": ts,
        "published_date": utc_date(ts) if ts else None,
        "url": (
            "https://api.github.com/advisories/"
            f"{body.get('ghsa_id') or body.get('ghsa_id') or ghsa_id}"
        ),
    }


def osv_published(db: CaptureDB, vid: str) -> dict[str, Any] | None:
    body = db.vulns.get(vid)
    if not body:
        return None
    ts = parse_ts(body.get("published"))
    return {
        "id": body.get("id") or vid,
        "published": body.get("published"),
        "published_dt": ts,
        "published_date": utc_date(ts) if ts else None,
        "url": f"https://api.osv.dev/v1/vulns/{body.get('id') or vid}",
        "aliases": list(body.get("aliases") or []),
    }


def second_signal_agreement(db: CaptureDB, ghsa_id: str) -> dict[str, Any]:
    osv = osv_published(db, ghsa_id)
    gh = github_published(db, ghsa_id)
    agree = bool(
        osv
        and gh
        and osv.get("published_date")
        and osv.get("published_date") == gh.get("published_date")
    )
    return {
        "ghsa_id": ghsa_id,
        "agree_utc_date": agree,
        "osv": {k: v for k, v in (osv or {}).items() if k != "published_dt"},
        "github": {k: v for k, v in (gh or {}).items() if k != "published_dt"},
    }


# Aliases used by measure.py / probes.
CaptureDB = CaptureDB
parse_npm_lock = parse_npm_lock
parse_requirements = parse_requirements
sha256_file = sha256_file
lockfile_verdict = lockfile_verdict
package_verdict = package_verdict
osv_published = osv_published
second_signal_agreement = second_signal_agreement
load_json = load_json
github_published = github_published
