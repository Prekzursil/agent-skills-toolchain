#!/usr/bin/env python3
"""Load the CNF-0137 sampling universe.

Prefer live command-center/CLAIM-REGISTRY.json WHEN it is a 4-axis frame
(severity x subsystem x author-vendor x claim-type). If the live file is
absent, or present but missing required axes, load the frozen fixture and
record that fact. Never silently drop claims; never default missing
severity to low; never invent a live registry file; never merge live
rows into the fixture (that would mix denominators).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIVE_REGISTRY = REPO / "command-center" / "CLAIM-REGISTRY.json"
FIXTURE = HERE / "fixtures" / "sampling-universe.json"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
FIXTURE_REL = (
    "command-center/p2-wave/probes/CNF-0137/fixtures/sampling-universe.json"
)

KNOWN_CLAIM_ID = "C-CNF0137-KNOWN"
KNOWN_KEY = ("P2", "schema", "anthropic", "existence")
NOVEL_SUBSYSTEM = "novel-subsystem-cnf0137"


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def git_head() -> str | None:
    try:
        p = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if p.returncode != 0:
        return None
    sha = (p.stdout or "").strip()
    return sha or None


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_catalog_vendors() -> dict[str, str]:
    from frame import catalog_vendor_map

    if not CATALOG.is_file():
        return {}
    return catalog_vendor_map(load_json(CATALOG))


def _pack(
    *,
    live_present: bool,
    live_stratifiable: bool,
    live_error: str | None,
    live_n: int | None,
    origin: str,
    source_path: str,
    path: Path,
    doc: Any,
    claims: list[dict],
    raw: bytes,
    catalog_vendors: dict[str, str],
    known_claim_id: str,
    known_key: tuple[str, str, str, str],
) -> dict[str, Any]:
    return {
        "live_registry_present": live_present,
        "live_stratifiable": live_stratifiable,
        "live_error": live_error,
        "live_n": live_n,
        "origin": origin,
        "source_path": source_path,
        "abs_path": str(path),
        "doc": doc,
        "claims": claims,
        "sha256": _sha256_bytes(raw),
        "bytes": len(raw.replace(b"\r\n", b"\n")),
        "catalog_vendors": catalog_vendors,
        "commit_sha": git_head(),
        "frozen_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "known_claim_id": known_claim_id,
        "known_key": list(known_key),
    }


def _try_live_claims(doc: Any, catalog_vendors: dict[str, str]) -> dict[str, Any]:
    from frame import FrameBuildError, build_frame, extract_claim_list, locate_claim

    try:
        claims = extract_claim_list(doc)
    except FrameBuildError as exc:
        return {"ok": False, "error": str(exc), "n": None, "claims": None, "known": None}
    n = len(claims)
    try:
        frame = build_frame(claims, catalog_vendors)
    except FrameBuildError as exc:
        return {"ok": False, "error": str(exc), "n": n, "claims": claims, "known": None}
    ids = sorted(c.id for c in frame.claims)
    known_id = KNOWN_CLAIM_ID if KNOWN_CLAIM_ID in ids else ids[0]
    key, _ = locate_claim(frame, known_id)
    return {
        "ok": True,
        "error": None,
        "n": n,
        "claims": claims,
        "known": (known_id, key),
    }


def load_universe() -> dict[str, Any]:
    catalog_vendors = load_catalog_vendors()
    live_present = LIVE_REGISTRY.is_file() and LIVE_REGISTRY.stat().st_size > 0

    live_error = None
    live_n = None
    live_stratifiable = False
    if live_present:
        live_raw = LIVE_REGISTRY.read_bytes()
        live_doc = json.loads(live_raw.decode("utf-8"))
        attempt = _try_live_claims(live_doc, catalog_vendors)
        live_error = attempt["error"]
        live_n = attempt["n"]
        live_stratifiable = bool(attempt["ok"])
        if live_stratifiable:
            known_id, known_key = attempt["known"]
            return _pack(
                live_present=True,
                live_stratifiable=True,
                live_error=None,
                live_n=live_n,
                origin="live-claim-registry",
                source_path="command-center/CLAIM-REGISTRY.json",
                path=LIVE_REGISTRY,
                doc=live_doc,
                claims=attempt["claims"],
                raw=live_raw,
                catalog_vendors=catalog_vendors,
                known_claim_id=known_id,
                known_key=known_key,
            )

    raw = FIXTURE.read_bytes()
    doc = json.loads(raw.decode("utf-8"))
    from frame import extract_claim_list

    claims = extract_claim_list(doc)
    if live_present:
        origin = "frozen-fixture-live-registry-unstratifiable"
    else:
        origin = "frozen-fixture-live-registry-absent"
    return _pack(
        live_present=live_present,
        live_stratifiable=False,
        live_error=live_error,
        live_n=live_n,
        origin=origin,
        source_path=FIXTURE_REL,
        path=FIXTURE,
        doc=doc,
        claims=claims,
        raw=raw,
        catalog_vendors=catalog_vendors,
        known_claim_id=KNOWN_CLAIM_ID,
        known_key=KNOWN_KEY,
    )
