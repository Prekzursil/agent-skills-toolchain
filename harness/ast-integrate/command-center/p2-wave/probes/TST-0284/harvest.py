#!/usr/bin/env python3
"""Harvest three real program records and score the five mandatory elements.

Catalog-declared impossibility artifacts (CNF-0026, CNF-0098, RES-0149) are
checked first. CNF-0026 / CNF-0098 files are absent on this worktree; the
RES-0149 evidence-quality receipt exists but is a schema report, not a
five-element proof record. The three scored records are live on-disk
proof-of-impossibility / unobtainability products of other units.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from validator import MANDATORY, _as_text, missing_elements, validate

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

CATALOG_DECLARED = (
    "command-center/confirmation/CNF-0026-impossibility-records.json",
    "command-center/confirmation/CNF-0098-macos-reachability.json",
    "command-center/research/evidence-quality/RES-0149-proof-of-impossibility-record-schema.json",
)

# Three distinct producers. Pointers are resolved live from the files.
# IMP-0368's receipt is not on this worktree, so harvest is retargeted.
PINNED = (
    {
        "id": "IMP-0139-repair-loop-macos-proof",
        "path": "command-center/p2-wave/probes/IMP-0139/fixtures/impossibility.json",
        "producer": "IMP-0139",
        "kind": "repair_loop_proof",
    },
    {
        "id": "IMP-0311-hung-jury-binary-collapse",
        "path": "command-center/p2-wave/probes/IMP-0311/artifacts/proof_of_impossibility.final.json",
        "producer": "IMP-0311",
        "kind": "council_poi",
    },
    {
        "id": "AUD-0084-claude-falsifier-unobtainable",
        "path": "command-center/p2-wave/probes/AUD-0084/_refute_out.json",
        "producer": "AUD-0084",
        "kind": "blocked_failure",
    },
)


def _load(rel: str) -> Any:
    path = REPO / rel
    return json.loads(path.read_text(encoding="utf-8"))


def _space_from_domain(domain: Any) -> str | None:
    if not isinstance(domain, dict):
        text = _as_text(domain)
        return text or None
    name = _as_text(domain.get("name"))
    method = _as_text(domain.get("enumeration_method"))
    members = _as_text(domain.get("members"))
    parts = [p for p in (name, method, members) if p]
    return "; ".join(parts) if parts else None


def extract_record(spec: dict[str, Any]) -> dict[str, Any]:
    """Project a foreign artifact onto the five-element shape (holes kept)."""
    kind = spec["kind"]
    doc = _load(spec["path"])
    if kind == "repair_loop_proof":
        attempts = doc.get("attempts") or []
        proof: dict[str, Any] = {}
        if attempts and isinstance(attempts[0], dict):
            proof = attempts[0].get("proof") or {}
        se = proof.get("settling_experiment")
        if isinstance(se, dict):
            obs = " ".join(
                p
                for p in (
                    _as_text(se.get("description")),
                    _as_text(se.get("would_falsify_if")),
                )
                if p
            )
        else:
            obs = _as_text(se)
        return {
            "claim_shown_unobtainable": proof.get("why_unobtainable")
            or proof.get("claim_shown_impossible"),
            "search_space_covered": _space_from_domain(proof.get("exhaustive_domain")),
            "resource_limit_reached": proof.get("missing_prerequisite"),
            "refuting_observation": obs or None,
            "source_pointer": f"{spec['path']}#attempts/0/proof",
        }
    if kind == "council_poi":
        out = doc.get("outcome") if isinstance(doc.get("outcome"), dict) else doc
        return {
            "claim_shown_unobtainable": out.get("claim_shown_impossible")
            or out.get("claim_shown_unobtainable"),
            "search_space_covered": out.get("scope"),
            "source_pointer": f"{spec['path']}#outcome",
        }
    if kind == "blocked_failure":
        failure = doc.get("failure") or {}
        attempts = (doc.get("retry") or {}).get("attempts") or []
        methods = []
        for att in attempts:
            if not isinstance(att, dict):
                continue
            methods.append(
                {
                    "method": str(
                        att.get("error_fingerprint") or att.get("attempt") or "retry"
                    ),
                    "output": str(att.get("outcome") or ""),
                }
            )
        residuals = doc.get("residual_unknowns") or []
        settling = ""
        if residuals and isinstance(residuals[0], dict):
            settling = str(residuals[0].get("settling_experiment") or "")
        return {
            "claim_shown_unobtainable": failure.get("reason") or doc.get("sentinel"),
            "methods_attempted": methods or None,
            "resource_limit_reached": failure.get("blocked_on"),
            "refuting_observation": settling or None,
            "source_pointer": f"{spec['path']}#failure",
        }
    if kind == "residual_unknown":
        row = (doc.get("residual_unknowns") or [])[int(spec["index"])]
        return {
            "claim_shown_unobtainable": row.get("claim"),
            "refuting_observation": row.get("settling_experiment"),
            "source_pointer": f"{spec['path']}#residual_unknowns/{spec['index']}",
        }
    if kind == "planted_bad":
        planted = doc.get("planted_bad") or {}
        return {
            "claim_shown_unobtainable": planted.get("text"),
            "refuting_observation": planted.get("falsifier"),
            "source_pointer": f"{spec['path']}#planted_bad",
        }
    raise ValueError(f"unknown harvest kind {kind}")


def catalog_declared_status() -> list[dict[str, Any]]:
    rows = []
    for rel in CATALOG_DECLARED:
        path = REPO / rel
        rows.append(
            {
                "path": rel,
                "present": path.is_file() and path.stat().st_size > 0,
                "bytes": path.stat().st_size if path.is_file() else 0,
            }
        )
    return rows


def harvest() -> dict[str, Any]:
    declared = catalog_declared_status()
    scored: list[dict[str, Any]] = []
    for spec in PINNED:
        rel = spec["path"]
        path = REPO / rel
        if not path.is_file() or path.stat().st_size <= 0:
            raise FileNotFoundError(f"harvest source missing: {rel}")
        raw = extract_record(spec)
        pointer = raw.pop("source_pointer", rel)
        verdict = validate(raw)
        missing = missing_elements(raw)
        scored.append(
            {
                "id": spec["id"],
                "producer": spec["producer"],
                "path": rel,
                "pointer": pointer,
                "accepted": verdict["accepted"],
                "classification": verdict["classification"],
                "missing": missing,
                "missing_of_five": missing,
                "reasons": verdict["reasons"],
                "present_fields": [k for k in MANDATORY if k not in missing],
                "projected": {k: raw.get(k) for k in MANDATORY},
            }
        )
    if len(scored) < 3:
        raise RuntimeError(f"need >=3 harvested records, got {len(scored)}")
    present_declared = [d["path"] for d in declared if d["present"]]
    absent_declared = [d["path"] for d in declared if not d["present"]]
    return {
        "n": len(scored),
        "catalog_declared_impossibility_artifacts": declared,
        "records": scored,
        "all_rejected": all(not r["accepted"] for r in scored),
        "note": (
            "Catalog CNF-0026 / CNF-0098 files are absent"
            + (f" ({', '.join(absent_declared)})" if absent_declared else "")
            + ". Present declared paths: "
            + (", ".join(present_declared) if present_declared else "none")
            + ". Scored records are live products of IMP-0139, IMP-0311, and AUD-0084."
        ),
    }


if __name__ == "__main__":
    print(json.dumps(harvest(), indent=2, sort_keys=True)[:8000])
