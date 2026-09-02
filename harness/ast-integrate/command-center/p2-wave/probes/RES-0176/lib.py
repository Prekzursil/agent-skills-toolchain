#!/usr/bin/env python3
"""Shared harvest/claim helpers for RES-0176 (graph vs role vs group-chat)."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SNAP = HERE / "snapshots"
ARTIFACT_REL = (
    "command-center/research/teardown/"
    "RES-0176-teardown-graph-vs-role-frameworks.json"
)
ARTIFACT = REPO / ARTIFACT_REL
HARVEST_INDEX = HERE / "harvest_index.json"
HARVEST_META = HERE / "harvest_meta.json"
UID = "RES-0176"
SENTINEL = "SUCCESS:RES-0176"
MIN_BYTES = 256
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
SHERMAN_KENT = frozenset(
    {
        "almost certain",
        "highly probable",
        "probable",
        "even chance",
        "probably not",
        "almost certainly not",
    }
)

from sources import (  # noqa: E402
    ABSTRACTION_OWNER,
    FRAMEWORK_SNAPS,
    HARDNESS_NEEDLES,
    SOURCES,
)

SOURCE_BY_NAME = {s["name"]: s for s in SOURCES}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes()
    return sha256_bytes(raw.replace(b"\r\n", b"\n")), len(raw)


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "")


def strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text)


def searchable_text(path: Path) -> str:
    raw = path.read_bytes()
    text = raw.decode("utf-8", "replace")
    return "\n".join([text, strip_tags(text)])


def quote_in_snapshot(path: Path, quote: str) -> bool:
    if not quote or not path.is_file():
        return False
    blob = norm(searchable_text(path))
    return norm(quote) in blob


def load_meta_times() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if HARVEST_META.is_file():
        try:
            doc = json.loads(HARVEST_META.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            doc = {}
        for entry in doc.get("entries") or []:
            if isinstance(entry, dict) and entry.get("name"):
                out[str(entry["name"])] = entry
    return out


def build_harvest_index() -> dict[str, Any]:
    meta = load_meta_times()
    files: dict[str, Any] = {}
    for spec in SOURCES:
        name = spec["name"]
        path = SNAP / name
        if not path.is_file() or path.stat().st_size <= 0:
            raise FileNotFoundError(f"missing snapshot {name}")
        raw = path.read_bytes()
        sha = sha256_bytes(raw)
        prev = meta.get(name) or {}
        files[name] = {
            "name": name,
            "path": (
                "command-center/p2-wave/probes/RES-0176/snapshots/" + name
            ),
            "url": spec["url"],
            "rail": spec["rail"],
            "family": spec["family"],
            "http_status": int(prev.get("status") or 200),
            "bytes": len(raw),
            "sha256": sha,
            "fetched_at": prev.get("fetched_at") or utc_now(),
        }
    idx = {"unit_id": UID, "built_at": utc_now(), "files": files}
    HARVEST_INDEX.write_text(
        json.dumps(idx, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return idx


def load_harvest_index() -> dict[str, Any]:
    if not HARVEST_INDEX.is_file():
        return build_harvest_index()
    return json.loads(HARVEST_INDEX.read_text(encoding="utf-8"))


def rail(name: str, quote: str, idx: dict[str, Any]) -> dict[str, Any]:
    rec = idx["files"][name]
    path = SNAP / name
    if not quote_in_snapshot(path, quote):
        raise AssertionError(f"quote not in snapshot {name}: {quote[:80]!r}")
    live_sha = sha256_bytes(path.read_bytes())
    if live_sha != rec["sha256"]:
        raise AssertionError(f"stale harvest sha for {name}")
    return {
        "snapshot": name,
        "permalink": rec["url"],
        "resolved_url": rec["url"],
        "fetch_timestamp": rec["fetched_at"],
        "http_status": rec["http_status"],
        "sha256": rec["sha256"],
        "bytes": rec["bytes"],
        "quote": quote,
        "rail_kind": rec["rail"],
        "family": rec["family"],
        "independent_verification_path": (
            "probe1_quotes.py re-grep of captured bytes plus live sha256"
        ),
    }


def evidence_tier(n_rails: int, n_kinds: int) -> str:
    if n_rails >= 2 and n_kinds >= 2:
        return "E2"
    if n_rails >= 1:
        return "E3"
    return "E4"


def grade_claim(claim: dict[str, Any], idx: dict[str, Any] | None = None) -> dict[str, Any]:
    """Mechanical grader: two rails of distinct kinds + live sha + quote-in-bytes.

    One rail, or two rails of the same kind, => E3 and not citable as measured fact.
    """
    idx = idx or load_harvest_index()
    rails = claim.get("source_lineage") or claim.get("rails") or []
    problems: list[str] = []
    ok_rails = 0
    kinds: set[str] = set()
    for r in rails:
        if not isinstance(r, dict):
            problems.append("non-object-rail")
            continue
        snap = SNAP / str(r.get("snapshot") or "")
        quote = str(r.get("quote") or "")
        want_sha = str(r.get("sha256") or "")
        if not snap.is_file():
            problems.append(f"missing-snapshot:{snap.name}")
            continue
        live = sha256_bytes(snap.read_bytes())
        if live != want_sha:
            problems.append(f"sha-mismatch:{snap.name}")
            continue
        if int(r.get("http_status") or 0) != 200:
            problems.append(f"http:{r.get('http_status')}")
            continue
        if not quote_in_snapshot(snap, quote):
            problems.append(f"quote-absent:{snap.name}")
            continue
        if not r.get("permalink") or not r.get("fetch_timestamp"):
            problems.append(f"incomplete-rail:{snap.name}")
            continue
        kinds.add(str(r.get("rail_kind") or ""))
        ok_rails += 1
    if ok_rails >= 2 and len(kinds) < 2:
        problems.append("rails-not-independent-kinds")
    band = str(claim.get("confidence_band") or claim.get("sherman_kent_band") or "")
    if band.split("(")[0].strip().lower() not in SHERMAN_KENT:
        problems.append("sherman-kent-band-missing")
    vpath = str(
        claim.get("independent_verification_path")
        or claim.get("named_independent_verification_path")
        or ""
    )
    if len(vpath) < 8:
        problems.append("verification-path-missing")
    tier = evidence_tier(ok_rails, len(kinds))
    citable = tier == "E2" and not problems
    return {
        "ok_rails": ok_rails,
        "rail_kinds": sorted(kinds),
        "tier": tier,
        "citable_as_measured_fact": citable,
        "problems": problems,
    }


def snapshot_has(name: str, needle: str) -> bool:
    return quote_in_snapshot(SNAP / name, needle)


def hardness_scan() -> dict[str, Any]:
    """Owner snapshots contain the distinctive needle; the other two families do not."""
    rows = []
    for abstraction, needle in HARDNESS_NEEDLES.items():
        owner = ABSTRACTION_OWNER[abstraction]
        present_owner = any(
            snapshot_has(n, needle) for n in FRAMEWORK_SNAPS[owner]
        )
        others = {
            fam: any(snapshot_has(n, needle) for n in snaps)
            for fam, snaps in FRAMEWORK_SNAPS.items()
            if fam != owner
        }
        leaked = [fam for fam, hit in others.items() if hit]
        rows.append(
            {
                "abstraction": abstraction,
                "owner": owner,
                "needle": needle,
                "present_in_owner": present_owner,
                "present_in_others": leaked,
                "exclusive": present_owner and not leaked,
            }
        )
    return {
        "rows": rows,
        "all_exclusive": all(r["exclusive"] for r in rows),
    }


def transfer_verdict_errors(verdicts: list[Any]) -> list[str]:
    errs: list[str] = []
    if not isinstance(verdicts, list) or len(verdicts) < 3:
        return ["transfer-verdicts-lt-3"]
    not_transferable = 0
    seen = set()
    for v in verdicts:
        if not isinstance(v, dict):
            errs.append("verdict-not-object")
            continue
        aid = str(v.get("abstraction") or "")
        seen.add(aid)
        mech = str(v.get("mechanism") or "")
        runtime = str(v.get("runtime_host") or "")
        cost = str(v.get("reimplementation_cost") or "")
        if len(mech) < 16:
            errs.append(f"mechanism-thin:{aid}")
        if len(runtime) < 8:
            errs.append(f"runtime-host-missing:{aid}")
        if len(cost) < 16:
            errs.append(f"cost-thin:{aid}")
        if mech and runtime and mech == runtime:
            errs.append(f"mechanism-equals-runtime:{aid}")
        flag = v.get("transferable")
        if flag is False:
            not_transferable += 1
            svc = str(v.get("runtime_service") or "")
            if len(svc) < 8:
                errs.append(f"runtime-service-unnamed:{aid}")
        elif flag is not True:
            errs.append(f"transferable-not-bool:{aid}")
    for need in (
        "typed_state_graphs",
        "role_crew_delegation",
        "conversational_group_chat",
    ):
        if need not in seen:
            errs.append(f"missing-abstraction:{need}")
    if not_transferable < 1:
        errs.append("negative-control-absent-no-nontransferable")
    return errs
