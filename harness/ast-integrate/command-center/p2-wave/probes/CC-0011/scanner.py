#!/usr/bin/env python3
"""Read-only credential-shape scanner for CC-0011.

Two engines:
  * pattern: known prefixes/formats that require a secret *body*
  * entropy-name: secret-like assignments whose value is high-entropy

Hits never carry the secret body. Only a zero-entropy prefix, byte length,
variable name, path, line, and optional commit SHA are retained.
"""
from __future__ import annotations

import base64
import json
import math
import os
import re
import stat
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable, Iterator

# Zero-entropy prefixes (documented; a prefix alone must not fire).
PREFIX_ANTHROPIC = "sk-ant-"
PREFIX_OPENAI_PROJ = "sk-proj-"
PREFIX_OPENAI = "sk-"
PREFIX_GITHUB = "ghp_"
PREFIX_GITHUB_PAT = "github_pat_"
PREFIX_AWS = "AKIA"
PREFIX_PEM = "-----BEGIN "

# Pattern engine: lookbehind so "task-" / "risky-" do not count as "sk-".
# Longer prefixes are listed first so overlapping matches collapse.
_PATTERN_RULES: list[tuple[str, str, str, re.Pattern[str]]] = []


def _rule(name: str, prefix: str, body: str) -> None:
    pat = re.compile(rf"(?<![A-Za-z0-9])({re.escape(prefix)})({body})")
    _PATTERN_RULES.append((name, prefix, body, pat))


_rule("anthropic-api-key", PREFIX_ANTHROPIC, r"[A-Za-z0-9_-]{20,}")
_rule("openai-proj-key", PREFIX_OPENAI_PROJ, r"[A-Za-z0-9_-]{20,}")
_rule("openai-legacy-key", PREFIX_OPENAI, r"[A-Za-z0-9]{32,}")
_rule("github-pat", PREFIX_GITHUB, r"[A-Za-z0-9]{36}")
_rule("github-fine-grained", PREFIX_GITHUB_PAT, r"[A-Za-z0-9_]{22,}")
_rule("github-oauth", "gho_", r"[A-Za-z0-9]{36}")
_rule("aws-access-key-id", PREFIX_AWS, r"[0-9A-Z]{16}")
_rule("slack-bot-token", "xoxb-", r"[A-Za-z0-9-]{20,}")
_rule("slack-user-token", "xoxp-", r"[A-Za-z0-9-]{20,}")
_rule("google-api-key", "AIza", r"[0-9A-Za-z_-]{35}")

_PEM_RE = re.compile(
    r"-----BEGIN ([A-Z0-9 ]{0,40}PRIVATE KEY)-----"
)
_JWT_RE = re.compile(
    r"(?<![A-Za-z0-9])(eyJ[A-Za-z0-9_-]{8,})\.([A-Za-z0-9_-]{8,})\.([A-Za-z0-9_-]{8,})"
)

_ASSIGN_RE = re.compile(
    r"(?i)(?:^|[\s,{])"
    r"([A-Za-z_][A-Za-z0-9_]{0,80}?(?:api[_-]?key|secret|token|password|passwd|"
    r"credential|private[_-]?key|authorization|auth_token|access_key))"
    r"\s*[:=]\s*[\"']?([A-Za-z0-9/+=_\-.]{24,})"
)

_HEX_DIGEST = re.compile(r"^(?:[0-9a-fA-F]{32}|[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")
# Split so this source file does not itself contain a complete well-known example token.
_WELL_KNOWN_PLACEHOLDERS = {
    "AKIA" + "IOSFODNN7EXAMPLE",
    "wJalrXUtnFEMI/K7MDENG/bPxRfiCY" + "EXAMPLEKEY",
}
_FIXTURE_MARKERS = (
    "fixture",
    "notareal",
    "not-a-real",
    "examplekey",
    "example",
    "changeme",
    "your_token",
    "placeholder",
    "cc0011",
    "canary",
    "synthetic",
    "planted",
    "decoy",
    "fake0000",
    "not_a_server",
    "tst0209",
)

# Third-party downloaded pages and runtime-assembled shape builders are
# research fixtures, not live program secrets. Path match is posix.
_SYNTHETIC_PATH_MARKERS = (
    "/fixtures/",
    "/_work/fixtures/",
    "/captures/",
    "/snapshots/",
)
_SYNTHETIC_BASENAMES = {
    "secret_shapes.py",
}

SKIP_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".so",
    ".o",
    ".a",
    ".bin",
    ".exe",
    ".dll",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".woff",
    ".woff2",
    ".zip",
    ".gz",
    ".tgz",
    ".tar",
    ".xz",
    ".7z",
    ".pdf",
}
SKIP_DIR_NAMES = {"__pycache__", ".git", "node_modules"}
ENTROPY_BYTE_LIMIT = 2_000_000
FILE_BYTE_LIMIT = 40_000_000

# Output of this unit — scanning it would score the receipt or planted fixtures.
SELF_SKIP = {
    "command-center/receipts/CC-0011.json",
    "command-center/p2-wave/probes/CC-0011/SUBAGENT-RETURN.json",
    "command-center/p2-wave/probes/CC-0011/UNIT-ARTIFACT-MANIFEST.json",
}


@dataclass(frozen=True)
class Hit:
    path: str
    line: int
    prefix: str
    byte_length: int
    rule: str
    engine: str
    scope: str
    variable_name: str | None = None
    commit: str | None = None
    whoami_authenticates: bool | None = None
    whoami_status: str | None = None
    classification: str = "credential-shaped"

    def as_public(self) -> dict:
        return asdict(self)


def shannon(s: str) -> float:
    n = len(s)
    if n == 0:
        return 0.0
    counts = Counter(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def _jwt_header_ok(first_seg: str) -> bool:
    try:
        pad = "=" * ((4 - len(first_seg) % 4) % 4)
        header = json.loads(base64.urlsafe_b64decode(first_seg + pad))
    except (ValueError, json.JSONDecodeError, OSError):
        return False
    return isinstance(header, dict) and "alg" in header


def classify_match(full: str, path: str) -> str:
    lower = full.lower()
    posix = path.replace("\\", "/")
    if full in _WELL_KNOWN_PLACEHOLDERS or any(m in lower for m in _FIXTURE_MARKERS):
        return "placeholder" if "example" in lower or full in _WELL_KNOWN_PLACEHOLDERS else "synthetic"
    if any(m in posix for m in _SYNTHETIC_PATH_MARKERS) or posix.endswith("/fixtures"):
        return "synthetic"
    if "CC-0011" in posix:
        return "synthetic"
    base = posix.rsplit("/", 1)[-1]
    if base in _SYNTHETIC_BASENAMES:
        return "synthetic"
    body = full
    for p in (
        PREFIX_ANTHROPIC,
        PREFIX_OPENAI_PROJ,
        PREFIX_GITHUB_PAT,
        PREFIX_GITHUB,
        PREFIX_AWS,
        PREFIX_OPENAI,
    ):
        if full.startswith(p):
            body = full[len(p) :]
            break
    if body and len(set(body)) <= 2:
        return "placeholder"
    return "credential-shaped"


def _line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def scan_text(
    text: str,
    path: str,
    *,
    scope: str,
    engines: tuple[str, ...] = ("pattern", "entropy-name"),
    commit: str | None = None,
) -> list[Hit]:
    hits: list[Hit] = []
    occupied: list[tuple[int, int]] = []

    def overlaps(start: int, end: int) -> bool:
        return any(not (end <= a or start >= b) for a, b in occupied)

    if "pattern" in engines:
        for name, prefix, _body, pat in _PATTERN_RULES:
            for m in pat.finditer(text):
                start, end = m.start(), m.end()
                if overlaps(start, end):
                    continue
                full = m.group(0)
                # openai-legacy `sk-` also matches `sk-ant-` / `sk-proj-` prefixes;
                # those are claimed by the longer rules.
                if name == "openai-legacy-key" and (
                    full.startswith("sk-ant-") or full.startswith("sk-proj-")
                ):
                    continue
                occupied.append((start, end))
                hits.append(
                    Hit(
                        path=path,
                        line=_line_of(text, start),
                        prefix=prefix,
                        byte_length=len(full.encode("utf-8", errors="replace")),
                        rule=name,
                        engine="pattern",
                        scope=scope,
                        commit=commit,
                        classification=classify_match(full, path),
                    )
                )
        for m in _PEM_RE.finditer(text):
            start = m.start()
            end = text.find("-----END", start)
            if end < 0:
                end = m.end()
            else:
                end = text.find("-----", end + 8)
                end = (end + 5) if end >= 0 else m.end()
            if overlaps(start, end):
                continue
            occupied.append((start, end))
            block = text[start:end]
            kind = m.group(1).strip()
            hits.append(
                Hit(
                    path=path,
                    line=_line_of(text, start),
                    prefix=f"-----BEGIN {kind}-----",
                    byte_length=len(block.encode("utf-8", errors="replace")),
                    rule="pem-private-key",
                    engine="pattern",
                    scope=scope,
                    commit=commit,
                    classification=classify_match(block[:80], path),
                )
            )
        for m in _JWT_RE.finditer(text):
            if not _jwt_header_ok(m.group(1)):
                continue
            start, end = m.start(), m.end()
            if overlaps(start, end):
                continue
            occupied.append((start, end))
            full = m.group(0)
            hits.append(
                Hit(
                    path=path,
                    line=_line_of(text, start),
                    prefix="eyJ",
                    byte_length=len(full.encode("utf-8", errors="replace")),
                    rule="jwt",
                    engine="pattern",
                    scope=scope,
                    commit=commit,
                    classification=classify_match(full, path),
                )
            )

    if "entropy-name" in engines:
        for m in _ASSIGN_RE.finditer(text):
            name, value = m.group(1), m.group(2).rstrip("\"',}")
            if _HEX_DIGEST.match(value):
                continue
            if shannon(value) < 3.5:
                continue
            start, end = m.start(2), m.start(2) + len(value)
            if overlaps(start, end):
                continue
            # Bare documented prefixes have low body entropy and fail the length
            # floor after stripping the prefix; still refuse prefix-only values.
            if value in {
                PREFIX_ANTHROPIC,
                PREFIX_OPENAI_PROJ,
                PREFIX_OPENAI,
                PREFIX_GITHUB,
                PREFIX_AWS,
            }:
                continue
            occupied.append((start, end))
            prefix = _zero_entropy_prefix(value)
            hits.append(
                Hit(
                    path=path,
                    line=_line_of(text, start),
                    prefix=prefix,
                    byte_length=len(value.encode("utf-8", errors="replace")),
                    rule="high-entropy-assignment",
                    engine="entropy-name",
                    scope=scope,
                    variable_name=name,
                    commit=commit,
                    classification=classify_match(value, path),
                )
            )
    return hits


def _zero_entropy_prefix(value: str) -> str:
    for p in (
        PREFIX_ANTHROPIC,
        PREFIX_OPENAI_PROJ,
        PREFIX_GITHUB_PAT,
        PREFIX_GITHUB,
        "gho_",
        PREFIX_AWS,
        "xoxb-",
        "xoxp-",
        "AIza",
        PREFIX_PEM,
        PREFIX_OPENAI,
        "eyJ",
    ):
        if value.startswith(p):
            return p
    return value[:4] if len(value) >= 4 else value


def is_binary(sample: bytes) -> bool:
    return b"\x00" in sample


def iter_files(root: Path) -> Iterator[Path]:
    if root.is_file():
        yield root
        return
    if not root.is_dir():
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES and not d.startswith(".git")]
        for name in filenames:
            yield Path(dirpath) / name


def rel_to(repo: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        return str(path)


def scan_path(
    path: Path,
    *,
    repo: Path,
    scope: str,
    engines: tuple[str, ...] = ("pattern", "entropy-name"),
    skip: Callable[[str], bool] | None = None,
) -> list[Hit]:
    if not path.exists():
        return []
    hits: list[Hit] = []
    for fp in iter_files(path):
        rel = rel_to(repo, fp) if fp.is_relative_to(repo) else str(fp)
        if rel in SELF_SKIP:
            continue
        if skip and skip(rel):
            continue
        suffix = fp.suffix.lower()
        if suffix in SKIP_SUFFIXES:
            continue
        try:
            st = fp.stat()
        except OSError:
            continue
        if not stat.S_ISREG(st.st_mode) or st.st_size <= 0:
            continue
        if st.st_size > FILE_BYTE_LIMIT:
            continue
        try:
            raw = fp.read_bytes()
        except OSError:
            continue
        if is_binary(raw[:8192]):
            continue
        text = raw.decode("utf-8", errors="replace")
        use_engines = engines
        if st.st_size > ENTROPY_BYTE_LIMIT:
            use_engines = tuple(e for e in engines if e != "entropy-name") or ("pattern",)
        hits.extend(
            scan_text(text, rel, scope=scope, engines=use_engines)
        )
    return hits


def scan_git_history(
    git_repo: Path,
    *,
    pathspec: str | None = None,
    label_path: str = "(git-history)",
    scope: str = "git-history",
) -> list[Hit]:
    """Scan `git log -p` so a deleted leak is still visible.

    The worktree itself is not mutated. `git_repo` may be a scratch fixture.
    """
    import subprocess

    if not (git_repo / ".git").exists() and not (git_repo / ".git").is_file():
        # bare or missing
        probe = subprocess.run(
            ["git", "-C", str(git_repo), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
        )
        if probe.returncode != 0:
            return []
    cmd = [
        "git",
        "-C",
        str(git_repo),
        "log",
        "-p",
        "--all",
        "--full-history",
        "--format=commit %H",
    ]
    if pathspec:
        cmd.extend(["--", pathspec])
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        return []
    hits: list[Hit] = []
    current = None
    # Split on commit headers; scan each patch as text.
    chunks = re.split(r"(?m)^commit ([0-9a-f]{40})\n", proc.stdout)
    # re.split keeps capture groups: [preamble, sha, body, sha, body, ...]
    it = iter(chunks[1:])
    for sha, body in zip(it, it):
        current = sha
        for hit in scan_text(
            body,
            f"{label_path}@{sha[:12]}",
            scope=scope,
            engines=("pattern",),
            commit=sha,
        ):
            hits.append(hit)
    return hits


def public_hits(hits: Iterable[Hit]) -> list[dict]:
    return [h.as_public() for h in hits]
