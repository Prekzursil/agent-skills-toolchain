"""Shannon-entropy literal scanner, independent of gitleaks-toml rules."""
from __future__ import annotations

import base64
import math
import re
from pathlib import Path
from typing import Any

from canary import PREFIX
from scan_fs import iter_text_files

PAT_TOKEN = re.compile(r"\bghp_([0-9A-Za-z]{16,})\b")
PAT_SPLIT = re.compile(r'["\']ghp_["\']\s*\+\s*["\']([0-9A-Za-z]+)["\']')
PAT_B64 = re.compile(r"[A-Za-z0-9+/]{24,}={0,2}")
PAT_ASSIGN = re.compile(
    r"(?i)\b([A-Z][A-Z0-9_]*(?:TOKEN|KEY|SECRET|PASSWORD|PAT))\s*[=:]\s*[\"']?(ghp_[0-9A-Za-z]+)"
)


def shannon(s: str) -> float:
    if not s:
        return 0.0
    counts: dict[str, int] = {}
    for ch in s:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def _b64_decoded(text: str) -> list[str]:
    out: list[str] = []
    for m in PAT_B64.finditer(text):
        blob = m.group(0)
        pad = "=" * ((4 - len(blob) % 4) % 4)
        try:
            decoded = base64.b64decode(blob + pad, validate=False).decode("utf-8", "replace")
        except Exception:
            continue
        out.append(decoded)
    return out


def scan_text(rel: str, text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    blobs = [text, *_b64_decoded(text)]
    for m in PAT_SPLIT.finditer(text):
        blobs.append(PREFIX + m.group(1))
    path = rel.replace("\\", "/")
    for blob in blobs:
        for m in PAT_ASSIGN.finditer(blob):
            body = m.group(2)[len(PREFIX) :]
            if shannon(body) >= 3.0:
                findings.append(
                    {
                        "detector": "shannon-entropy",
                        "prefix": PREFIX,
                        "path": path,
                        "variable_name": m.group(1),
                        "rule": "high-entropy-github-pat",
                        "line": 1,
                    }
                )
        for m in PAT_TOKEN.finditer(blob):
            body = m.group(1)
            if shannon(body) >= 3.0:
                findings.append(
                    {
                        "detector": "shannon-entropy",
                        "prefix": PREFIX,
                        "path": path,
                        "variable_name": "GITHUB_TOKEN",
                        "rule": "high-entropy-github-pat",
                        "line": 1,
                    }
                )
        if PAT_SPLIT.search(text):
            findings.append(
                {
                    "detector": "shannon-entropy",
                    "prefix": PREFIX,
                    "path": path,
                    "variable_name": "GITHUB_TOKEN",
                    "rule": "high-entropy-split-literal",
                    "line": 1,
                }
            )
    seen: set[tuple[str, str]] = set()
    uniq: list[dict[str, Any]] = []
    for f in findings:
        key = (f["path"], f["detector"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(f)
    return uniq


def scan_tree(root: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for rel, text in iter_text_files(root):
        findings.extend(scan_text(rel, text))
    return findings
