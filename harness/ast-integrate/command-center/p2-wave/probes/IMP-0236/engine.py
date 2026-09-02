"""Interpret a blueprint's typed workflow against hermetic sources."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from claims import (
    evidence_class_coverage,
    forum_class_split,
    translation_distinctness,
    validate_harvest,
)
from classify import UnclassifiedPost
from contract import ContractError, validate_blueprint
from extract import EXTRACTORS
from policy import SourcePolicyError, enforce
from taxonomy import WORKING_LANGUAGE_DEFAULT

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"


class HarvestError(RuntimeError):
    pass


def _load_fixture(name: str) -> list[dict[str, Any]]:
    path = FIXTURES / name
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "sources" in data:
        return list(data["sources"])
    raise HarvestError(f"fixture {name} is not a source list")


def run_blueprint(
    blueprint: Mapping[str, Any],
    *,
    sources: list[Mapping[str, Any]] | None = None,
    policy: Mapping[str, Any] | None = None,
    working_language: str = WORKING_LANGUAGE_DEFAULT,
) -> dict[str, Any]:
    validate_blueprint(blueprint)
    bid = str(blueprint["id"])
    allowed = enforce(bid, policy)
    stopping = blueprint["stopping_rules"]
    if sources is None:
        fixture = blueprint["runnable_example"]["fixture"]
        sources = _load_fixture(fixture)

    halt_on = set(stopping.get("halt_on") or [])
    extractor = EXTRACTORS[bid]
    rejected: list[dict[str, Any]] = []
    try:
        claims = extractor(list(sources), working_language=working_language)
    except UnclassifiedPost as exc:
        if "unclassified-source" in halt_on or "missing-evidence-class" in halt_on:
            raise HarvestError(str(exc)) from exc
        raise

    max_claims = stopping.get("max_claims")
    if isinstance(max_claims, int) and len(claims) > max_claims:
        raise HarvestError(f"{bid}: stopping_rules.max_claims={max_claims} exceeded")

    validate_harvest(claims)
    cov = evidence_class_coverage(claims)
    if cov["coverage"] != 1.0:
        raise HarvestError(
            f"{bid}: evidence-class coverage {cov['coverage']} < 1.0 "
            f"untagged={cov['untagged_ids']}"
        )
    return {
        "blueprint_id": bid,
        "source_classes_allowed": allowed,
        "claim_count": len(claims),
        "rejected_count": len(rejected),
        "coverage": cov,
        "forum_split": forum_class_split(claims) if bid == "niche-forum" else None,
        "translation": translation_distinctness(claims)
        if bid == "multilingual"
        else None,
        "claims": claims,
    }


def run_named(
    library: Mapping[str, Mapping[str, Any]],
    blueprint_id: str,
    **kwargs: Any,
) -> dict[str, Any]:
    if blueprint_id not in library:
        raise HarvestError(f"unknown blueprint {blueprint_id}")
    return run_blueprint(library[blueprint_id], **kwargs)


def run_library(
    library: Mapping[str, Mapping[str, Any]],
    **kwargs: Any,
) -> dict[str, Any]:
    runs = {bid: run_named(library, bid, **kwargs) for bid in sorted(library)}
    claims = [c for run in runs.values() for c in run["claims"]]
    return {
        "runs": runs,
        "claims": claims,
        "coverage": evidence_class_coverage(claims),
        "forum_split": forum_class_split(claims),
        "translation": translation_distinctness(
            [c for c in claims if c.get("blueprint_id") == "multilingual"]
        ),
    }
