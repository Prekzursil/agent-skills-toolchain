#!/usr/bin/env python3
"""Dated-snapshot advisory scanner for RES-0051.

Scans a scratch manifest against a published-date cut of a pinned OSV/GHSA
corpus. Live osv-scanner cannot implement two dated snapshots: it queries
today's database twice. Membership is published <= snapshot_date.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "RES-0051"
FIXTURES = HERE / "fixtures"
CORPUS_REL = "command-center/p2-wave/probes/RES-0051/fixtures/corpus.json"
FROZEN_REL = "command-center/p2-wave/probes/RES-0051/fixtures/frozen-lock.json"
VULN_REL = "command-center/p2-wave/probes/RES-0051/fixtures/scratch-vulnerable.json"
PATCH_REL = "command-center/p2-wave/probes/RES-0051/fixtures/scratch-patched.json"
SKILL_REL = "command-center/p2-wave/probes/RES-0051/fixtures/skill-payload.md"
CAPTURES_REL = "command-center/p2-wave/probes/RES-0051/fixtures/captures.json"
OUT_REL = "command-center/research/RES-0051.json"
SCHEMA_REL = "command-center/schema/research-claim-record.schema.json"
SNAPSHOT_A = "2024-05-01T00:00:00Z"
SNAPSHOT_B = "2024-06-01T00:00:00Z"
HIT_ID = "GHSA-9wx4-h78v-vm56"
PRIOR_ID = "GHSA-j8r2-6x86-q33q"
NODE_LATER_ID = "GHSA-3xgq-45jj-v275"
ECO_ALIASES = {"pypi": "pypi", "pip": "pypi", "python": "pypi", "npm": "npm", "node": "npm"}


def parse_ts(value: str) -> datetime:
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_ver(value: str) -> tuple[int, ...]:
    text = str(value).strip()
    if not text or text == "0":
        return (0,)
    parts: list[int] = []
    for token in text.split("."):
        digits = ""
        for ch in token:
            if ch.isdigit():
                digits += ch
            else:
                break
        parts.append(int(digits or "0"))
    return tuple(parts) or (0,)


def ver_cmp(left: str, right: str) -> int:
    a, b = parse_ver(left), parse_ver(right)
    n = max(len(a), len(b))
    a = a + (0,) * (n - len(a))
    b = b + (0,) * (n - len(b))
    return (a > b) - (a < b)


def in_range(version: str, events: list[dict[str, str]]) -> bool:
    introduced = "0"
    fixed: str | None = None
    last_affected: str | None = None
    for event in events:
        if "introduced" in event:
            introduced = str(event["introduced"])
        if "fixed" in event:
            fixed = str(event["fixed"])
        if "last_affected" in event:
            last_affected = str(event["last_affected"])
    if ver_cmp(version, introduced) < 0:
        return False
    if fixed is not None and ver_cmp(version, fixed) >= 0:
        return False
    if last_affected is not None and ver_cmp(version, last_affected) > 0:
        return False
    return True


def norm_eco(value: str | None) -> str | None:
    if not value:
        return None
    return ECO_ALIASES.get(str(value).strip().lower(), str(value).strip().lower())


def load_json(rel: str) -> Any:
    path = REPO / rel
    return json.loads(path.read_text(encoding="utf-8"))


def load_corpus() -> dict[str, Any]:
    return load_json(CORPUS_REL)


def load_manifest(rel: str) -> dict[str, Any]:
    return load_json(rel)


def cut_snapshot(corpus: dict[str, Any], snapshot_date: str) -> dict[str, Any]:
    cut = parse_ts(snapshot_date)
    kept = [
        adv
        for adv in corpus.get("advisories") or []
        if parse_ts(str(adv.get("published") or "1970-01-01T00:00:00Z")) <= cut
    ]
    return {
        "snapshot_date": snapshot_date,
        "advisory_count": len(kept),
        "advisory_ids": [str(a.get("id")) for a in kept],
        "advisories": kept,
    }


def match_advisory(pkg: dict[str, Any], advisory: dict[str, Any]) -> dict[str, Any] | None:
    eco = norm_eco(pkg.get("ecosystem"))
    name = str(pkg.get("name") or "").strip().lower()
    version = str(pkg.get("version") or "").strip()
    if not eco or not name or not version:
        return None
    for affected in advisory.get("affected") or []:
        if norm_eco(affected.get("ecosystem")) != eco:
            continue
        if str(affected.get("name") or "").strip().lower() != name:
            continue
        events = list(affected.get("events") or [])
        if in_range(version, events):
            return {
                "id": advisory.get("id"),
                "aliases": list(advisory.get("aliases") or []),
                "published": advisory.get("published"),
                "source": advisory.get("source"),
                "package": name,
                "ecosystem": eco,
                "version": version,
                "events": events,
            }
    return None


def scan_manifest(manifest: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    hits: list[dict[str, Any]] = []
    clean: list[dict[str, Any]] = []
    unscannable: list[dict[str, Any]] = []
    for pkg in manifest.get("packages") or []:
        kind = str(pkg.get("kind") or "")
        eco = pkg.get("ecosystem")
        if kind == "prompt-payload" or not eco or not pkg.get("name"):
            unscannable.append(
                {
                    "path": pkg.get("path"),
                    "kind": kind or "no-ecosystem-identifier",
                    "reason": "no-purl-no-ecosystem",
                }
            )
            continue
        pkg_hits = []
        for adv in snapshot.get("advisories") or []:
            hit = match_advisory(pkg, adv)
            if hit:
                pkg_hits.append(hit)
                hits.append(hit)
        if not pkg_hits:
            clean.append(
                {
                    "ecosystem": norm_eco(eco),
                    "name": pkg.get("name"),
                    "version": pkg.get("version"),
                }
            )
    return {
        "snapshot_date": snapshot.get("snapshot_date"),
        "advisory_ids_in_snapshot": list(snapshot.get("advisory_ids") or []),
        "hit_count": len(hits),
        "hits": hits,
        "clean": clean,
        "unscannable": unscannable,
        "zero_open_alerts": len(hits) == 0,
        "verdict": "RED" if hits else "GREEN",
    }


def two_snapshot_comparison(
    manifest: dict[str, Any] | None = None,
    corpus: dict[str, Any] | None = None,
) -> dict[str, Any]:
    corpus = corpus if corpus is not None else load_corpus()
    manifest = manifest if manifest is not None else load_manifest(FROZEN_REL)
    snap_a = cut_snapshot(corpus, SNAPSHOT_A)
    snap_b = cut_snapshot(corpus, SNAPSHOT_B)
    scan_a = scan_manifest(manifest, snap_a)
    scan_b = scan_manifest(manifest, snap_b)
    ids_a = {h["id"] for h in scan_a["hits"]}
    ids_b = {h["id"] for h in scan_b["hits"]}
    appeared = sorted(ids_b - ids_a)
    disappeared = sorted(ids_a - ids_b)
    return {
        "frozen_lock": FROZEN_REL,
        "snapshot_a": SNAPSHOT_A,
        "snapshot_b": SNAPSHOT_B,
        "scan_a": scan_a,
        "scan_b": scan_b,
        "verdict_a": scan_a["verdict"],
        "verdict_b": scan_b["verdict"],
        "verdict_changed": scan_a["verdict"] != scan_b["verdict"],
        "appeared_ids": appeared,
        "disappeared_ids": disappeared,
        "packages_unchanged": True,
        "unscannable_both": bool(scan_a["unscannable"]) and bool(scan_b["unscannable"]),
        "node_still_green_at_b": NODE_LATER_ID not in ids_b
        and NODE_LATER_ID not in snap_b["advisory_ids"],
        "pass": (
            scan_a["verdict"] == "GREEN"
            and scan_b["verdict"] == "RED"
            and HIT_ID in appeared
            and PRIOR_ID not in ids_a
            and PRIOR_ID not in ids_b
            and bool(scan_a["unscannable"])
        ),
    }


def seeded_control(
    corpus: dict[str, Any] | None = None,
) -> dict[str, Any]:
    corpus = corpus if corpus is not None else load_corpus()
    snap_b = cut_snapshot(corpus, SNAPSHOT_B)
    snap_a = cut_snapshot(corpus, SNAPSHOT_A)
    vuln = load_manifest(VULN_REL)
    patched = load_manifest(PATCH_REL)
    skill_only = {
        "id": "scratch-skill-only",
        "packages": [
            {
                "ecosystem": None,
                "kind": "prompt-payload",
                "name": None,
                "path": SKILL_REL,
                "version": None,
            }
        ],
    }
    vuln_b = scan_manifest(vuln, snap_b)
    patched_b = scan_manifest(patched, snap_b)
    vuln_a = scan_manifest(vuln, snap_a)
    skill_b = scan_manifest(skill_only, snap_b)
    hit_ids = [h["id"] for h in vuln_b["hits"]]
    detected = HIT_ID in hit_ids
    return {
        "seeded_manifest": VULN_REL,
        "patched_manifest": PATCH_REL,
        "snapshot_used_for_detection": SNAPSHOT_B,
        "seeded_scan": vuln_b,
        "patched_scan": patched_b,
        "seeded_against_snapshot_a": vuln_a,
        "skill_only_scan": skill_b,
        "positive_detection": detected,
        "patched_silent": patched_b["hit_count"] == 0,
        "seeded_silent_on_earlier_snapshot": vuln_a["hit_count"] == 0,
        "skill_never_detected": skill_b["hit_count"] == 0 and bool(skill_b["unscannable"]),
        "detected_ids": hit_ids,
        "pass": (
            detected
            and patched_b["hit_count"] == 0
            and vuln_a["hit_count"] == 0
            and skill_b["hit_count"] == 0
        ),
    }


def load_captures() -> dict[str, Any]:
    return load_json(CAPTURES_REL)


def catalog_sentinel() -> str:
    data = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == UNIT:
            return str(unit.get("completion_sentinel") or "")
    raise RuntimeError("RES-0051 missing from catalog")


def artifact_path() -> Path:
    return REPO / OUT_REL


if __name__ == "__main__":
    cmp = two_snapshot_comparison()
    ctl = seeded_control()
    print(json.dumps({"two_snapshot": {"pass": cmp["pass"], "verdict_a": cmp["verdict_a"], "verdict_b": cmp["verdict_b"], "appeared": cmp["appeared_ids"]}, "seeded": {"pass": ctl["pass"], "detected_ids": ctl["detected_ids"]}}, sort_keys=True))
    raise SystemExit(0 if cmp["pass"] and ctl["pass"] else 1)
