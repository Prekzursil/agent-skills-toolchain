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

    @property
    def rule_id(self) -> str:
        return self.rule

    def as_dict(self) -> dict[str, str]:
        return {"rule": self.rule, "rule_id": self.rule, "detail": self.detail}


class LintReport(dict):
    """Lint outcome: a JSON-shaped mapping with attribute accessors.

    Mapping keys (``report["ok"]``, ``report["finding_count"]``,
    ``report["findings"][0]["rule"]``) serve callers that treat the report as
    data; the properties (``report.ok``, ``report.findings[0].rule``) expose the
    same computed values as objects.
    """

    def __init__(self, ok: bool, findings: list[Finding] | None = None) -> None:
        self._findings: list[Finding] = list(findings or [])
        super().__init__(
            ok=bool(ok),
            accepted=bool(ok),
            finding_count=len(self._findings),
            findings=[f.as_dict() for f in self._findings],
            rule_ids=[f.rule for f in self._findings],
        )

    @property
    def ok(self) -> bool:
        return bool(self["ok"])

    @property
    def accepted(self) -> bool:
        return bool(self["accepted"])

    @property
    def findings(self) -> list[Finding]:
        return list(self._findings)

    @property
    def finding_count(self) -> int:
        return int(self["finding_count"])

    @property
    def rule_ids(self) -> list[str]:
        return list(self["rule_ids"])

    def as_dict(self) -> dict[str, Any]:
        return dict(self)


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
    return LintReport(ok=not findings, findings=findings)
