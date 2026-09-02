#!/usr/bin/env python3
"""Resolve receipt evidence anchors against files, transcripts, and archives.

Line-range checks for a cited revision read git blob bytes (`git show <rev>:<path>`),
never the working tree. A URL resolves only when a local archived copy exists;
this module does not fetch the network. A quoted command resolves only when it
appears in the receipt's recorded transcript (tests / named_probes / transcripts),
not because it is written in the evidence item itself.
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

RESOLVED = "resolved"
UNRESOLVED = "unresolved"
UNPARSEABLE = "unparseable"

KIND_FILE_LINE = "file_line"
KIND_FILE = "file"
KIND_COMMAND = "command"
KIND_URL = "url"
KIND_INFERRED = "inferred"

EVIDENCE_KEYS = ("evidence", "evidence_anchors")

# path.ext:12  or path.ext:12-18  or path.ext:12@abc1234
_FILE_LINE = re.compile(
    r"^(?P<path>(?:[A-Za-z0-9_.@-]+/)*[A-Za-z0-9_.@-]+\.[A-Za-z0-9_.-]+)"
    r":(?P<line>\d+)(?:-(?P<end>\d+))?"
    r"(?:@(?P<rev>[0-9A-Fa-f]{7,40}))?$"
)
# path.ext:Symbol
_FILE_SYMBOL = re.compile(
    r"^(?P<path>(?:[A-Za-z0-9_.@-]+/)*[A-Za-z0-9_.@-]+\.[A-Za-z0-9_.-]+)"
    r":(?P<symbol>[A-Za-z_][A-Za-z0-9_]*)$"
)
_BARE_PATH = re.compile(
    r"^(?P<path>(?:[A-Za-z0-9_.@-]+/)*[A-Za-z0-9_.@-]+\.[A-Za-z0-9_.-]+)$"
)
_URL = re.compile(r"^https?://", re.I)


@dataclass
class Anchor:
    kind: str
    raw: str
    source: str
    index: int
    path: str | None = None
    line: int | None = None
    line_end: int | None = None
    revision: str | None = None
    snippet: str | None = None
    command: str | None = None
    url: str | None = None
    statement: str | None = None
    symbol: str | None = None

    def locator(self) -> str:
        if self.kind == KIND_FILE_LINE and self.path:
            loc = f"{self.path}:{self.line}"
            if self.line_end:
                loc += f"-{self.line_end}"
            if self.revision:
                loc += f"@{self.revision}"
            return loc
        if self.kind == KIND_FILE and self.path:
            if self.symbol:
                return f"{self.path}:{self.symbol}"
            return self.path
        if self.kind == KIND_COMMAND:
            return f"command:{self.command}"
        if self.kind == KIND_URL:
            return f"url:{self.url}"
        if self.kind == KIND_INFERRED:
            return f"inferred-from:{self.statement}"
        return self.raw

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["locator"] = self.locator()
        return d


@dataclass
class Resolution:
    anchor: Anchor
    status: str
    reason: str

    def as_dict(self) -> dict[str, Any]:
        row = self.anchor.as_dict()
        row["status"] = self.status
        row["reason"] = self.reason
        return row


@dataclass
class ResolveContext:
    root: Path
    git_cwd: Path | None = None
    archive_index: dict[str, str] = field(default_factory=dict)
    transcripts: list[str] = field(default_factory=list)


@dataclass
class Audit:
    checked: int
    resolved: list[dict[str, Any]]
    unresolved: list[dict[str, Any]]
    unparseable: list[dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "checked": self.checked,
            "resolved_count": len(self.resolved),
            "unresolved_count": len(self.unresolved),
            "unparseable_count": len(self.unparseable),
            "resolved": self.resolved,
            "unresolved": self.unresolved,
            "unparseable": self.unparseable,
        }


def _norm_path(value: str) -> str:
    text = value.strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text


def _intish(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def parse_locator(text: str) -> Anchor | None:
    raw = text.strip()
    if not raw:
        return None
    if _URL.match(raw):
        return Anchor(kind=KIND_URL, raw=raw, source="string", index=0, url=raw)
    m = _FILE_LINE.match(raw)
    if m:
        end = int(m.group("end")) if m.group("end") else None
        return Anchor(
            kind=KIND_FILE_LINE,
            raw=raw,
            source="string",
            index=0,
            path=_norm_path(m.group("path")),
            line=int(m.group("line")),
            line_end=end,
            revision=m.group("rev"),
        )
    m = _FILE_SYMBOL.match(raw)
    if m:
        return Anchor(
            kind=KIND_FILE,
            raw=raw,
            source="string",
            index=0,
            path=_norm_path(m.group("path")),
            symbol=m.group("symbol"),
        )
    m = _BARE_PATH.match(raw)
    if m:
        return Anchor(
            kind=KIND_FILE,
            raw=raw,
            source="string",
            index=0,
            path=_norm_path(m.group("path")),
        )
    return None


def _from_dict(item: dict[str, Any], source: str, index: int) -> Anchor:
    inferred = (
        item.get("inferred_from")
        or item.get("inferred-from")
        or item.get("inferredFrom")
    )
    if isinstance(inferred, str) and inferred.strip():
        return Anchor(
            kind=KIND_INFERRED,
            raw=json.dumps(item, sort_keys=True),
            source=source,
            index=index,
            statement=inferred.strip(),
        )
    url = item.get("url")
    if isinstance(url, str) and _URL.match(url.strip()):
        return Anchor(
            kind=KIND_URL,
            raw=json.dumps(item, sort_keys=True),
            source=source,
            index=index,
            url=url.strip(),
        )
    command = item.get("command")
    kind_hint = str(item.get("kind") or item.get("type") or "").lower()
    if isinstance(command, str) and command.strip() and (
        kind_hint in {"command", "cmd", "transcript"} or "path" not in item
    ):
        # Command-only evidence. If path+command both exist, prefer file then command
        # is still captured via a second pass in extract_anchors.
        if not item.get("path") and not item.get("anchor"):
            return Anchor(
                kind=KIND_COMMAND,
                raw=json.dumps(item, sort_keys=True),
                source=source,
                index=index,
                command=command.strip(),
            )
    path = item.get("path")
    line = _intish(item.get("line"))
    revision = item.get("revision") or item.get("rev") or item.get("commit")
    revision_s = str(revision).strip() if isinstance(revision, str) and revision.strip() else None
    snippet = item.get("snippet") or item.get("quote")
    snippet_s = str(snippet) if isinstance(snippet, str) and snippet.strip() else None
    if isinstance(path, str) and path.strip():
        npath = _norm_path(path)
        if line is not None:
            end = _intish(item.get("line_end") or item.get("end_line"))
            return Anchor(
                kind=KIND_FILE_LINE,
                raw=json.dumps(item, sort_keys=True),
                source=source,
                index=index,
                path=npath,
                line=line,
                line_end=end,
                revision=revision_s,
                snippet=snippet_s,
            )
        symbol = item.get("symbol") or item.get("name")
        return Anchor(
            kind=KIND_FILE,
            raw=json.dumps(item, sort_keys=True),
            source=source,
            index=index,
            path=npath,
            revision=revision_s,
            snippet=snippet_s,
            symbol=str(symbol) if isinstance(symbol, str) and symbol.strip() else None,
        )
    anchor = item.get("anchor")
    if isinstance(anchor, str) and anchor.strip():
        parsed = parse_locator(anchor.strip())
        if parsed is not None:
            parsed.source = source
            parsed.index = index
            parsed.raw = json.dumps(item, sort_keys=True)
            if revision_s and not parsed.revision:
                parsed.revision = revision_s
            if snippet_s and not parsed.snippet:
                parsed.snippet = snippet_s
            if line is not None and parsed.kind == KIND_FILE:
                parsed.kind = KIND_FILE_LINE
                parsed.line = line
            return parsed
    if isinstance(command, str) and command.strip():
        return Anchor(
            kind=KIND_COMMAND,
            raw=json.dumps(item, sort_keys=True),
            source=source,
            index=index,
            command=command.strip(),
        )
    detail = item.get("detail")
    if isinstance(detail, str) and detail.strip():
        parsed = parse_locator(detail.strip().split()[0] if " " in detail else detail.strip())
        if parsed is not None and parsed.kind in {KIND_FILE_LINE, KIND_FILE, KIND_URL}:
            parsed.source = source
            parsed.index = index
            parsed.raw = json.dumps(item, sort_keys=True)
            return parsed
    return Anchor(
        kind=UNPARSEABLE,
        raw=json.dumps(item, sort_keys=True),
        source=source,
        index=index,
    )


def extract_anchors(doc: Any, source: str = "receipt") -> list[Anchor]:
    if not isinstance(doc, dict):
        return [
            Anchor(kind=UNPARSEABLE, raw=type(doc).__name__, source=source, index=0)
        ]
    out: list[Anchor] = []
    for key in EVIDENCE_KEYS:
        val = doc.get(key)
        items: Iterable[Any]
        if val is None:
            continue
        if isinstance(val, list):
            items = list(val)
        else:
            items = [val]
        for i, item in enumerate(items):
            if isinstance(item, str):
                parsed = parse_locator(item)
                if parsed is None:
                    out.append(
                        Anchor(
                            kind=UNPARSEABLE,
                            raw=item,
                            source=f"{source}.{key}",
                            index=i,
                        )
                    )
                else:
                    parsed.source = f"{source}.{key}"
                    parsed.index = i
                    out.append(parsed)
            elif isinstance(item, dict):
                a = _from_dict(item, f"{source}.{key}", i)
                out.append(a)
                # A dict with both a file locator and a command is two claims.
                cmd = item.get("command")
                if (
                    isinstance(cmd, str)
                    and cmd.strip()
                    and a.kind in {KIND_FILE, KIND_FILE_LINE, KIND_URL, KIND_INFERRED}
                ):
                    out.append(
                        Anchor(
                            kind=KIND_COMMAND,
                            raw=json.dumps(item, sort_keys=True),
                            source=f"{source}.{key}",
                            index=i,
                            command=cmd.strip(),
                        )
                    )
            else:
                out.append(
                    Anchor(
                        kind=UNPARSEABLE,
                        raw=repr(item),
                        source=f"{source}.{key}",
                        index=i,
                    )
                )
    if not out and not any(doc.get(k) for k in EVIDENCE_KEYS):
        out.append(
            Anchor(
                kind=UNPARSEABLE,
                raw="no-evidence-fields",
                source=source,
                index=0,
            )
        )
    return out


def transcript_of(doc: dict[str, Any]) -> list[str]:
    cmds: list[str] = []
    for key in ("tests", "named_probes", "probes", "recorded_commands"):
        for item in doc.get(key) or []:
            if isinstance(item, str) and item.strip():
                cmds.append(item.strip())
            elif isinstance(item, dict):
                for field in ("command", "cmd", "verbatim", "text"):
                    val = item.get(field)
                    if isinstance(val, str) and val.strip():
                        cmds.append(val.strip())
    for item in doc.get("transcripts") or []:
        if isinstance(item, str) and item.strip():
            cmds.append(item.strip())
        elif isinstance(item, dict):
            val = item.get("text") or item.get("command") or ""
            if isinstance(val, str) and val.strip():
                cmds.append(val.strip())
    return cmds


def git_show(git_cwd: Path, revision: str, rel: str) -> tuple[bytes | None, str]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(git_cwd), "show", f"{revision}:{rel}"],
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"git-show-error:{type(exc).__name__}"
    if proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
        return None, f"git-show-failed:{err[:200] or proc.returncode}"
    return proc.stdout, "git-show"


def read_at_revision(ctx: ResolveContext, rel: str, revision: str | None) -> tuple[bytes | None, str]:
    if revision:
        if ctx.git_cwd is None:
            return None, "revision-cited-but-no-git"
        return git_show(ctx.git_cwd, revision, rel)
    path = ctx.root / rel
    if not path.is_file():
        return None, "missing-worktree-file"
    try:
        return path.read_bytes(), "worktree"
    except OSError as exc:
        return None, f"read-error:{exc}"


def _line_count(raw: bytes) -> list[str]:
    text = raw.decode("utf-8", errors="replace")
    return text.splitlines()


def _command_in_transcript(command: str, transcripts: list[str]) -> bool:
    needle = command.strip()
    if not needle:
        return False
    for line in transcripts:
        hay = line.strip()
        if needle == hay or needle in hay:
            return True
    return False


def resolve_anchor(anchor: Anchor, ctx: ResolveContext) -> Resolution:
    if anchor.kind == UNPARSEABLE:
        return Resolution(anchor, UNPARSEABLE, "unparseable-evidence-item")
    if anchor.kind == KIND_INFERRED:
        if anchor.statement and anchor.statement.strip():
            return Resolution(anchor, RESOLVED, "explicit-inferred-from")
        return Resolution(anchor, UNPARSEABLE, "empty-inferred-from")
    if anchor.kind == KIND_COMMAND:
        if not anchor.command:
            return Resolution(anchor, UNPARSEABLE, "empty-command")
        if _command_in_transcript(anchor.command, ctx.transcripts):
            return Resolution(anchor, RESOLVED, "command-in-transcript")
        return Resolution(anchor, UNRESOLVED, "command-never-run")
    if anchor.kind == KIND_URL:
        if not anchor.url:
            return Resolution(anchor, UNPARSEABLE, "empty-url")
        rel = ctx.archive_index.get(anchor.url)
        if not rel:
            parsed = urlparse(anchor.url)
            if parsed.scheme in {"http", "https"}:
                return Resolution(anchor, UNRESOLVED, "url-has-no-archived-copy")
            return Resolution(anchor, UNRESOLVED, "url-unsupported-scheme")
        archived = (ctx.root / rel) if not Path(rel).is_absolute() else Path(rel)
        if archived.is_file() and archived.stat().st_size > 0:
            return Resolution(anchor, RESOLVED, f"archived-copy:{rel}")
        return Resolution(anchor, UNRESOLVED, "archived-copy-missing-or-empty")
    if anchor.kind in {KIND_FILE, KIND_FILE_LINE}:
        if not anchor.path:
            return Resolution(anchor, UNPARSEABLE, "empty-path")
        raw, how = read_at_revision(ctx, anchor.path, anchor.revision)
        if raw is None:
            return Resolution(anchor, UNRESOLVED, how)
        lines = _line_count(raw)
        n = len(lines)
        if anchor.kind == KIND_FILE:
            if anchor.symbol:
                body = "\n".join(lines)
                if anchor.symbol not in body:
                    return Resolution(
                        anchor, UNRESOLVED, f"symbol-absent:{anchor.symbol}:{how}"
                    )
            if anchor.snippet:
                if anchor.snippet not in "\n".join(lines):
                    return Resolution(anchor, UNRESOLVED, f"snippet-miss:{how}")
            return Resolution(anchor, RESOLVED, f"file-exists:{how}:lines={n}")
        line = int(anchor.line or 0)
        end = int(anchor.line_end or line)
        if line < 1 or end < line or end > n:
            return Resolution(
                anchor, UNRESOLVED, f"line-out-of-range:{line}-{end}:n={n}:{how}"
            )
        window = "\n".join(lines[line - 1 : end])
        if anchor.snippet and anchor.snippet not in window:
            return Resolution(anchor, UNRESOLVED, f"snippet-miss:{how}")
        return Resolution(anchor, RESOLVED, f"line-in-range:{how}:n={n}")
    return Resolution(anchor, UNPARSEABLE, f"unknown-kind:{anchor.kind}")


def audit_receipt(doc: dict[str, Any], ctx: ResolveContext) -> Audit:
    merged = ResolveContext(
        root=ctx.root,
        git_cwd=ctx.git_cwd,
        archive_index=dict(ctx.archive_index),
        transcripts=list(ctx.transcripts) + transcript_of(doc),
    )
    resolved: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    unparseable: list[dict[str, Any]] = []
    anchors = extract_anchors(doc)
    for a in anchors:
        r = resolve_anchor(a, merged)
        row = r.as_dict()
        if r.status == RESOLVED:
            resolved.append(row)
        elif r.status == UNPARSEABLE:
            unparseable.append(row)
        else:
            unresolved.append(row)
    return Audit(
        checked=len(anchors),
        resolved=resolved,
        unresolved=unresolved,
        unparseable=unparseable,
    )


def audit_receipts(paths: Iterable[Path], ctx: ResolveContext) -> dict[str, Any]:
    per: list[dict[str, Any]] = []
    resolved: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    unparseable: list[dict[str, Any]] = []
    checked = 0
    for path in paths:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            unparseable.append(
                {
                    "source": str(path),
                    "status": UNPARSEABLE,
                    "reason": f"receipt-unparseable:{type(exc).__name__}",
                    "locator": str(path),
                }
            )
            continue
        if not isinstance(doc, dict):
            unparseable.append(
                {
                    "source": str(path),
                    "status": UNPARSEABLE,
                    "reason": "receipt-not-object",
                    "locator": str(path),
                }
            )
            continue
        audit = audit_receipt(doc, ctx)
        checked += audit.checked
        rel = path.as_posix()
        for row in audit.resolved:
            row["receipt"] = rel
            resolved.append(row)
        for row in audit.unresolved:
            row["receipt"] = rel
            unresolved.append(row)
        for row in audit.unparseable:
            row["receipt"] = rel
            unparseable.append(row)
        per.append(
            {
                "path": rel,
                "checked": audit.checked,
                "resolved_count": len(audit.resolved),
                "unresolved_count": len(audit.unresolved),
                "unparseable_count": len(audit.unparseable),
            }
        )
    return {
        "checked": checked,
        "resolved_count": len(resolved),
        "unresolved_count": len(unresolved),
        "unparseable_count": len(unparseable),
        "resolved": resolved,
        "unresolved": unresolved,
        "unparseable": unparseable,
        "receipts": per,
    }


def independent_file_line_ok(root: Path, rel: str, line: int) -> bool:
    """Ground truth for unpinned file:line: worktree bytes, not the validator."""
    path = root / rel
    if not path.is_file():
        return False
    try:
        n = len(path.read_bytes().decode("utf-8", errors="replace").splitlines())
    except OSError:
        return False
    return 1 <= line <= n
