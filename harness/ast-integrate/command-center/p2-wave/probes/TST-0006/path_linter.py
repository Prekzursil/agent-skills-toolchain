"""Cite-vs-mention path linter for agent result payloads.

A path-shaped token in text is not proof the file exists. This module extracts
path-shaped tokens, stats them on disk, and downgrades a payload to
UNVERIFIED-PATH when a *cited* (non-illustrative) path is absent.

Illustrative mentions live in fenced code blocks (``` ... ```), including
fences nested inside JSON string values. Those are use-vs-mention MENTION
tokens and do not trigger the downgrade.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

UNVERIFIED = "UNVERIFIED-PATH"
VERIFIED = "VERIFIED-PATHS"

# Trailing junk commonly glued to tokens in JSON / prose.
_TRAIL = " \t\r\n,;:.)]}'\"`\\"

# Repo-relative roots that appear throughout this estate's agent payloads.
_REPO_ROOTS = (
    "command-center/",
    "tools/",
    "platform/",
    "ci/",
    "tests/",
    "docs/",
    "rules/",
    "harness/",
    "workflows/",
)

_WIN_ABS = re.compile(r"^[A-Za-z]:[\\/]")
_POSIX_ABS = re.compile(r"^/(?:opt|home|Users|tmp|var|etc|root|usr)/")
_REL_EXT = re.compile(
    r"^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+\.[A-Za-z][A-Za-z0-9]{0,11}$"
)
_URL = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")

# JSON keys whose unfenced path tokens are documentary mentions, not citations.
DOCUMENTARY_KEYS = frozenset(
    {
        "question_or_target",
        "question",
        "example",
        "snippet",
        "original_preview",
        "notes",
        "doc",
        "documentation",
        "prompt",
        "body",
        "markdown",
        "title",
        "catalog_title",
        "evidence_requirement",
        "tests_required",
        "completion_sentinel",
        "completion_sentinel_catalog",
    }
)

# Capture candidates; validated by looks_like_path. Separators are / after
# backslash-normalization in extract_path_tokens.
_TOKEN = re.compile(
    r"(?:"
    r"[A-Za-z]:/[^\s\"'`<>|*?]{3,}"
    r"|/(?:opt|home|Users|tmp|var|etc|root|usr)/[^\s\"'`<>|*?]{3,}"
    r"|(?:command-center|tools|platform|ci|tests|docs|rules|harness|workflows)/"
    r"[^\s\"'`<>|*?]{3,}"
    r"|[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+\.[A-Za-z][A-Za-z0-9]{0,11}"
    r")"
)


@dataclass
class PathFinding:
    token: str
    normalized: str
    exists: bool
    role: str  # USE | MENTION
    flagged: bool


@dataclass
class LintResult:
    status: str
    findings: list[PathFinding] = field(default_factory=list)
    use_paths: list[str] = field(default_factory=list)
    mention_paths: list[str] = field(default_factory=list)
    flagged_paths: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "flagged_paths": list(self.flagged_paths),
            "use_paths": list(self.use_paths),
            "mention_paths": list(self.mention_paths),
            "n_use": len(self.use_paths),
            "n_mention": len(self.mention_paths),
            "n_flagged": len(self.flagged_paths),
            "findings": [
                {
                    "token": f.token,
                    "normalized": f.normalized,
                    "exists": f.exists,
                    "role": f.role,
                    "flagged": f.flagged,
                }
                for f in self.findings
            ],
        }


def split_fenced(text: str) -> tuple[str, str]:
    """Split text into (outside-fences, inside-fences) using ``` markers.

    Unclosed fences treat the remainder as mention (fail closed for
    illustrative-path false positives).
    """
    if not text:
        return "", ""
    # Honour both real newlines and escaped-newline sequences that appear
    # when a JSON document is scanned as raw text rather than decoded strings.
    prepared = text.replace("\\n", "\n")
    use_parts: list[str] = []
    mention_parts: list[str] = []
    in_fence = False
    buf: list[str] = []
    for line in prepared.splitlines(keepends=True):
        if line.strip().startswith("```"):
            chunk = "".join(buf)
            if in_fence:
                mention_parts.append(chunk)
            else:
                use_parts.append(chunk)
            buf = []
            in_fence = not in_fence
            continue
        buf.append(line)
    chunk = "".join(buf)
    if in_fence:
        mention_parts.append(chunk)
    else:
        use_parts.append(chunk)
    return "".join(use_parts), "".join(mention_parts)


def normalize_token(token: str) -> str:
    t = token.strip(_TRAIL)
    t = t.replace("\\", "/")
    while "//" in t and not t.startswith("http"):
        t = t.replace("//", "/")
    # JSON pointers / schema fragments are not filesystem paths.
    if "#" in t:
        t = t.split("#", 1)[0]
    t = t.rstrip(_TRAIL)
    t = re.sub(r":\d+$", "", t)
    if t.endswith(".json.") or t.endswith(".md.") or t.endswith(".py."):
        t = t[:-1]
    return t


def looks_like_path(token: str) -> bool:
    if not token or len(token) < 5:
        return False
    if _URL.match(token):
        return False
    if " " in token or "\n" in token or "\t" in token:
        return False
    if token.count("/") < 1 and "\\" not in token:
        return False
    # Version-like or logical-and/or.
    if token in {"and/or", "n/a", "N/A"}:
        return False
    if _WIN_ABS.match(token) or _POSIX_ABS.match(token):
        return True
    if any(token.startswith(root) for root in _REPO_ROOTS):
        return True
    if _REL_EXT.match(token):
        return True
    return False


def extract_path_tokens(text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    if not text:
        return found
    # Normalize Windows separators so one regex covers both estates.
    haystack = text.replace("\\", "/")
    for match in _TOKEN.finditer(haystack):
        raw = normalize_token(match.group(0))
        if not looks_like_path(raw):
            continue
        if raw not in seen:
            seen.add(raw)
            found.append(raw)
    return found


def repo_relative_candidate(root: Path, token: str) -> Path:
    """Map a cited token onto a path we can stat on this worktree."""
    t = normalize_token(token)
    marker = "/ast-integrate/"
    if t.endswith("/ast-integrate"):
        return root
    if marker in t:
        rel = t.split(marker, 1)[1]
        if not rel:
            return root
        return root / rel
    if _WIN_ABS.match(t):
        # Foreign Windows path with no estate marker: stat as-is (will miss).
        return Path(t)
    if t.startswith("/"):
        abs_p = Path(t)
        try:
            rel = abs_p.resolve().relative_to(root.resolve())
            return root / rel
        except (OSError, ValueError):
            return abs_p
    return root / t


def stat_cited_path(root: Path, token: str) -> tuple[str, bool]:
    target = repo_relative_candidate(root, token)
    try:
        exists = target.exists()
    except OSError:
        exists = False
    try:
        rel = str(target.resolve()).replace("\\", "/")
        root_s = str(root.resolve()).replace("\\", "/")
        if rel.startswith(root_s.rstrip("/") + "/"):
            return rel[len(root_s) + 1 :], exists
    except OSError:
        pass
    return normalize_token(token), exists


def _walk_string_fields(obj: Any, key: str | None = None) -> Iterable[tuple[str | None, str]]:
    if isinstance(obj, str):
        yield key, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk_string_fields(v, key=str(k))
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_string_fields(v, key=key)


def _walk_strings(obj: Any) -> Iterable[str]:
    for _key, blob in _walk_string_fields(obj):
        yield blob


def _blobs_for_payload(text: str) -> tuple[str, str]:
    """Return (use_text, mention_text) for a payload.

    JSON payloads: split fences inside each decoded string (agent receipts
    store markdown examples as escaped newlines). Strings under documentary
    keys are mention even outside fences (catalog quotes, titles). Non-JSON:
    split the raw document on line-based fences.
    """
    try:
        doc = json.loads(text)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return split_fenced(text)
    use_parts: list[str] = []
    mention_parts: list[str] = []
    for key, blob in _walk_string_fields(doc):
        u, m = split_fenced(blob)
        documentary = bool(key) and key.lower() in DOCUMENTARY_KEYS
        if documentary:
            if u:
                mention_parts.append(u)
            if m:
                mention_parts.append(m)
            continue
        if u:
            use_parts.append(u)
        if m:
            mention_parts.append(m)
    return "\n".join(use_parts), "\n".join(mention_parts)


def lint_payload(
    text: str,
    root: Path,
    *,
    strip_fences: bool = True,
) -> LintResult:
    if strip_fences:
        use_text, mention_text = _blobs_for_payload(text)
    else:
        use_text, mention_text = text, ""
    use_paths = extract_path_tokens(use_text)
    mention_paths = extract_path_tokens(mention_text)
    mention_set = set(mention_paths)
    findings: list[PathFinding] = []
    flagged: list[str] = []
    for token in use_paths:
        norm, exists = stat_cited_path(root, token)
        is_flag = not exists
        findings.append(
            PathFinding(
                token=token,
                normalized=norm,
                exists=exists,
                role="USE",
                flagged=is_flag,
            )
        )
        if is_flag:
            flagged.append(token)
    for token in mention_paths:
        # Mention-only tokens are recorded but never flagged.
        if token in set(use_paths):
            continue
        norm, exists = stat_cited_path(root, token)
        findings.append(
            PathFinding(
                token=token,
                normalized=norm,
                exists=exists,
                role="MENTION",
                flagged=False,
            )
        )
    status = UNVERIFIED if flagged else VERIFIED
    return LintResult(
        status=status,
        findings=findings,
        use_paths=use_paths,
        mention_paths=mention_paths,
        flagged_paths=flagged,
    )


def lint_file(path: Path, root: Path, *, strip_fences: bool = True) -> LintResult:
    text = path.read_text(encoding="utf-8", errors="replace")
    return lint_payload(text, root, strip_fences=strip_fences)
