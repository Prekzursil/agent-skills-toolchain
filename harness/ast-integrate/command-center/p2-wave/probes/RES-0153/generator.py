#!/usr/bin/env python3
"""Rule-based settling-experiment generator. Structure only; no LLM framing."""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
NEEDS = "NEEDS-HUMAN-FRAMING"
GENERATED = "GENERATED"

PATH_RE = re.compile(
    r"(?:~/|\./)?"
    r"(?:command-center|tools|rules|scripts|probes|\.claude)/"
    r"[A-Za-z0-9_./-]+"
    r"(?:\.[A-Za-z0-9]+)?"
)
BARE_FILE_RE = re.compile(
    r"\b("
    r"UNIFIED-BACKLOG\.md|settings\.json|_USER-PROMPTS\.md|"
    r"WORK-UNIT-CATALOG\.json|_dispatch/manifest\.json|"
    r"OWNER-DECISIONS\.md"
    r")\b"
)
FILE_LINE_RE = re.compile(r"([\w./-]+\.(?:py|json|md)):(\d+)(?:-(\d+))?")
URL_RE = re.compile(r"https?://[^\s\"']+")
SHA_RE = re.compile(r"\b[a-f0-9]{64}\b", re.I)
ABSENT_RE = re.compile(
    r"\b("
    r"absent|missing|not on this (?:worktree|tree|disk|linux worktree)|"
    r"not present|does not exist|not on disk|not in this worktree|"
    r"not importable|is not delivered|are not on this worktree|"
    r"was not observed|not itself observed|I did not open|"
    r"not measured|unmeasured|not on this linux"
    r")\b",
    re.I,
)


def _first(regex: re.Pattern[str], text: str) -> str | None:
    m = regex.search(text)
    return m.group(0) if m else None


def _paths(text: str) -> list[str]:
    found: list[str] = []
    for rx in (PATH_RE, BARE_FILE_RE):
        for m in rx.finditer(text):
            token = m.group(0).rstrip(").,;:\"'")
            if token not in found:
                found.append(token)
    return found


def _polarity_absent(text: str) -> bool:
    return bool(ABSENT_RE.search(text))


def generate(claim: str) -> dict:
    """Return a mechanical experiment or NEEDS-HUMAN-FRAMING from claim text."""
    text = (claim or "").strip()
    file_line = FILE_LINE_RE.search(text)
    paths = _paths(text)
    url = _first(URL_RE, text)
    digest = _first(SHA_RE, text)

    if file_line:
        rel, line = file_line.group(1), int(file_line.group(2))
        expect = "absent" if _polarity_absent(text) else "has-line"
        cmd = (
            "python3 -c "
            + json.dumps(
                "from pathlib import Path; p=Path(%r); "
                "print('absent' if not p.is_file() else "
                "('has-line' if len(p.read_text(encoding='utf-8', errors='replace').splitlines())>=%d else 'short'))"
                % (rel, line)
            )
        )
        return {
            "status": GENERATED,
            "kind": "file-line",
            "path": rel,
            "line": line,
            "expect": expect,
            "command": cmd,
            "expected_observation": expect,
            "discriminating_outcome": "absent" if expect == "has-line" else "has-line",
            "runnable_locally": True,
            "reason": "file:line anchor named in claim",
        }

    if paths:
        rel = paths[0]
        expect = "absent" if _polarity_absent(text) else "exists"
        cmd = (
            "python3 -c "
            + json.dumps(
                "from pathlib import Path; p=Path(%r).expanduser(); "
                "print('exists' if p.is_file() else 'absent')" % rel
            )
        )
        return {
            "status": GENERATED,
            "kind": "path-exists",
            "path": rel,
            "expect": expect,
            "command": cmd,
            "expected_observation": expect,
            "discriminating_outcome": "exists" if expect == "absent" else "absent",
            "runnable_locally": True,
            "reason": "filesystem path named in claim",
        }

    if digest:
        cmd = (
            "python3 -c "
            + json.dumps(
                "import hashlib,sys; print('digest-format-ok' if "
                "len(%r)==64 else 'bad')" % digest.lower()
            )
        )
        return {
            "status": GENERATED,
            "kind": "sha256-format",
            "path": None,
            "expect": "digest-format-ok",
            "command": cmd,
            "expected_observation": "digest-format-ok",
            "discriminating_outcome": "bad",
            "runnable_locally": True,
            "reason": "sha256 named in claim",
        }

    if url:
        cmd = (
            "python3 -c "
            + json.dumps(
                "from urllib.parse import urlparse; u=urlparse(%r); "
                "print('url-ok' if u.scheme in ('http','https') and u.netloc else 'url-bad')"
                % url
            )
        )
        return {
            "status": GENERATED,
            "kind": "url-shape",
            "path": url,
            "expect": "url-ok",
            "command": cmd,
            "expected_observation": "url-ok",
            "discriminating_outcome": "url-bad",
            "runnable_locally": False,
            "reason": "URL named; live fetch is GENERATED-UNRUN (no network in this unit)",
        }

    return {
        "status": NEEDS,
        "kind": None,
        "path": None,
        "expect": None,
        "command": None,
        "expected_observation": None,
        "discriminating_outcome": None,
        "runnable_locally": False,
        "reason": "claim names no path, URL, file:line, hash, or command observable",
    }


def generate_naive(claim: str) -> dict:
    """Always-emit mutant: fabricates a plausible experiment for any claim."""
    _ = claim
    return {
        "status": GENERATED,
        "kind": "naive-echo",
        "path": None,
        "expect": "plausible-ok",
        "command": "echo plausible-ok",
        "expected_observation": "plausible-ok",
        "discriminating_outcome": "not-ok",
        "runnable_locally": True,
        "reason": "naive-always-emit",
    }


def load_unobservable_plants() -> list[dict]:
    doc = json.loads(
        (HERE / "fixtures" / "unobservable.json").read_text(encoding="utf-8")
    )
    return list(doc["plants"])
