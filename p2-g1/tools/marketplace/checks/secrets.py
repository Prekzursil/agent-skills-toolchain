"""Rule secret-gate: no live credential material in the package.

Findings quote only a 4-character prefix of the matched material and
withhold the synthetic body.
"""
from __future__ import annotations

PATTERNS = (
    "sk-",
    "hf_",
    "ghp_",
    "AKIA",
    "BEGIN PRIVATE KEY",
)


def standalone_findings(root):
    from pathlib import Path

    root = Path(root)
    findings = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.suffix in {".png", ".jpg", ".zip"}:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for pat in PATTERNS:
            idx = text.find(pat)
            if idx >= 0:
                prefix = text[idx : idx + 4]
                findings.append(
                    {
                        "rule": "secret-gate",
                        "detail": "%s: material matching %r (prefix %r, body withheld)"
                        % (p.name, pat, prefix),
                    }
                )
    return findings
