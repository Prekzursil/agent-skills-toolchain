"""Participant preparation and research-requirement enforcement (IMP-0362).

A seat may speak only when its preparation is *verified*, never when it is
merely *asserted*.  Verification has three legs and all three must hold:

1. an artifact exists: notes of a minimum length plus at least one named
   source anchor (a workspace-relative file or an http(s) URL);
2. every anchor resolves (the file stats in the workspace / the URL parses)
   AND is corroborated by a real fetch in the participant's tool-call log:
   a ``Read`` of that file or a ``WebFetch`` of that URL with ``status=ok``.
   A call whose status is ``asserted``/``claimed`` or that carries
   ``asserted: true`` is a self-report and never counts;
3. the notes are grounded in the fetched bytes: they share at least one
   distinctive token (a hyphenated identifier chain or a long word) with the
   content that was actually fetched (file bytes for Read, snippet for
   WebFetch).

Corroboration detector.  When an artifact *claims* preparation (it names a
source, or sets ``asserted_prepared``) and any named anchor has no real fetch
behind it, ``corroboration_fired`` is set and ``require_prepared`` raises
``AssertionWithoutFetchError``.  An empty or missing artifact is simply
unprepared (``UnpreparedError``): there is no claim to falsify, so the
detector stays silent on that path.

Kernel hook: ``before_turn(gate, speaker, artifacts=..., logs=...)`` is the
call the council kernel makes before granting a speaking turn.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

__all__ = [
    "ASSERTED_STATUSES",
    "AssertionWithoutFetchError",
    "FETCH_TOOLS",
    "MIN_ANCHORS",
    "MIN_NOTES_CHARS",
    "PrepArtifact",
    "PrepGate",
    "PrepVerdict",
    "ToolCall",
    "UnpreparedError",
    "before_turn",
    "digest_bytes",
    "distinctive_tokens",
    "is_url_anchor",
    "parse_tool_call",
]

MIN_NOTES_CHARS = 24
MIN_ANCHORS = 1
FETCH_TOOLS = frozenset({"Read", "WebFetch"})
ASSERTED_STATUSES = frozenset({"asserted", "claimed", "self-reported", "self_reported"})
URL_SCHEMES = frozenset({"http", "https"})

# A "distinctive" token is one unlikely to appear in generic prose: a chain
# of three or more hyphen-joined segments (``quorum-recusal-anchor-zeta``) or
# a single word of twelve or more characters.  Short generic words such as
# "reading", "required" or "prepared" never ground a note.
_CHAIN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+){2,}")
_LONG_WORD = re.compile(r"[a-z][a-z0-9_]{11,}")


class UnpreparedError(RuntimeError):
    """The seat is not prepared; the turn is refused.  Detector is silent."""

    def __init__(self, verdict: "PrepVerdict") -> None:
        super().__init__(verdict.summary())
        self.verdict = verdict


class AssertionWithoutFetchError(RuntimeError):
    """The seat asserted preparation the tool-call log does not corroborate."""

    def __init__(self, verdict: "PrepVerdict") -> None:
        super().__init__(verdict.summary())
        self.verdict = verdict


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def is_url_anchor(anchor: str) -> bool:
    try:
        parsed = urlparse(str(anchor))
    except ValueError:
        return False
    return parsed.scheme.lower() in URL_SCHEMES and bool(parsed.netloc)


def distinctive_tokens(text: str) -> set[str]:
    low = str(text or "").lower()
    return set(_CHAIN.findall(low)) | set(_LONG_WORD.findall(low))


@dataclass
class PrepArtifact:
    """What the participant hands in *before* the turn."""

    participant_id: str
    notes: str = ""
    source_anchors: list[str] = field(default_factory=list)
    asserted_prepared: bool = False
    path: str = ""

    def anchors(self) -> list[str]:
        out: list[str] = []
        for anc in self.source_anchors or []:
            text = str(anc or "").strip()
            if text and text not in out:
                out.append(text)
        return out

    def claims_preparation(self) -> bool:
        """True when the artifact asserts that reading happened."""
        return bool(self.asserted_prepared) or (
            bool(str(self.notes or "").strip()) and bool(self.anchors())
        )


@dataclass
class ToolCall:
    """One normalised row of the participant's tool-call log."""

    tool: str
    target: str = ""
    status: str = ""
    asserted: bool = False
    url: str = ""
    snippet: str = ""
    sha256: str = ""
    bytes: int = -1

    def is_real_fetch(self) -> bool:
        """A fetch counts only when it is a Read/WebFetch that really ran.

        Self-reports (``asserted: true`` or ``status`` in ASSERTED_STATUSES)
        and failed calls (any non-``ok`` status) are not fetches.
        """
        if self.asserted:
            return False
        status = (self.status or "").strip().lower()
        if status in ASSERTED_STATUSES:
            return False
        if status and status != "ok":
            return False
        if self.tool not in FETCH_TOOLS:
            return False
        return bool(self.target or self.url)

    def corroborates(self, anchor: str) -> bool:
        """Does this (real) fetch cover ``anchor``?  URLs need a WebFetch,
        files need a Read whose target is the same workspace-relative path."""
        if not self.is_real_fetch():
            return False
        if is_url_anchor(anchor):
            return self.tool == "WebFetch" and _same_url(self.url or self.target, anchor)
        if self.tool != "Read":
            return False
        return _same_rel_path(self.target, anchor)


def _same_url(a: str, b: str) -> bool:
    pa, pb = urlparse(a), urlparse(b)
    return (
        pa.scheme.lower() == pb.scheme.lower()
        and pa.netloc.lower() == pb.netloc.lower()
        and pa.path.rstrip("/") == pb.path.rstrip("/")
        and pa.query == pb.query
    )


def _same_rel_path(a: str, b: str) -> bool:
    if not a or not b:
        return False
    return Path(a.replace("\\", "/")).as_posix().lstrip("./") == Path(
        b.replace("\\", "/")
    ).as_posix().lstrip("./")


def parse_tool_call(row: dict[str, Any]) -> ToolCall:
    """Normalise a raw log row.  Both ``target`` and ``arguments.path`` /
    ``arguments.url`` spellings are accepted."""
    if not isinstance(row, dict):
        return ToolCall(tool="")
    args = row.get("arguments") if isinstance(row.get("arguments"), dict) else {}
    url = str(row.get("url") or args.get("url") or "")
    target = str(row.get("target") or args.get("path") or args.get("file_path") or url or "")
    status = str(row.get("status") or "")
    asserted = bool(row.get("asserted")) or status.strip().lower() in ASSERTED_STATUSES
    size = row.get("bytes")
    return ToolCall(
        tool=str(row.get("tool") or row.get("name") or ""),
        target=target,
        status=status,
        asserted=asserted,
        url=url,
        snippet=str(row.get("snippet") or row.get("content") or ""),
        sha256=str(row.get("sha256") or ""),
        bytes=int(size) if isinstance(size, int) else -1,
    )


@dataclass
class PrepVerdict:
    allowed_to_speak: bool
    prepared: bool
    corroboration_fired: bool
    notes_grounded: bool
    resolved_anchors: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    participant_id: str = ""
    corroborated_anchors: list[str] = field(default_factory=list)
    uncorroborated_anchors: list[str] = field(default_factory=list)
    real_fetches: int = 0
    asserted_calls: int = 0

    def summary(self) -> str:
        head = (
            "corroboration-fired"
            if self.corroboration_fired
            else ("prepared" if self.allowed_to_speak else "unprepared")
        )
        tail = "; ".join(self.reasons) if self.reasons else "-"
        return f"{head} participant={self.participant_id} speak={self.allowed_to_speak} {tail}"


class PrepGate:
    """Verifies preparation from artifact + tool-call log, never self-report."""

    def __init__(
        self,
        workspace: Path | str,
        *,
        min_notes_chars: int = MIN_NOTES_CHARS,
        min_anchors: int = MIN_ANCHORS,
    ) -> None:
        self.workspace = Path(workspace)
        self.min_notes_chars = int(min_notes_chars)
        self.min_anchors = int(min_anchors)

    # -- anchor resolution -------------------------------------------------
    def resolve_anchor(self, anchor: str) -> tuple[bool, str]:
        """Return (resolves, kind).  Files must stat inside the workspace."""
        if is_url_anchor(anchor):
            return True, "url"
        rel = str(anchor).replace("\\", "/")
        if rel.startswith("/") or rel.startswith(".."):
            return False, "file"
        path = (self.workspace / rel)
        try:
            resolved = path.resolve()
            root = self.workspace.resolve()
        except OSError:
            return False, "file"
        if root not in resolved.parents and resolved != root:
            return False, "file"
        return path.is_file(), "file"

    def fetched_bytes(self, anchor: str, call: ToolCall) -> bytes:
        """Bytes the fetch actually produced: file content for Read (only if
        the recorded sha256, when present, matches), snippet for WebFetch."""
        if call.tool == "WebFetch":
            return call.snippet.encode("utf-8")
        path = self.workspace / str(anchor).replace("\\", "/")
        try:
            raw = path.read_bytes()
        except OSError:
            return b""
        if call.sha256 and call.sha256.lower() != digest_bytes(raw):
            return b""
        return raw

    # -- verdict ------------------------------------------------------------
    def evaluate(
        self,
        participant_id: str,
        artifact: PrepArtifact | None,
        fetches: Iterable[dict[str, Any]] | None,
    ) -> PrepVerdict:
        pid = str(participant_id or getattr(artifact, "participant_id", "") or "")
        calls = [parse_tool_call(f) for f in (fetches or [])]
        real = [c for c in calls if c.is_real_fetch()]
        asserted_calls = sum(1 for c in calls if c.tool in FETCH_TOOLS and not c.is_real_fetch())
        reasons: list[str] = []

        # Leg 1: the artifact.  No artifact / no notes / no anchors is plain
        # unprepared; there is no claim for the detector to falsify.
        notes = str(getattr(artifact, "notes", "") or "").strip() if artifact else ""
        anchors = artifact.anchors() if artifact is not None else []
        if artifact is None:
            reasons.append("artifact-missing")
        if len(notes) < self.min_notes_chars:
            reasons.append("notes-missing-or-too-short")
        if len(anchors) < self.min_anchors:
            reasons.append("too-few-source-anchors")
        if artifact is None or not anchors or not notes:
            reasons.append("unprepared")
            return PrepVerdict(
                allowed_to_speak=False,
                prepared=False,
                corroboration_fired=False,
                notes_grounded=False,
                reasons=reasons,
                participant_id=pid,
                real_fetches=len(real),
                asserted_calls=asserted_calls,
            )

        # Leg 2: every anchor resolves AND is corroborated by a real fetch.
        resolved: list[str] = []
        corroborated: list[str] = []
        uncorroborated: list[str] = []
        fetched_blob: list[bytes] = []
        for anc in anchors:
            ok, kind = self.resolve_anchor(anc)
            if not ok:
                reasons.append(f"unresolved:{anc}")
                uncorroborated.append(anc)
                continue
            resolved.append(anc)
            hits = [c for c in real if c.corroborates(anc)]
            if not hits:
                why = "url-but-no-webfetch" if kind == "url" else "stat-ok-but-not-fetched"
                reasons.append(f"uncorroborated:{anc}:{why}")
                uncorroborated.append(anc)
                continue
            raw = b"".join(self.fetched_bytes(anc, c) for c in hits)
            if not raw:
                reasons.append(f"uncorroborated:{anc}:fetch-digest-mismatch-or-empty")
                uncorroborated.append(anc)
                continue
            corroborated.append(anc)
            fetched_blob.append(raw)

        # Leg 3: notes are grounded in what was actually fetched.
        fetched_text = b"\n".join(fetched_blob).decode("utf-8", errors="replace")
        shared = distinctive_tokens(notes) & distinctive_tokens(fetched_text)
        notes_grounded = bool(fetched_blob) and bool(shared)
        if not notes_grounded:
            reasons.append("notes-not-grounded-in-fetched-sources")

        # Detector: a claim of preparation that the log does not back.
        claims = artifact.claims_preparation()
        corroboration = bool(claims and uncorroborated)
        if corroboration:
            reasons.append("assertion-without-fetch")

        prepared = (
            len(anchors) >= self.min_anchors
            and len(notes) >= self.min_notes_chars
            and not uncorroborated
            and len(corroborated) == len(anchors)
            and notes_grounded
        )
        allowed = prepared and not corroboration
        if not allowed and not reasons:
            reasons.append("unprepared")
        return PrepVerdict(
            allowed_to_speak=allowed,
            prepared=prepared,
            corroboration_fired=corroboration,
            notes_grounded=notes_grounded,
            resolved_anchors=resolved,
            reasons=reasons,
            participant_id=pid,
            corroborated_anchors=corroborated,
            uncorroborated_anchors=uncorroborated,
            real_fetches=len(real),
            asserted_calls=asserted_calls,
        )

    def require_prepared(
        self,
        participant_id: str,
        artifact: PrepArtifact | None,
        fetches: Iterable[dict[str, Any]] | None,
    ) -> PrepVerdict:
        """Raise unless the seat may speak.  Corroboration outranks unprepared."""
        verdict = self.evaluate(participant_id, artifact, fetches)
        if verdict.corroboration_fired:
            raise AssertionWithoutFetchError(verdict)
        if not verdict.allowed_to_speak:
            raise UnpreparedError(verdict)
        return verdict


def before_turn(
    gate: PrepGate,
    speaker: dict[str, Any],
    artifacts: dict[str, PrepArtifact] | None = None,
    logs: dict[str, list[dict[str, Any]]] | None = None,
) -> PrepVerdict:
    """Kernel hook: called with the speaker record before the turn is granted."""
    pid = str((speaker or {}).get("participant_id") or (speaker or {}).get("id") or "")
    artifacts = artifacts or {}
    logs = logs or {}
    return gate.require_prepared(pid, artifacts.get(pid), logs.get(pid) or [])
