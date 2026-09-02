#!/usr/bin/env python3
"""RES-0026 contract helpers: two-rail evidence and client-vs-server classifier."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "RES-0026"
OUT_REL = "command-center/research/RES-0026.json"
SCHEMA_REL = (
    "command-center/p2-wave/probes/RES-0026/research-claim-record.local.schema.json"
)
CATALOG_SCHEMA = "command-center/schema/research-claim-record.schema.json"
SENTINEL = (
    "SUCCESS:RES-0026 in the receipt AND a control table with a "
    "client-vs-server enforcement column justified per row"
)
ENFORCEMENT = frozenset(
    {
        "CLIENT-SIDE",
        "SERVER-ENFORCED",
        "HYBRID",
        "NOT-ENFORCED-ON-SURFACE",
    }
)
MEASURED_TIERS = frozenset({"E1", "E2"})


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def artifact_path() -> Path:
    return REPO / OUT_REL


def load_artifact() -> dict:
    return load_json(artifact_path())


def load_schema() -> dict:
    return load_json(REPO / SCHEMA_REL)


def validate_schema(doc: dict) -> None:
    import jsonschema

    jsonschema.validate(instance=doc, schema=load_schema())


def capture_text(rel: str) -> str:
    raw = (REPO / rel).read_bytes()
    text = raw.decode("utf-8", "replace")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return text
    if isinstance(doc, dict) and doc.get("encoding") == "base64" and doc.get("content"):
        import base64

        blob = base64.b64decode(doc["content"]).decode("utf-8", "replace")
        return text + "\n" + blob
    return text


def host_of(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def rail_errors(claim: dict, require_live_hash: bool = True) -> list[str]:
    errs: list[str] = []
    cid = claim.get("id", "?")
    lineage = claim.get("source_lineage") or []
    if not isinstance(lineage, list) or len(lineage) < 2:
        return [f"{cid}: source_lineage needs two rails"]
    kinds = []
    hosts = []
    for i, rail in enumerate(lineage):
        if not isinstance(rail, dict):
            errs.append(f"{cid}: rail[{i}] not an object")
            continue
        kinds.append(str(rail.get("rail") or ""))
        hosts.append(host_of(str(rail.get("permalink") or "")))
        if rail.get("http_status") != 200:
            errs.append(f"{cid}: rail[{i}] http_status={rail.get('http_status')}")
        sha = str(rail.get("sha256") or "")
        rel = str(rail.get("capture_path") or "")
        if require_live_hash:
            cap = REPO / rel
            if not cap.is_file():
                errs.append(f"{cid}: missing capture {rel}")
                continue
            live = digest_bytes(cap.read_bytes())
            if live != sha:
                errs.append(f"{cid}: sha mismatch {rel}")
            quote = str(rail.get("quote") or "")
            if len(quote) < 12:
                errs.append(f"{cid}: rail[{i}] quote too short")
            elif quote not in capture_text(rel):
                errs.append(f"{cid}: quote not in capture {rel}")
        for key in (
            "permalink",
            "fetch_timestamp",
            "http_status",
            "sha256",
        ):
            if rail.get(key) in (None, ""):
                errs.append(f"{cid}: rail[{i}] missing {key}")
    if "structured-api" not in kinds:
        errs.append(f"{cid}: missing structured-api rail")
    if "prose-source" not in kinds:
        errs.append(f"{cid}: missing prose-source rail")
    live_hosts = [h for h in hosts if h]
    if len(set(live_hosts)) < 2:
        errs.append(f"{cid}: rails share a host ({live_hosts}); not independent")
    tier = str(claim.get("evidence_tier") or "")
    if tier in MEASURED_TIERS and len(lineage) < 2:
        errs.append(f"{cid}: measured tier {tier} with <2 rails")
    return errs


def control_table_errors(table) -> list[str]:
    errs: list[str] = []
    if not isinstance(table, list) or len(table) < 4:
        return ["control_table missing or too short"]
    server = 0
    for i, row in enumerate(table):
        if not isinstance(row, dict):
            errs.append(f"row[{i}] not an object")
            continue
        enf = str(row.get("client_vs_server_enforcement") or "")
        just = str(row.get("justification") or "")
        if enf not in ENFORCEMENT:
            errs.append(f"{row.get('control_id', i)}: bad enforcement {enf!r}")
        if len(just) < 24:
            errs.append(f"{row.get('control_id', i)}: justification too short")
        if "portable_to_local_runtime" not in row or not isinstance(
            row.get("portable_to_local_runtime"), bool
        ):
            errs.append(f"{row.get('control_id', i)}: portable_to_local_runtime not bool")
        if enf == "SERVER-ENFORCED":
            server += 1
            if row.get("portable_to_local_runtime") is True:
                errs.append(
                    f"{row.get('control_id')}: SERVER-ENFORCED marked portable "
                    "(the specific error this unit exists to prevent)"
                )
    if server < 1:
        errs.append("classifier-suspect: zero SERVER-ENFORCED rows")
    return errs


def classifier_suspect(table) -> bool:
    return any("classifier-suspect" in e for e in control_table_errors(table))


def artifact_errors(doc: dict, require_live_hash: bool = True) -> list[str]:
    errs: list[str] = []
    if doc.get("unit_id") != UNIT:
        errs.append("unit_id")
    if SENTINEL not in json.dumps(doc, sort_keys=True):
        errs.append("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        errs.append(f"self-declared:{st}")
    try:
        validate_schema(doc)
    except Exception as exc:
        errs.append(f"schema:{type(exc).__name__}:{exc}")
    for claim in doc.get("claims") or []:
        if isinstance(claim, dict):
            errs.extend(rail_errors(claim, require_live_hash=require_live_hash))
    errs.extend(control_table_errors(doc.get("control_table")))
    return errs
