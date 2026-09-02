#!/usr/bin/env python3
"""Shared contract checks for RES-0039 probes (no network)."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center/research/RES-0039.json"
SCHEMA = REPO / "command-center/schema/threat-model.schema.json"
PROFILES = REPO / "platform/schema/artifact-class-profiles.schema.json"
RECEIPT_SCHEMA = REPO / "platform/schema/receipt.schema.json"
SENTINEL = (
    "SUCCESS:RES-0039 in the receipt AND an attack-class table where every "
    "mitigation row carries an attempted-bypass outcome"
)
REQUIRED_IDS = {
    "tool-poisoning",
    "description-injection",
    "confused-deputy",
    "rug-pull-update",
    "cross-server-shadowing",
}


def digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def payload(doc: dict) -> dict:
    """Domain fields live under report when the receipt_core envelope is used."""
    report = doc.get("report")
    if isinstance(report, dict) and (
        report.get("attack_class_table") or report.get("kind") == "threat-model"
    ):
        return report
    return doc


def local_validator() -> jsonschema.Draft202012Validator:
    """Resolve ast-integrate.invalid $ref from disk. Never hit the network."""
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    profiles = json.loads(PROFILES.read_text(encoding="utf-8"))
    receipt = json.loads(RECEIPT_SCHEMA.read_text(encoding="utf-8"))
    store = {
        str(schema.get("$id") or ""): schema,
        str(profiles.get("$id") or ""): profiles,
        str(receipt.get("$id") or ""): receipt,
        "https://ast-integrate.invalid/command-center/schema/threat-model.schema.json": schema,
        "https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json": profiles,
        "https://ast-integrate.invalid/platform/schema/receipt.schema.json": receipt,
    }
    resolver = jsonschema.RefResolver(
        base_uri=str(schema.get("$id") or SCHEMA.as_uri()),
        referrer=schema,
        store=store,
    )
    return jsonschema.Draft202012Validator(schema, resolver=resolver)


def load_artifact() -> dict:
    if not ART.is_file() or ART.stat().st_size <= 0:
        raise RuntimeError("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        raise RuntimeError("catalog sentinel absent")
    if doc.get("unit_id") != "RES-0039":
        raise RuntimeError("unit_id mismatch")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        raise RuntimeError(f"self-declared {doc.get('state')}")
    return doc


def validate_schema(doc: dict) -> None:
    local_validator().validate(doc)


def schema_errors(doc: dict) -> list[str]:
    return [e.message for e in local_validator().iter_errors(doc)]


def check_table(doc: dict) -> dict:
    body = payload(doc)
    table = body.get("attack_class_table") or []
    ids = {row.get("id") for row in table if isinstance(row, dict)}
    if ids != REQUIRED_IDS:
        raise RuntimeError(f"attack class ids {ids} != {REQUIRED_IDS}")
    outcomes = []
    missing = []
    for row in table:
        inst = row.get("local_instantiation") or {}
        if inst.get("third_party_system_touched") is not False:
            raise RuntimeError(f"{row.get('id')} touched a third party")
        if not inst.get("path") or not inst.get("observation"):
            raise RuntimeError(f"{row.get('id')} local instantiation incomplete")
        mits = row.get("mitigations") or []
        if not mits:
            raise RuntimeError(f"{row.get('id')} has no mitigations")
        for mit in mits:
            out = mit.get("attempted_bypass_outcome")
            if out not in {"SURVIVED", "BYPASSED", "INCONCLUSIVE"}:
                missing.append(mit.get("id") or row.get("id"))
            else:
                outcomes.append(out)
            if not mit.get("attempted_bypass"):
                missing.append(mit.get("id"))
    if missing:
        raise RuntimeError(f"mitigations missing bypass outcome: {missing}")
    survived = outcomes.count("SURVIVED")
    bypassed = outcomes.count("BYPASSED")
    if survived < 1:
        raise RuntimeError("honesty control: zero mitigations survived")
    if bypassed < 1:
        raise RuntimeError("honesty control: zero mitigations bypassed")
    if int(body.get("surviving_mitigation_count") or 0) != survived:
        raise RuntimeError("surviving_mitigation_count does not match table")
    if body.get("third_party_exploit_executed") is not False:
        raise RuntimeError("third_party_exploit_executed must be false")
    return {"survived": survived, "bypassed": bypassed, "n_classes": len(table)}


def check_dual_rails(doc: dict) -> int:
    body = payload(doc)
    n = 0
    for claim in body.get("claims") or []:
        rails = claim.get("rails") or []
        kinds = {r.get("kind") for r in rails if isinstance(r, dict)}
        if "structured-api" not in kinds or "prose-source" not in kinds:
            raise RuntimeError(f"{claim.get('id')} missing dual rails {kinds}")
        if (claim.get("evidence_tier") or "E3") == "E3":
            raise RuntimeError(f"{claim.get('id')} graded E3 with dual rails present")
        for rail in rails:
            for key in ("permalink", "fetched_at", "http_status", "sha256"):
                if not rail.get(key):
                    raise RuntimeError(f"{claim.get('id')} rail missing {key}")
            if int(rail.get("http_status") or 0) < 200:
                raise RuntimeError(f"{claim.get('id')} rail http {rail.get('http_status')}")
            n += 1
    snaps = HERE / "snapshots"
    index = json.loads((snaps / "index.json").read_text(encoding="utf-8"))
    for rec in index.get("rails") or []:
        body_path = REPO / rec["snapshot"]
        if not body_path.is_file():
            raise RuntimeError(f"snapshot missing {rec['snapshot']}")
        live = hashlib.sha256(body_path.read_bytes()).hexdigest()
        if live != rec.get("sha256"):
            raise RuntimeError(f"snapshot sha mismatch {rec['id']}")
    return n


def mutant_strip_outcomes(doc: dict) -> dict:
    mutant = copy.deepcopy(doc)
    table = payload(mutant).get("attack_class_table") or []
    for row in table:
        for mit in row["mitigations"]:
            mit.pop("attempted_bypass_outcome", None)
    return mutant


def mutant_all_bypassed(doc: dict) -> dict:
    mutant = copy.deepcopy(doc)
    body = payload(mutant)
    for row in body["attack_class_table"]:
        for mit in row["mitigations"]:
            mit["attempted_bypass_outcome"] = "BYPASSED"
    body["surviving_mitigation_count"] = 0
    return mutant
