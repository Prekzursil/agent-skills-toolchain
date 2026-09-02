#!/usr/bin/env python3
"""Shared contract checks for RES-0191 artifact + captures."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "RES-0191"
SENTINEL = "SUCCESS:RES-0191"
OUT_REL = (
    "command-center/research/deep-research-design/"
    "RES-0191-mid-run-backend-outage-resume.json"
)
ART = REPO / OUT_REL
INDEX = HERE / "captures" / "INDEX.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0191/probe1_kill_resume.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0191/probe2_pay_corrupt.py"
)
REQUIRED_STATUSES = {"not_started", "partial", "completed", "failed"}


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def load_index() -> dict[str, Any]:
    return json.loads(INDEX.read_text(encoding="utf-8"))


def verify_captures(index: dict[str, Any] | None = None) -> list[str]:
    idx = index or load_index()
    errors: list[str] = []
    for cap in idx.get("captures") or []:
        rel = cap.get("path")
        path = REPO / str(rel)
        if not path.is_file():
            errors.append(f"capture-missing:{rel}")
            continue
        live = sha256_bytes(path.read_bytes())
        if live != cap.get("sha256"):
            errors.append(f"capture-sha-mismatch:{cap.get('id')}")
        text = path.read_text(encoding="utf-8", errors="replace")
        for needle in cap.get("needles") or []:
            if needle not in text:
                errors.append(f"needle-miss:{cap.get('id')}:{needle}")
        if cap.get("ok") is not True:
            errors.append(f"capture-not-ok:{cap.get('id')}")
        if cap.get("http_status") != 200:
            errors.append(f"http:{cap.get('id')}:{cap.get('http_status')}")
    failed = idx.get("failed_ids") or idx.get("failed_ids") or []
    if failed:
        errors.append(f"failed_ids:{failed}")
    return errors


def snapshot_sha256(index: dict[str, Any] | None = None) -> str:
    idx = index or load_index()
    rows = []
    for cap in idx.get("captures") or []:
        rows.append({"id": cap["id"], "sha256": cap["sha256"], "path": cap["path"]})
    blob = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _rail_ok(rail: dict[str, Any]) -> str | None:
    for k in ("rail", "kind", "permalink", "fetch_timestamp", "http_status", "sha256"):
        if not rail.get(k):
            return f"rail-missing:{k}"
    if rail.get("http_status") != 200:
        return "rail-http"
    if not isinstance(rail.get("sha256"), str) or len(rail["sha256"]) != 64:
        return "rail-sha"
    return None


def evaluate_artifact(doc: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if doc.get("unit_id") != UNIT:
        errors.append("unit_id")
    if doc.get("kind") != "design-spec":
        errors.append("kind")
    if doc.get("state") != "SUCCESS":
        errors.append("state")
    if doc.get("sentinel") != SENTINEL:
        errors.append("sentinel-field")
    if SENTINEL not in json.dumps(doc):
        errors.append("sentinel-bytes")
    proto = doc.get("protocol") or {}
    fields = set(proto.get("durable_fields") or [])
    for need in (
        "query_id",
        "status",
        "harvest_index",
        "emitted_claim_ids",
        "backend_calls",
        "integrity_sha256",
    ):
        if need not in fields:
            errors.append(f"durable-field:{need}")
    if not REQUIRED_STATUSES.issubset(set(proto.get("statuses") or [])):
        errors.append("statuses")
    dist = doc.get("distinct_from") or {}
    if "RES-0004" not in dist or "RES-0171" not in dist:
        errors.append("distinct_from")
    t0004 = dist.get("RES-0004", "").lower()
    if "snapshot" not in t0004 and "fetch" not in t0004:
        errors.append("distinct_from-0004-text")
    t0171 = dist.get("RES-0171", "").lower()
    if "cache" not in t0171:
        errors.append("distinct_from-0171-text")
    bs = doc.get("both_states") or {}
    for k in (
        "resume_matches_control",
        "corrupt_refused",
        "naive_skip_drops_claims",
        "completed_not_repaid",
    ):
        if bs.get(k) is not True:
            errors.append(f"both_states:{k}")
    claims = doc.get("claims") or []
    if len(claims) < 4:
        errors.append("claims-short")
    probe_ids = set()
    for cl in claims:
        if cl.get("verdict") == "CONFIRMED":
            sp = str(cl.get("source_probe") or "")
            vp = str(cl.get("verifier_probe") or "")
            if not sp or not vp:
                errors.append(f"no-source-probe:{cl.get('claim_id')}")
            elif sp == vp:
                errors.append(f"same-probe-rerun:{cl.get('claim_id')}")
            probe_ids.add(sp)
            probe_ids.add(vp)
        rails = cl.get("rails") or []
        if len(rails) < 2:
            errors.append(f"single-rail:{cl.get('claim_id')}")
        kinds = {r.get("kind") for r in rails}
        if len(kinds) < 2:
            errors.append(f"rails-same-kind:{cl.get('claim_id')}")
        for r in rails:
            err = _rail_ok(r)
            if err:
                errors.append(f"{cl.get('claim_id')}:{err}")
        lin = cl.get("source_lineage") or []
        if not lin:
            errors.append(f"lineage:{cl.get('claim_id')}")
        if not cl.get("confidence_band"):
            errors.append(f"confidence:{cl.get('claim_id')}")
    tests = doc.get("tests") or []
    if len(tests) < 2:
        errors.append("tests-short")
    cmds = [t.get("command") for t in tests]
    if P1 not in cmds or P2 not in cmds:
        errors.append("tests-named-probes")
    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True:
        errors.append("reviewer-independent")
    if rev.get("default_without_evidence") != "REFUTED":
        errors.append("reviewer-default")
    arts = doc.get("artifacts") or []
    if not any(a.get("path") == OUT_REL and a.get("exists") is True for a in arts):
        errors.append("artifacts-primary")
    return errors
