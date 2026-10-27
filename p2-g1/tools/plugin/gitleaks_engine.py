"""gitleaks-toml rule engine (stdlib re, no gitleaks binary)."""
from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Any

from canary import PREFIX
from scan_fs import iter_text_files

HERE = Path(__file__).resolve().parent
TOML = HERE / "gitleaks.toml"
PAT_ASSIGN = re.compile(
    r"(?i)\b([A-Z][A-Z0-9_]*(?:TOKEN|KEY|SECRET|PASSWORD|PAT))\s*[=:]\s*[\"']?(ghp_[0-9A-Za-z]+)"
)
PAT_TOKEN = re.compile(r"\bghp_[0-9A-Za-z]{20,}\b")
PAT_SPLIT = re.compile(r'["\']ghp_["\']\s*\+\s*["\']([0-9A-Za-z]+)["\']')


def _b64_decode_candidates(text: str) -> list[str]:
    out: list[str] = []
    for m in re.finditer(r"[A-Za-z0-9+/]{20,}={0,2}", text):
        blob = m.group(0)
        if len(blob) % 4:
            blob += "=" * (4 - len(blob) % 4)
        try:
            decoded = base64.b64decode(blob, validate=False).decode("utf-8", "replace")
        except Exception:
            continue
        if "ghp_" in decoded or decoded.startswith(PREFIX):
            out.append(decoded)
    return out


def scan_text(rel: str, text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    blobs = [text, *(_b64_decode_candidates(text))]
    reconstructed = list(PAT_SPLIT.finditer(text))
    for m in reconstructed:
        blobs.append(PREFIX + m.group(1))

    for blob in blobs:
        for m in PAT_ASSIGN.finditer(blob):
            token = m.group(2)
            findings.append(
                {
                    "detector": "gitleaks-rules",
                    "prefix": PREFIX,
                    "path": rel.replace("\\", "/"),
                    "variable_name": m.group(1),
                    "rule": "github-pat-assignment",
                    "line": 1,
                }
            )
            del token
        if not any(f["path"] == rel.replace("\\", "/") and f["detector"] == "gitleaks-rules" for f in findings):
            if PAT_TOKEN.search(blob):
                findings.append(
                    {
                        "detector": "gitleaks-rules",
                        "prefix": PREFIX,
                        "path": rel.replace("\\", "/"),
                        "variable_name": "GITHUB_TOKEN",
                        "rule": "github-pat",
                        "line": 1,
                    }
                )
    # split-literal reconstruction
    for m in reconstructed:
        findings.append(
            {
                "detector": "gitleaks-rules",
                "prefix": PREFIX,
                "path": rel.replace("\\", "/"),
                "variable_name": "GITHUB_TOKEN",
                "rule": "github-pat-split-literal",
                "line": 1,
            }
        )
    # unique by path+rule+detector
    seen: set[tuple[str, str, str]] = set()
    uniq: list[dict[str, Any]] = []
    for f in findings:
        key = (f["path"], f["detector"], f["rule"])
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
