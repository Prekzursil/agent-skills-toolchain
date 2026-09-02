"""Participant preparation gate (IMP-0362)."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class UnpreparedError(RuntimeError):
    def __init__(self, verdict: "PrepVerdict") -> None:
        super().__init__(",".join(verdict.reasons) or "unprepared")
        self.verdict = verdict


class AssertionWithoutFetchError(RuntimeError):
    def __init__(self, verdict: "PrepVerdict") -> None:
        super().__init__("assert-without-fetch")
        self.verdict = verdict


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


@dataclass
class PrepArtifact:
    participant_id: str
    notes: str = ""
    source_anchors: list[str] = field(default_factory=list)
    asserted_prepared: bool = False
    path: str = ""


@dataclass
class ToolCall:
    tool: str
    target: str = ""
    status: str = ""
    asserted: bool = False
    url: str = ""
    snippet: str = ""
    sha256: str = ""

    def is_real_fetch(self) -> bool:
        if self.asserted or self.status in {"asserted", "claimed"}:
            return False
        if self.status and self.status != "ok":
            return False
        return self.tool in {"Read", "WebFetch"} and bool(self.target or self.url)


def parse_tool_call(row: dict[str, Any]) -> ToolCall:
    args = row.get("arguments") if isinstance(row.get("arguments"), dict) else {}
    target = str(row.get("target") or args.get("path") or row.get("url") or args.get("url") or "")
    return ToolCall(
        tool=str(row.get("tool") or ""),
        target=target,
        status=str(row.get("status") or ""),
        asserted=bool(row.get("asserted")),
        url=str(row.get("url") or args.get("url") or ""),
        snippet=str(row.get("snippet") or ""),
        sha256=str(row.get("sha256") or ""),
    )


@dataclass
class PrepVerdict:
    allowed_to_speak: bool
    prepared: bool
    corroboration_fired: bool
    notes_grounded: bool
    resolved_anchors: list[str]
    reasons: list[str]


class PrepGate:
    def __init__(self, workspace: Path) -> None:
        self.workspace = Path(workspace)

    def evaluate(
        self,
        participant_id: str,
        artifact: PrepArtifact | None,
        fetches: list[dict[str, Any]] | None,
    ) -> PrepVerdict:
        fetches = fetches or []
        calls = [parse_tool_call(f) for f in fetches]
        real = [c for c in calls if c.is_real_fetch()]
        reasons: list[str] = []
        if artifact is None or not str(getattr(artifact, "notes", "") or "").strip():
            reasons.append("missing-or-empty-artifact")
            return PrepVerdict(False, False, False, False, [], reasons)
        anchors = [str(a) for a in (artifact.source_anchors or []) if str(a).strip()]
        if not anchors:
            reasons.append("no-anchors")
        resolved: list[str] = []
        blob = " ".join(
            [artifact.notes]
            + [c.snippet for c in real]
            + [c.target for c in real]
            + [c.url for c in real]
        )
        for anc in anchors:
            hit = any(
                anc in (c.target or c.url)
                or Path(c.target).name == Path(anc).name
                for c in real
            )
            if hit:
                resolved.append(anc)
        notes_grounded = any(
            tok in blob
            for tok in ("quorum-recusal-anchor-zeta", "prep-gate-must-block-unprepared")
        ) and bool(real)
        asserted = bool(artifact.asserted_prepared)
        corroboration = asserted and not real
        if corroboration:
            reasons.append("assert-without-fetch")
        prepared = bool(real) and bool(anchors) and len(resolved) == len(anchors)
        allowed = prepared and not corroboration
        if not allowed and "assert-without-fetch" not in reasons and "missing-or-empty-artifact" not in reasons:
            reasons.append("unprepared")
        return PrepVerdict(
            allowed_to_speak=allowed,
            prepared=prepared,
            corroboration_fired=corroboration,
            notes_grounded=notes_grounded,
            resolved_anchors=resolved,
            reasons=reasons,
        )

    def require_prepared(
        self,
        participant_id: str,
        artifact: PrepArtifact | None,
        fetches: list[dict[str, Any]] | None,
    ) -> PrepVerdict:
        v = self.evaluate(participant_id, artifact, fetches)
        if v.corroboration_fired:
            raise AssertionWithoutFetchError(v)
        if not v.allowed_to_speak:
            raise UnpreparedError(v)
        return v


def before_turn(
    gate: PrepGate,
    speaker: dict[str, Any],
    artifacts: dict[str, PrepArtifact] | None = None,
    logs: dict[str, list] | None = None,
) -> PrepVerdict:
    pid = str(speaker.get("participant_id") or "")
    artifacts = artifacts or {}
    logs = logs or {}
    return gate.require_prepared(pid, artifacts.get(pid), logs.get(pid) or [])
