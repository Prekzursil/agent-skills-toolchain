"""Research-stage runner with fail-closed tor/onion source-class gating."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from agentspec.source_policy import (
    OWNER_FLAG_PUBLIC_TOR,
    SOURCE_CLASSES,
    TOR_ALIASES,
    TOR_CLASS,
)


@dataclass
class SourceRequest:
    source_class: str
    locator: str = ""

    def __init__(self, source_class: str, locator: str = "", **kwargs: Any) -> None:
        del kwargs
        self.source_class = str(source_class)
        self.locator = str(locator)


@dataclass
class HarvestHit:
    source_class: str
    payload: str
    locator: str = ""


@dataclass
class ResearchResult:
    status: str
    results: list[HarvestHit] = field(default_factory=list)
    violation_id: str = ""
    egress_attempts: int = 0
    loud: bool = True
    partial: bool = False
    message: str = ""


def _canonical_class(name: str) -> str:
    if name in TOR_ALIASES:
        return TOR_CLASS
    return name


def _tor_requested(reqs: Sequence[SourceRequest]) -> bool:
    return any(_canonical_class(r.source_class) == TOR_CLASS for r in reqs)


def _unknown(reqs: Sequence[SourceRequest]) -> list[str]:
    out = []
    for r in reqs:
        if r.source_class not in SOURCE_CLASSES and _canonical_class(r.source_class) not in SOURCE_CLASSES:
            out.append(r.source_class)
    return out


def run_research_stage(unit: Any, requests: Iterable[SourceRequest], *, dry_run: bool = False) -> ResearchResult:
    reqs = list(requests)
    unknown = _unknown(reqs)
    if unknown:
        return ResearchResult(
            status="class-unknown",
            results=[],
            violation_id="source-class-unknown",
            egress_attempts=0,
            loud=True,
            partial=False,
            message=f"SOURCE-CLASS-UNAVAILABLE unknown={unknown}",
        )

    flags = tuple(getattr(unit, "owner_flags", ()) or ())
    allowed = tuple(getattr(unit, "source_policy", ()) or ())
    tor = _tor_requested(reqs)
    owner_ok = OWNER_FLAG_PUBLIC_TOR in flags

    if tor and not owner_ok:
        mixed = [r.source_class for r in reqs]
        return ResearchResult(
            status="owner-blocked",
            results=[],
            violation_id="source-class-owner-blocked",
            egress_attempts=0,
            loud=True,
            partial=False,
            message=(
                "SOURCE-CLASS-UNAVAILABLE: public-tor/onion requires "
                f"{OWNER_FLAG_PUBLIC_TOR}. Refusing a silent subset of {mixed}."
            ),
        )

    hits: list[HarvestHit] = []
    for r in reqs:
        klass = _canonical_class(r.source_class)
        if allowed and klass not in allowed and r.source_class not in allowed:
            return ResearchResult(
                status="owner-blocked",
                results=[],
                violation_id="source-class-owner-blocked",
                egress_attempts=0,
                loud=True,
                partial=False,
                message="SOURCE-CLASS-UNAVAILABLE class not in unit source_policy; refusing silent subset",
            )
        payload = "DRY-RUN" if dry_run else f"harvest:{klass}"
        hits.append(HarvestHit(source_class=klass, payload=payload, locator=r.locator))
    return ResearchResult(
        status="allowed",
        results=hits,
        violation_id="",
        egress_attempts=0 if dry_run else 1,
        loud=False,
        partial=False,
        message="ok",
    )
