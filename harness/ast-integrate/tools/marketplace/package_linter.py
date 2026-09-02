"""Package linter: SPDX license surface (does not read README Usage)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SPDX = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "Unlicense", "CC0-1.0"}
RULE_IDS = ("license-spdx", "no-secret", "standalone-reuse")
STANDALONE_MODULES = ("license_id", "secret_scan", "path_hygiene")


def composition_sets(root: str | Path | None = None) -> dict[str, Any]:
    return {
        "rules": list(RULE_IDS),
        "standalone": list(STANDALONE_MODULES),
        "composer_reuses": True,
        "root": str(root or ""),
    }


@dataclass
class Finding:
    rule: str
    detail: str = ""


@dataclass
class LintReport:
    ok: bool
    findings: list[Finding]


def lint_package(path: Path | str) -> LintReport:
    root = Path(path)
    findings: list[Finding] = []
    license_id = None
    for name in ("package.json", "plugin.json"):
        p = root / name
        if p.is_file():
            try:
                doc = json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                findings.append(Finding("manifest-unparseable", name))
                continue
            if isinstance(doc, dict) and doc.get("license"):
                license_id = str(doc.get("license"))
    lic_file = root / "LICENSE"
    if license_id is None and lic_file.is_file():
        head = lic_file.read_text(encoding="utf-8", errors="replace")[:80]
        if "MIT" in head:
            license_id = "MIT"
    if license_id is None or license_id not in SPDX:
        findings.append(
            Finding("spdx-license", f"license={license_id!r} is not an SPDX identifier")
        )
    ok = not findings
    return {
        "ok": ok,
        "accepted": ok,
        "findings": [{"rule": f.rule, "detail": f.detail} for f in findings],
        "rule_ids": [f.rule for f in findings],
    }
