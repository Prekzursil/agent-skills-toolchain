"""Independent gitleaks-style scanner for IMP-0317.

Mechanically different from tools/council/artifacts/retention.py:
  * line-oriented regex rules (gitleaks allowlist shape), not a JSON walk
  * Shannon entropy gate on assignment values and base64 blobs
  * does not import the redactor's Finding/key tables

Reports (path, line, rule_id) with values stripped. Never prints a secret.
"""
from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

# Rule table is local to this file. Do not share with retention.py.
_RULES: list[tuple[str, re.Pattern[str]]] = [
    (
        "env-assignment",
        re.compile(
            r"(?i)(?:export\s+)?[A-Z][A-Z0-9_]{0,80}(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|AUTH)[A-Z0-9_]{0,40}\s*[=:]\s*\S{12,}"
        ),
    ),
    (
        "json-password",
        re.compile(
            r'(?i)(?:\\*)["\']password(?:\\*)["\']\s*:\s*(?:\\*)["\'][^"\'\\]{12,}(?:\\*)["\']'
        ),
    ),
    (
        "camelcase-apikey",
        re.compile(
            r"""apiKey\s*["']?\s*[:=]\s*["']?[^"'\s\\]{12,}"""
        ),
    ),
    (
        "base64-assignment",
        re.compile(
            r"(?i)(?:credential|secret|password|token|key)\w*\s*[=:]\s*[A-Za-z0-9+/]{24,}={0,2}"
        ),
    ),
]

_PLACEHOLDER = "[REDACTED:"


def _entropy(s: str) -> float:
    if not s:
        return 0.0
    freq: dict[str, int] = {}
    for ch in s:
        freq[ch] = freq.get(ch, 0) + 1
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in freq.values())


def scan_text(text: str, *, path: str = "-") -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if _PLACEHOLDER in line and "SYNTHETIC-NOT-A-LIVE-SECRET" not in line:
            # Redacted lines still matching a key name are not survivors.
            if "SYNTHETIC-NOT-A-LIVE-SECRET" not in line and "imp0317-" not in line.lower():
                # Keep scanning: a redacted line may still carry a *different* leak.
                pass
        for rule_id, pat in _RULES:
            if not pat.search(line):
                continue
            # Entropy gate: skip low-entropy (e.g. token_count=000000000000)
            # Extract a candidate value after = or :
            val_m = re.search(r"[=:]\s*(\\?[\"'])?([^\"'\\]{8,})", line)
            val = val_m.group(2) if val_m else line
            if val.startswith("REDACTED:") or val.startswith("[REDACTED:"):
                continue
            if _PLACEHOLDER in line and "SYNTHETIC-NOT-A-LIVE-SECRET" not in line and "imp0317-" not in line:
                continue
            if _entropy(val) < 2.5 and "SYNTHETIC" not in line:
                continue
            hits.append(
                {
                    "path": path,
                    "line": lineno,
                    "rule_id": rule_id,
                    "entropy": round(_entropy(val), 3),
                }
            )
    return hits


def scan_dir(directory: Path) -> list[dict[str, Any]]:
    directory = Path(directory)
    hits: list[dict[str, Any]] = []
    if not directory.exists():
        return hits
    paths: list[Path]
    if directory.is_file():
        paths = [directory]
    else:
        paths = [p for p in sorted(directory.rglob("*")) if p.is_file()]
    for path in paths:
        if path.suffix not in {".json", ".txt", ".md", ".jsonl", ""}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = path.as_posix()
        hits.extend(scan_text(text, path=rel))
    return hits
