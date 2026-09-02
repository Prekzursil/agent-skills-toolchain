"""Fusion entry point: the licence matrix is consulted BEFORE any body is fused (IMP-0157).

:func:`fuse_workflows` is the real fusion API.  It hands the inbound licence list to
``licence_matrix.solve_licences`` (looked up through the module attribute at call
time, so the call path is observable) and raises :class:`FusionRefused` carrying the
matrix's named reason and suggested alternative when the combination is forbidden.
Only an allowed verdict yields a :class:`FusedWorkflow`; a refused fusion never
produces a body.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from workflow_foundry import licence_matrix


@dataclass(frozen=True)
class WorkflowSource:
    """One inbound workflow: its id, declared licence, body text and credit line."""

    id: str
    licence: str
    body: str
    credit: str = ""


@dataclass(frozen=True)
class FusedWorkflow:
    """The product of an allowed fusion: outbound licence, merged body, provenance."""

    id: str
    licence: str
    body: str
    sources: tuple[str, ...]
    credits: tuple[str, ...]
    verdict: licence_matrix.LicenceVerdict = field(repr=False)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "licence": self.licence,
            "body": self.body,
            "sources": list(self.sources),
            "credits": list(self.credits),
            "verdict": self.verdict.as_dict(),
        }


class FusionRefused(Exception):
    """Raised at the fusion entry when the licence matrix forbids the combination."""

    def __init__(self, verdict: licence_matrix.LicenceVerdict, sources: list[str]) -> None:
        self.verdict = verdict
        self.reason = verdict.reason
        self.suggested_alternative = verdict.suggested_alternative
        self.sources = list(sources)
        pair = " + ".join(verdict.failing_pair or verdict.canonical)
        super().__init__(
            f"fusion refused ({verdict.reason}): {pair}; "
            f"suggested alternative: {verdict.suggested_alternative}"
        )


def _credit_line(source: WorkflowSource) -> str:
    credit = source.credit.strip() if source.credit else "(no credit declared)"
    return f"# source: {source.id} licence: {source.licence} credit: {credit}\n"


def _with_newline(text: str) -> str:
    return text if text.endswith("\n") else text + "\n"


def fuse_workflows(
    sources: list[WorkflowSource] | tuple[WorkflowSource, ...],
    *,
    fused_id: str | None = None,
) -> FusedWorkflow:
    """Fuse ``sources`` into one workflow, or raise :class:`FusionRefused`.

    The licence solve happens first and gates everything else: if the matrix
    refuses, no body is assembled.  On an allowed verdict the bodies are
    concatenated in inbound order, each preceded by an attribution line, and the
    product carries the matrix's outbound (most restrictive compatible) licence.
    """
    ordered = list(sources)
    if not ordered:
        raise ValueError("fuse_workflows needs at least one WorkflowSource")
    for item in ordered:
        if not isinstance(item, WorkflowSource):
            raise TypeError(f"fuse_workflows expects WorkflowSource, got {type(item).__name__}")
    inbound = [item.licence for item in ordered]
    verdict = licence_matrix.solve_licences(inbound)
    if not verdict.allowed:
        raise FusionRefused(verdict, [item.id for item in ordered])
    body = "".join(_credit_line(item) + _with_newline(item.body) for item in ordered)
    return FusedWorkflow(
        id=fused_id or "+".join(item.id for item in ordered),
        licence=verdict.result_licence,
        body=body,
        sources=tuple(item.id for item in ordered),
        credits=tuple(item.credit for item in ordered),
        verdict=verdict,
    )


__all__ = ["FusedWorkflow", "FusionRefused", "WorkflowSource", "fuse_workflows"]
