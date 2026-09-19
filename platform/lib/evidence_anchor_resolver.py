"""Evidence-anchor resolution validator (TST-0331).

Parses receipt evidence fields and resolves each anchor by kind:

* ``file`` / ``file:line`` — the file exists *at the cited revision* and the
  line (or line range) is within that revision's blob. Line counts use
  ``git cat-file -p`` bytes (``splitlines()``), never the working tree.
* ``command`` — the quoted command appears in the recorded transcript
  (probe commands + raw_output).
* ``url`` — an archived copy is recorded (archive_url / wayback / archive.org).
* ``inferred`` — an explicit ``inferred-from:<named-source>`` statement.

An anchor that does not resolve is a fabricated citation. The report always
carries counts for checked / resolved / unresolved / unparseable plus the
full unresolved list.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

__all__ = [
    "AnchorKind",
    "ParsedAnchor",
    "Resolution",
    "ResolutionReport",
    "parse_anchor",
    "resolve_anchor",
    "resolve_evidence_item",
    "validate_receipt_evidence",
    "read_blob_at_revision",
    "line_count_at_revision",
]

REPO_DEFAULT = Path(__file__).resolve().parents[2]

# Path-ish tokens: allow drive letters, forward/back slashes, dots, hyphens.
_PATH_CHARS = r"[A-Za-z0-9_./\\@+~-]+"
_HEX_REV = r"[0-9a-fA-F]{7,40}"

# rev:<sha>:<path>:<line>[-<end>]
_RE_REV_FILE_LINE = re.compile(
    rf"^rev:(?P<rev>{_HEX_REV}):(?P<path>{_PATH_CHARS}):(?P<line>\d+)"
    rf"(?:-(?P<end>\d+))?$"
)
# <path>@<sha>:<line>[-<end>]
_RE_PATH_AT_REV = re.compile(
    rf"^(?P<path>{_PATH_CHARS})@(?P<rev>{_HEX_REV}):(?P<line>\d+)"
    rf"(?:-(?P<end>\d+))?$"
)
# file:<path>:<line>[-<end>]  OR  file:<path>
_RE_FILE_PREFIX = re.compile(
    rf"^file:(?P<path>{_PATH_CHARS})(?::(?P<line>\d+)(?:-(?P<end>\d+))?)?$"
)
# bare path:line[-end]  (path must contain / or \ or end in a known suffix)
_RE_BARE_FILE_LINE = re.compile(
    rf"^(?P<path>{_PATH_CHARS}):(?P<line>\d+)(?:-(?P<end>\d+))?$"
)
_RE_COMMAND = re.compile(
    r"^(?:command|cmd)\s*:\s*(?P<command>.+)$", re.IGNORECASE | re.DOTALL
)
_RE_URL_PREFIX = re.compile(r"^(?:url|uri)\s*:\s*(?P<url>\S+)$", re.IGNORECASE)
_RE_BARE_URL = re.compile(r"^(?P<url>https?://\S+)$", re.IGNORECASE)
_RE_INFERRED = re.compile(
    r"^(?:inferred-from|inferred)\s*:\s*(?P<source>.+)$", re.IGNORECASE
)

_FILE_SUFFIXES = (
    ".py",
    ".md",
    ".json",
    ".jsonl",
    ".txt",
    ".yml",
    ".yaml",
    ".toml",
    ".rs",
    ".go",
    ".ts",
    ".js",
    ".mjs",
    ".c",
    ".h",
    ".cpp",
    ".ps1",
    ".sh",
    ".css",
    ".html",
    ".schema.json",
)

_ARCHIVE_HINTS = (
    "archive.org",
    "web.archive.org",
    "archive.is",
    "archive.today",
    "perma.cc",
    "ghostarchive.org",
)


class AnchorKind:
    FILE = "file"
    COMMAND = "command"
    URL = "url"
    INFERRED = "inferred"
    UNPARSEABLE = "unparseable"


@dataclass(frozen=True)
class ParsedAnchor:
    kind: str
    raw: str
    path: str | None = None
    revision: str | None = None
    line: int | None = None
    end_line: int | None = None
    command: str | None = None
    url: str | None = None
    inferred_from: str | None = None
    parse_error: str | None = None


@dataclass
class Resolution:
    raw: str
    kind: str
    status: str  # resolved | unresolved | unparseable
    reason: str
    revision_used: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResolutionReport:
    anchors_checked: int
    resolved: int
    unresolved: int
    unparseable: int
    unresolved_list: list[dict[str, Any]]
    unparseable_list: list[dict[str, Any]]
    resolutions: list[dict[str, Any]]
    ok: bool  # True iff unresolved==0 and unparseable==0 and checked>0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def read_blob_at_revision(
    path: str, revision: str, *, repo: Path | None = None
) -> bytes:
    """Committed blob bytes via ``git cat-file -p``. Never the working tree."""
    root = repo or REPO_DEFAULT
    norm = path.replace("\\", "/")
    # Strip a leading "file:" if a caller passed one through.
    if norm.startswith("file:"):
        norm = norm[5:]
    proc = subprocess.run(
        ["git", "-C", str(root), "cat-file", "-p", f"{revision}:{norm}"],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace").strip()[:240]
        raise FileNotFoundError(
            f"path {norm!r} not present at revision {revision!r}: {err}"
        )
    return proc.stdout


def line_count_at_revision(
    path: str, revision: str, *, repo: Path | None = None
) -> int:
    """Logical line count of the blob at ``revision`` (splitlines semantics)."""
    data = read_blob_at_revision(path, revision, repo=repo)
    return len(data.splitlines())


def _looks_like_path(path: str) -> bool:
    if "/" in path or "\\" in path:
        return True
    lower = path.lower()
    return any(lower.endswith(suf) for suf in _FILE_SUFFIXES)


def parse_anchor(raw: str) -> ParsedAnchor:
    """Parse one evidence-anchor string into a typed structure."""
    text = (raw or "").strip()
    if not text:
        return ParsedAnchor(
            kind=AnchorKind.UNPARSEABLE,
            raw=raw or "",
            parse_error="empty anchor",
        )

    m = _RE_REV_FILE_LINE.match(text)
    if m:
        return ParsedAnchor(
            kind=AnchorKind.FILE,
            raw=text,
            path=m.group("path").replace("\\", "/"),
            revision=m.group("rev"),
            line=int(m.group("line")),
            end_line=int(m.group("end")) if m.group("end") else None,
        )

    m = _RE_PATH_AT_REV.match(text)
    if m:
        return ParsedAnchor(
            kind=AnchorKind.FILE,
            raw=text,
            path=m.group("path").replace("\\", "/"),
            revision=m.group("rev"),
            line=int(m.group("line")),
            end_line=int(m.group("end")) if m.group("end") else None,
        )

    m = _RE_FILE_PREFIX.match(text)
    if m:
        line = int(m.group("line")) if m.group("line") else None
        end = int(m.group("end")) if m.group("end") else None
        return ParsedAnchor(
            kind=AnchorKind.FILE,
            raw=text,
            path=m.group("path").replace("\\", "/"),
            line=line,
            end_line=end,
        )

    m = _RE_COMMAND.match(text)
    if m:
        cmd = m.group("command").strip()
        if not cmd:
            return ParsedAnchor(
                kind=AnchorKind.UNPARSEABLE,
                raw=text,
                parse_error="command anchor with empty command",
            )
        return ParsedAnchor(kind=AnchorKind.COMMAND, raw=text, command=cmd)

    m = _RE_URL_PREFIX.match(text) or _RE_BARE_URL.match(text)
    if m:
        return ParsedAnchor(kind=AnchorKind.URL, raw=text, url=m.group("url"))

    m = _RE_INFERRED.match(text)
    if m:
        src = m.group("source").strip()
        if not src:
            return ParsedAnchor(
                kind=AnchorKind.UNPARSEABLE,
                raw=text,
                parse_error="inferred-from with empty source",
            )
        return ParsedAnchor(kind=AnchorKind.INFERRED, raw=text, inferred_from=src)

    m = _RE_BARE_FILE_LINE.match(text)
    if m and _looks_like_path(m.group("path")):
        return ParsedAnchor(
            kind=AnchorKind.FILE,
            raw=text,
            path=m.group("path").replace("\\", "/"),
            line=int(m.group("line")),
            end_line=int(m.group("end")) if m.group("end") else None,
        )

    # Bare path without line (existence-only).
    if _looks_like_path(text) and " " not in text and not text.startswith("http"):
        return ParsedAnchor(
            kind=AnchorKind.FILE,
            raw=text,
            path=text.replace("\\", "/").removeprefix("file:"),
        )

    return ParsedAnchor(
        kind=AnchorKind.UNPARSEABLE,
        raw=text,
        parse_error="unrecognized anchor grammar",
    )


def _transcript_blob(evidence_item: Mapping[str, Any] | None) -> str:
    """Concatenate recorded probe commands + raw_output as the transcript."""
    if not evidence_item:
        return ""
    chunks: list[str] = []
    # Explicit transcript fields if present.
    for key in ("transcript", "recorded_transcript", "command_transcript"):
        val = evidence_item.get(key)
        if isinstance(val, str) and val.strip():
            chunks.append(val)
    for pr in evidence_item.get("probes") or []:
        if not isinstance(pr, dict):
            continue
        for key in ("command", "raw_output", "stdout", "stderr"):
            val = pr.get(key)
            if isinstance(val, str) and val:
                chunks.append(val)
    # Nested sources/verifiers arrays sometimes used outside schema.
    for key in ("sources", "verifiers", "runs"):
        for pr in evidence_item.get(key) or []:
            if isinstance(pr, dict):
                for k in ("command", "raw_output"):
                    val = pr.get(k)
                    if isinstance(val, str) and val:
                        chunks.append(val)
    return "\n".join(chunks)


def _archive_recorded(
    evidence_item: Mapping[str, Any] | None, url: str
) -> tuple[bool, str]:
    """Return whether an archived copy of ``url`` is recorded on the evidence item."""
    if not evidence_item:
        return False, "no evidence item to carry archive metadata"
    # Explicit fields.
    for key in (
        "archive_url",
        "archived_url",
        "archived_copy",
        "wayback_url",
        "archive",
    ):
        val = evidence_item.get(key)
        if isinstance(val, str) and val.strip():
            return True, f"archive recorded via {key}={val[:120]}"
        if isinstance(val, dict):
            href = val.get("url") or val.get("href") or val.get("archive_url")
            if isinstance(href, str) and href.strip():
                return True, f"archive recorded via {key}.url={href[:120]}"
    archives = evidence_item.get("archives")
    if isinstance(archives, list):
        for row in archives:
            if isinstance(row, str) and row.strip():
                return True, f"archive recorded in archives[]={row[:120]}"
            if isinstance(row, dict):
                href = row.get("url") or row.get("archive_url")
                if isinstance(href, str) and href.strip():
                    return True, f"archive recorded in archives[]={href[:120]}"
    # Probe transcripts mentioning an archive service + the original URL.
    blob = _transcript_blob(evidence_item).lower()
    if url.lower() in blob and any(h in blob for h in _ARCHIVE_HINTS):
        return True, "archive hint + original URL present in recorded transcript"
    return False, "no archived copy recorded for URL"


def _default_revision(
    parsed: ParsedAnchor, evidence_item: Mapping[str, Any] | None, default_rev: str
) -> str:
    if parsed.revision:
        return parsed.revision
    if evidence_item:
        for key in ("revision", "rev", "commit", "cited_revision", "git_rev"):
            val = evidence_item.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
        # probes may pin a rev
        for pr in evidence_item.get("probes") or []:
            if isinstance(pr, dict):
                for key in ("revision", "rev", "commit"):
                    val = pr.get(key)
                    if isinstance(val, str) and val.strip():
                        return val.strip()
    return default_rev


def resolve_anchor(
    parsed: ParsedAnchor,
    *,
    repo: Path | None = None,
    evidence_item: Mapping[str, Any] | None = None,
    default_revision: str = "HEAD",
    transcript: str | None = None,
) -> Resolution:
    """Resolve one parsed anchor. File checks always use revision-pinned blobs."""
    root = repo or REPO_DEFAULT

    if parsed.kind == AnchorKind.UNPARSEABLE:
        return Resolution(
            raw=parsed.raw,
            kind=parsed.kind,
            status="unparseable",
            reason=parsed.parse_error or "unparseable",
        )

    if parsed.kind == AnchorKind.FILE:
        assert parsed.path is not None
        rev = _default_revision(parsed, evidence_item, default_revision)
        try:
            n = line_count_at_revision(parsed.path, rev, repo=root)
        except FileNotFoundError as exc:
            return Resolution(
                raw=parsed.raw,
                kind=parsed.kind,
                status="unresolved",
                reason=str(exc),
                revision_used=rev,
                detail={"path": parsed.path, "fabricated_citation": True},
            )
        if parsed.line is None:
            return Resolution(
                raw=parsed.raw,
                kind=parsed.kind,
                status="resolved",
                reason=f"{parsed.path} exists at {rev} ({n} lines)",
                revision_used=rev,
                detail={"path": parsed.path, "line_count": n},
            )
        end = parsed.end_line if parsed.end_line is not None else parsed.line
        if parsed.line < 1 or end < parsed.line:
            return Resolution(
                raw=parsed.raw,
                kind=parsed.kind,
                status="unresolved",
                reason=f"invalid line range {parsed.line}-{end}",
                revision_used=rev,
                detail={
                    "path": parsed.path,
                    "line_count": n,
                    "fabricated_citation": True,
                },
            )
        if end > n:
            return Resolution(
                raw=parsed.raw,
                kind=parsed.kind,
                status="unresolved",
                reason=(
                    f"{parsed.path} at {rev} has only {n} lines; "
                    f"anchor cites {parsed.line}"
                    + (f"-{end}" if parsed.end_line else "")
                ),
                revision_used=rev,
                detail={
                    "path": parsed.path,
                    "line_count": n,
                    "cited_line": parsed.line,
                    "cited_end": parsed.end_line,
                    "fabricated_citation": True,
                },
            )
        return Resolution(
            raw=parsed.raw,
            kind=parsed.kind,
            status="resolved",
            reason=f"{parsed.path} at {rev} has {n} lines covering {parsed.line}"
            + (f"-{end}" if parsed.end_line else ""),
            revision_used=rev,
            detail={"path": parsed.path, "line_count": n, "cited_line": parsed.line},
        )

    if parsed.kind == AnchorKind.COMMAND:
        assert parsed.command is not None
        blob = transcript if transcript is not None else _transcript_blob(evidence_item)
        if parsed.command in blob:
            return Resolution(
                raw=parsed.raw,
                kind=parsed.kind,
                status="resolved",
                reason="quoted command appears in recorded transcript",
                detail={"command": parsed.command[:200]},
            )
        return Resolution(
            raw=parsed.raw,
            kind=parsed.kind,
            status="unresolved",
            reason="quoted command never appears in recorded transcript",
            detail={
                "command": parsed.command[:200],
                "fabricated_citation": True,
                "transcript_bytes": len(blob.encode("utf-8", errors="replace")),
            },
        )

    if parsed.kind == AnchorKind.URL:
        assert parsed.url is not None
        ok, why = _archive_recorded(evidence_item, parsed.url)
        if ok:
            return Resolution(
                raw=parsed.raw,
                kind=parsed.kind,
                status="resolved",
                reason=why,
                detail={"url": parsed.url},
            )
        return Resolution(
            raw=parsed.raw,
            kind=parsed.kind,
            status="unresolved",
            reason=why,
            detail={"url": parsed.url, "fabricated_citation": True},
        )

    if parsed.kind == AnchorKind.INFERRED:
        assert parsed.inferred_from is not None
        src = parsed.inferred_from.strip()
        if not src:
            return Resolution(
                raw=parsed.raw,
                kind=parsed.kind,
                status="unresolved",
                reason="inferred-from source is empty",
                detail={"fabricated_citation": True},
            )
        return Resolution(
            raw=parsed.raw,
            kind=parsed.kind,
            status="resolved",
            reason=f"explicit inferred-from source recorded: {src[:120]}",
            detail={"inferred_from": src},
        )

    return Resolution(
        raw=parsed.raw,
        kind=AnchorKind.UNPARSEABLE,
        status="unparseable",
        reason=f"unknown kind {parsed.kind!r}",
    )


def resolve_evidence_item(
    item: Mapping[str, Any],
    *,
    repo: Path | None = None,
    default_revision: str = "HEAD",
) -> Resolution:
    """Resolve the ``anchor`` field of one receipt evidence item."""
    raw = item.get("anchor")
    if not isinstance(raw, str):
        return Resolution(
            raw=str(raw),
            kind=AnchorKind.UNPARSEABLE,
            status="unparseable",
            reason="evidence item has no string anchor",
        )
    parsed = parse_anchor(raw)
    return resolve_anchor(
        parsed,
        repo=repo,
        evidence_item=item,
        default_revision=default_revision,
    )


def validate_receipt_evidence(
    receipt: Mapping[str, Any] | Sequence[Mapping[str, Any]] | str | Path,
    *,
    repo: Path | None = None,
    default_revision: str = "HEAD",
) -> ResolutionReport:
    """Validate every evidence anchor on a receipt (or a bare evidence list)."""
    root = repo or REPO_DEFAULT
    if isinstance(receipt, (str, Path)):
        path = Path(receipt)
        if not path.is_absolute():
            path = root / path
        doc = json.loads(path.read_text(encoding="utf-8"))
        items = [x for x in (doc.get("evidence") or []) if isinstance(x, dict)]
    elif isinstance(receipt, Mapping):
        items = [x for x in (receipt.get("evidence") or []) if isinstance(x, dict)]
    else:
        items = [x for x in receipt if isinstance(x, dict)]

    resolutions: list[Resolution] = []
    for item in items:
        resolutions.append(
            resolve_evidence_item(item, repo=root, default_revision=default_revision)
        )

    unresolved_list = [r.to_dict() for r in resolutions if r.status == "unresolved"]
    unparseable_list = [r.to_dict() for r in resolutions if r.status == "unparseable"]
    resolved_n = sum(1 for r in resolutions if r.status == "resolved")
    report = ResolutionReport(
        anchors_checked=len(resolutions),
        resolved=resolved_n,
        unresolved=len(unresolved_list),
        unparseable=len(unparseable_list),
        unresolved_list=unresolved_list,
        unparseable_list=unparseable_list,
        resolutions=[r.to_dict() for r in resolutions],
        ok=(
            len(resolutions) > 0
            and len(unresolved_list) == 0
            and len(unparseable_list) == 0
        ),
    )
    return report


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("receipt", nargs="+", help="receipt JSON path(s)")
    ap.add_argument("--repo", default=str(REPO_DEFAULT))
    ap.add_argument(
        "--revision", default="HEAD", help="default revision for unpinned file anchors"
    )
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    repo = Path(args.repo)
    worst = 0
    for spec in args.receipt:
        report = validate_receipt_evidence(
            spec, repo=repo, default_revision=args.revision
        )
        if args.json:
            print(json.dumps({"receipt": spec, **report.to_dict()}, indent=2))
        else:
            print(
                f"{'OK' if report.ok else 'FABRICATED'}:{spec} "
                f"checked={report.anchors_checked} resolved={report.resolved} "
                f"unresolved={report.unresolved} unparseable={report.unparseable}"
            )
            for row in report.unresolved_list:
                print(f"  UNRESOLVED {row['raw']!r}: {row['reason']}")
            for row in report.unparseable_list:
                print(f"  UNPARSEABLE {row['raw']!r}: {row['reason']}")
        if not report.ok:
            worst = 1
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
