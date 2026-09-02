"""RES-0107 artifact contracts: two-rail claims, comparison metric, scale limit."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT_REL = "command-center/research/RES-0107.json"
SENTINEL = (
    "SUCCESS:RES-0107 in the receipt AND a cited comparison or an explicit "
    "downgrade to design-preference, plus a stated scale limit"
)
RAIL_FIELDS = (
    "kind",
    "permalink",
    "fetch_timestamp_utc",
    "http_status",
    "sha256",
    "bytes",
)
STRUCTURED = "structured-api"
PROSE = "prose-source"


def digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def load_doc(path: Path | None = None) -> dict[str, Any]:
    p = path or (REPO / OUT_REL)
    doc = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError("artifact is not an object")
    return doc


def rail_errors(rail: dict[str, Any], captures: Path) -> list[str]:
    errs: list[str] = []
    for key in RAIL_FIELDS:
        if key not in rail:
            errs.append(f"rail missing {key}")
    kind = str(rail.get("kind") or "")
    if kind not in {STRUCTURED, PROSE}:
        errs.append(f"rail kind {kind!r} not in {{{STRUCTURED}, {PROSE}}}")
    sha = str(rail.get("sha256") or "")
    if len(sha) != 64:
        errs.append("rail sha256 is not 64 hex chars")
    rel = str(rail.get("capture_path") or "")
    if rel:
        cap = REPO / rel
        if not cap.is_file():
            errs.append(f"capture missing {rel}")
        else:
            live = hashlib.sha256(cap.read_bytes()).hexdigest()
            if live != sha:
                errs.append(f"capture sha mismatch {rel}")
    status = rail.get("http_status")
    if not isinstance(status, int):
        errs.append("http_status not int")
    return errs


def two_rails_errors(claim: dict[str, Any], captures: Path) -> list[str]:
    rails = claim.get("rails") or []
    errs: list[str] = []
    if not isinstance(rails, list) or len(rails) < 2:
        return ["claim needs two rails"]
    kinds = {str(r.get("kind")) for r in rails if isinstance(r, dict)}
    if STRUCTURED not in kinds or PROSE not in kinds:
        errs.append("rails must include structured-api AND prose-source")
    for i, rail in enumerate(rails):
        if not isinstance(rail, dict):
            errs.append(f"rail[{i}] not object")
            continue
        errs.extend(f"rail[{i}] {e}" for e in rail_errors(rail, captures))
    return errs


def comparison_errors(doc: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    text = json.dumps(doc, sort_keys=True)
    if SENTINEL not in text and SENTINEL not in str(doc.get("sentinel") or ""):
        errs.append("catalog completion_sentinel string absent")
    if "SUCCESS:RES-0107" not in text:
        errs.append("SUCCESS:RES-0107 absent")
    metric = doc.get("comparison_metric")
    if not isinstance(metric, dict):
        return ["comparison_metric missing"]
    name = str(metric.get("name") or "").strip()
    if len(name) < 8:
        errs.append("comparison_metric.name too short")
    cited = metric.get("cited_measurement")
    if not isinstance(cited, dict):
        errs.append("cited_measurement missing")
    else:
        for key in ("value", "n_resolved", "n_total", "source_permalink"):
            if cited.get(key) in (None, ""):
                errs.append(f"cited_measurement.{key} missing")
    label = str(doc.get("competitive_vs_embeddings_label") or "")
    if label != "DESIGN-PREFERENCE":
        errs.append(
            "competitive vs embeddings must be labelled DESIGN-PREFERENCE "
            "(no same-harness embedding baseline cited)"
        )
    if not doc.get("competitive_claim_downgraded"):
        errs.append("competitive_claim_downgraded must be true")
    return errs


def scale_errors(doc: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    scale = doc.get("scale_limit")
    if not isinstance(scale, dict):
        return ["scale_limit missing"]
    n = scale.get("n_files")
    if not isinstance(n, int) or n < 1000:
        errs.append("scale_limit.n_files must be int >= 1000")
    if not str(scale.get("criterion") or "").strip():
        errs.append("scale_limit.criterion missing")
    if scale.get("too_slow_threshold_s") != 5.0:
        errs.append("scale_limit.too_slow_threshold_s must be 5.0")
    if str(scale.get("limiting_stage") or "") != "cold-tag-extraction-not-pagerank":
        errs.append("limiting_stage must name tag extraction, not a silent pagerank claim")
    return errs


def check_document(doc: dict[str, Any]) -> dict[str, Any]:
    captures = HERE / "captures"
    errs: list[str] = []
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        errs.append(f"self-declared {doc.get('state')}")
    if str(doc.get("unit_id") or "") != "RES-0107":
        errs.append("unit_id")
    claims = doc.get("claims") or []
    if not isinstance(claims, list) or len(claims) < 4:
        errs.append("need >=4 claims")
    else:
        for claim in claims:
            if not isinstance(claim, dict):
                errs.append("claim not object")
                continue
            cid = str(claim.get("id") or "")
            if claim.get("evidence_tier") == "E3" and claim.get("cited_as_measured_fact"):
                errs.append(f"{cid} E3 cited as measured fact")
            if len(claim.get("rails") or []) < 2:
                errs.append(f"{cid} single-rail")
            else:
                errs.extend(f"{cid} {e}" for e in two_rails_errors(claim, captures))
            if not str(claim.get("strongest_caveat") or "").strip():
                errs.append(f"{cid} missing strongest_caveat")
    errs.extend(comparison_errors(doc))
    errs.extend(scale_errors(doc))
    return {"pass": not errs, "errors": errs}


def mutant_competitive_without_downgrade(doc: dict[str, Any]) -> dict[str, Any]:
    mutant = copy.deepcopy(doc)
    mutant["competitive_vs_embeddings_label"] = "MEASURED-FACT"
    mutant["competitive_claim_downgraded"] = False
    mutant["claims"] = [
        c
        for c in (mutant.get("claims") or [])
        if isinstance(c, dict) and c.get("id") != "C-COMPETITIVE"
    ]
    mutant["claims"].insert(
        0,
        {
            "id": "C-COMPETITIVE",
            "claim": "Symbol-graph ranking is competitive with embedding retrieval.",
            "verdict": "CONFIRMED",
            "evidence_tier": "E1",
            "cited_as_measured_fact": True,
            "label": "MEASURED-FACT",
            "strongest_caveat": "",
            "rails": [],
        },
    )
    return mutant


def mutant_missing_scale(doc: dict[str, Any]) -> dict[str, Any]:
    mutant = copy.deepcopy(doc)
    mutant["scale_limit"] = {"note": "large repos are slow"}
    return mutant
