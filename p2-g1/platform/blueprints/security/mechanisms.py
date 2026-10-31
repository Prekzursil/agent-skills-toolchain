"""Secret-exposure mechanism: report prefixes, never values, never rotate."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

PREFIX_RE = re.compile(r"(PLANTEDFAKE_|sk-|ghp_|hf_)")
LAST_REPORT: dict[str, Any] = {}


def secret_exposure(root: Path) -> dict[str, Any]:
    findings = []
    for path in Path(root).rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in PREFIX_RE.finditer(text):
            prefix = m.group(1)
            findings.append(
                {
                    "path": str(path),
                    "prefix": prefix,
                    "rotation": {
                        "recommendation": "Owner must rotate the credential out of band. RECOMMENDATION"
                    },
                }
            )
    report = {
        "finding_count": len(findings),
        "findings": findings,
        "rotates": False,
        "owner_recommendation": "RECOMMENDATION: owner rotates; this tool does not.",
    }
    LAST_REPORT.clear()
    LAST_REPORT.update(report)
    return report


def emit_report(report: dict[str, Any], known_secrets: list[str] | None = None) -> dict[str, Any]:
    secrets = list(known_secrets or [])
    blob = json.dumps(report, sort_keys=True)
    for secret in secrets:
        if secret in blob:
            # Redact values if a caller stuffed them in.
            report = json.loads(blob.replace(secret, "[REDACTED]"))
    return report
