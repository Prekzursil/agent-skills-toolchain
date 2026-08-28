#!/usr/bin/env python3
"""Bounded, value-free secret audit for live and historical text artifacts."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import pathlib
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass


TEXT_SUFFIXES = {
    ".cfg",
    ".conf",
    ".env",
    ".ini",
    ".json",
    ".jsonl",
    ".log",
    ".md",
    ".ps1",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
SKIP_PARTS = {".git", ".hf", "node_modules", "secure-evidence", "__pycache__"}
REFERENCE_RE = re.compile(
    r"^(?:\$\{[A-Z][A-Z0-9_]*\}|Bearer \$\{[A-Z][A-Z0-9_]*\}|"
    r"[A-Z][A-Z0-9_]{2,}|(?i:keyring://\S+|env:[A-Z][A-Z0-9_]*|"
    r"\[?REDACTED\]?|<redacted>))$",
)
PLACEHOLDER_RE = re.compile(
    r"(?:example|dummy|fake|fixture|placeholder|test|changeme|replace|your[-_]|generated[-_])",
    re.I,
)
SENSITIVE_KEY_RE = re.compile(
    r"(?:^|[_-])(?:api[_-]?key|access[_-]?key|authorization|bearer|credential|"
    r"password|private[_-]?key|secret|token|pat)(?:$|[_-])",
    re.I,
)
ASSIGNMENT_RE = re.compile(
    r"^[\s\"']*([A-Za-z][A-Za-z0-9_.-]*(?:token|secret|password|key|pat|authorization)[A-Za-z0-9_.-]*)"
    r"[\"']*\s*[:=]\s*[\"']([^\"'\r\n]{8,})[\"']",
    re.I | re.M,
)
STRONG_TOKEN_PATTERNS = {
    "github": re.compile(r"(?:github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,})"),
    "huggingface": re.compile(r"hf_[A-Za-z0-9]{20,}"),
    "apify": re.compile(r"apify_api_[A-Za-z0-9]{20,}"),
    "digitalocean": re.compile(r"do[op]_v1_[A-Fa-f0-9]{32,}"),
    "sentry": re.compile(r"sntry[su]_[A-Za-z0-9_-]{20,}"),
    "sonarqube": re.compile(r"squ_[A-Za-z0-9]{20,}"),
    "tavily": re.compile(r"tvly-[A-Za-z0-9_-]{20,}"),
    "firecrawl": re.compile(r"fc-[A-Za-z0-9_-]{20,}"),
    "private-key": re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----",
        re.I,
    ),
}


@dataclass(frozen=True)
class Finding:
    path: str
    sha256: str
    line: int
    detector: str
    name: str


def iter_files(roots: Iterable[pathlib.Path], max_bytes: int) -> Iterable[pathlib.Path]:
    seen: set[pathlib.Path] = set()
    for root in roots:
        if not root.exists():
            continue
        candidates = [root] if root.is_file() else root.rglob("*")
        for candidate in candidates:
            if not candidate.is_file() or candidate in seen:
                continue
            seen.add(candidate)
            if any(part in SKIP_PARTS for part in candidate.parts):
                continue
            if candidate.suffix.lower() not in TEXT_SUFFIXES:
                continue
            try:
                if candidate.stat().st_size > max_bytes:
                    continue
            except OSError:
                continue
            yield candidate


def _line(text: str, position: int) -> int:
    return text.count("\n", 0, position) + 1


def _entropy(value: str) -> float:
    counts = {character: value.count(character) for character in set(value)}
    length = len(value)
    return -sum((count / length) * math.log2(count / length) for count in counts.values())


def looks_like_credential_literal(value: str) -> bool:
    normalized = value.strip()
    if len(normalized) < 20:
        return False
    if REFERENCE_RE.fullmatch(normalized) or PLACEHOLDER_RE.search(normalized):
        return False
    if any(character.isspace() for character in normalized):
        return False
    if any(marker in normalized for marker in ("://", "\\", "/", "<", ">")):
        return False
    if re.search(r"\.(?:json|toml|md|txt|py|js|ts|safetensors)$", normalized, re.I):
        return False
    credential_characters = sum(character.isalnum() or character in "_-" for character in normalized)
    if credential_characters / len(normalized) < 0.85:
        return False
    return _entropy(normalized) >= 3.5


def scan_file(path: pathlib.Path, environment_values: dict[str, str]) -> list[Finding]:
    raw = path.read_bytes()
    if b"\x00" in raw:
        return []
    text = raw.decode("utf-8", errors="replace")
    digest = hashlib.sha256(raw).hexdigest()
    findings: list[Finding] = []

    for name, value in environment_values.items():
        if len(value) < 8:
            continue
        start = 0
        while (index := text.find(value, start)) >= 0:
            findings.append(Finding(str(path), digest, _line(text, index), "environment-value", name))
            start = index + len(value)

    for name, pattern in STRONG_TOKEN_PATTERNS.items():
        for match in pattern.finditer(text):
            value = match.group(0)
            if PLACEHOLDER_RE.search(value):
                continue
            findings.append(Finding(str(path), digest, _line(text, match.start()), "token-pattern", name))

    for match in ASSIGNMENT_RE.finditer(text):
        key, value = match.groups()
        if not SENSITIVE_KEY_RE.search(key):
            continue
        normalized = value.strip()
        if not looks_like_credential_literal(normalized):
            continue
        findings.append(Finding(str(path), digest, _line(text, match.start()), "credential-literal", key))

    unique = {(f.path, f.line, f.detector, f.name): f for f in findings}
    return list(unique.values())


def audit(roots: list[pathlib.Path], env_names: Iterable[str], max_bytes: int) -> dict:
    environment_values = {
        name: value
        for name in env_names
        if (value := os.environ.get(name)) and not REFERENCE_RE.fullmatch(value)
    }
    files = list(iter_files(roots, max_bytes))
    findings: list[Finding] = []
    skipped_errors: list[str] = []
    for path in files:
        try:
            findings.extend(scan_file(path, environment_values))
        except OSError:
            skipped_errors.append(str(path))
    return {
        "schema_version": 1,
        "files_scanned": len(files),
        "findings": [asdict(item) for item in findings],
        "errors": sorted(skipped_errors),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="+", type=pathlib.Path)
    parser.add_argument("--rotation-manifest", type=pathlib.Path)
    parser.add_argument("--report", type=pathlib.Path)
    parser.add_argument("--max-bytes", type=int, default=8 * 1024 * 1024)
    args = parser.parse_args()

    env_names: set[str] = set()
    if args.rotation_manifest and args.rotation_manifest.is_file():
        manifest = json.loads(args.rotation_manifest.read_text(encoding="utf-8"))
        for provider in manifest.get("providers", []):
            env_names.update(provider.get("environmentVariables", []))

    result = audit(args.roots, sorted(env_names), args.max_bytes)
    rendered = json.dumps(result, indent=2, ensure_ascii=True) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.report.with_suffix(args.report.suffix + ".tmp")
        temporary.write_text(rendered, encoding="utf-8")
        os.replace(temporary, args.report)
    print(
        "SUCCESS:secret-audit "
        f"files={result['files_scanned']} findings={len(result['findings'])} "
        f"errors={len(result['errors'])}"
    )
    return 2 if result["findings"] or result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
