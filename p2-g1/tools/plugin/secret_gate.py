"""Two-signal secret gate: gitleaks-toml rules + Shannon entropy. Never emit the body."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PREFIX = "ghp_"


def _lazy_canary():
    try:
        from plugin.canary import PREFIX as p, leak_in, synthetic_body
        return p, leak_in, synthetic_body
    except Exception:
        from canary import PREFIX as p, leak_in, synthetic_body
        return p, leak_in, synthetic_body


def _shape(s: str) -> str:
    # Schema-friendly descriptor; must not contain the secret body.
    import math

    if not s:
        return "len=0 entropy=0.0bits"
    counts: dict[str, int] = {}
    for ch in s:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(s)
    ent = -sum((c / n) * math.log2(c / n) for c in counts.values())
    return f"len={n} entropy={ent:.1f}bits"


def build_report(root: Path) -> dict[str, Any]:
    root = Path(root)
    try:
        from plugin.entropy_scan import scan_tree as entropy_scan_tree
        from plugin.gitleaks_engine import scan_tree as gitleaks_scan_tree
        from plugin.redact import redact_obj
    except Exception:
        from entropy_scan import scan_tree as entropy_scan_tree
        from gitleaks_engine import scan_tree as gitleaks_scan_tree
        from redact import redact_obj
    pfx, leak_in, synthetic_body = _lazy_canary()
    gl = gitleaks_scan_tree(root)
    ent = entropy_scan_tree(root)
    findings = []
    for f in gl + ent:
        row = dict(f)
        row["prefix"] = pfx
        row.pop("token", None)
        row.pop("secret", None)
        row.pop("body", None)
        findings.append(row)
    blocked = bool(findings)
    report = {
        "blocked": blocked,
        "exit_code": 1 if blocked else 0,
        "findings": findings,
        "detectors": {
            "gitleaks_rules": {
                "exit_code": 1 if gl else 0,
                "findings_count": len(gl),
            },
            "shannon_entropy": {
                "findings_count": len(ent),
                "exit_code": 1 if ent else 0,
            },
        },
    }
    dumped = json.dumps(report)
    if leak_in(dumped) or synthetic_body() in dumped:
        report = redact_obj(report)
    return report


def write_report(report: dict[str, Any], path: Path) -> None:
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    text = redact_text(text)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


_ASSIGN = __import__("re").compile(
    r"(?i)\b([A-Z][A-Z0-9_]*(?:TOKEN|KEY|SECRET|PASSWORD|PAT))\s*[=:]\s*(\S+)"
)


def scan_file(path: Path, rel: str | None = None) -> list[dict[str, Any]]:
    path = Path(path)
    rel = (rel or path.name).replace("\\", "/")
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    findings: list[dict[str, Any]] = []
    for m in _ASSIGN.finditer(text):
        findings.append(
            {
                "detector": "assignment-gate",
                "path": rel,
                "variable_name": m.group(1),
                "rule": "named-secret-assignment",
                "shape": _shape(m.group(2).strip().strip("\"'")),
            }
        )
    if not findings and path.suffix.lower() == ".env" and "=" in text:
        findings.append(
            {
                "detector": "assignment-gate",
                "path": rel,
                "variable_name": "ENV",
                "rule": "dotenv-assignment",
                "shape": _shape(text.strip()[:64]),
            }
        )
    return findings


def scan_tree(root: Path) -> list[dict[str, Any]]:
    root = Path(root)
    out: list[dict[str, Any]] = []
    if not root.exists():
        return out
    for p in root.rglob("*"):
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            out.extend(scan_file(p, rel=rel))
    return out


def findings_leak_body(findings: list[dict[str, Any]], body: str) -> bool:
    blob = json.dumps(findings)
    return body in blob


def report_dict(findings: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "blocked": bool(findings),
        "findings_count": len(findings),
        "findings": findings,
    }

