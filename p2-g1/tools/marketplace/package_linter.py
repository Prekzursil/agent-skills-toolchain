"""Package linter composer (IMP-0113).

The composer imports RULE_IDS / SUBCHECKS / STANDALONE_MODULES from
marketplace.checks and calls standalone_findings. It contains no SPDX lists,
no secret patterns, no size ceilings, no permission ids and no confusable
maps of its own: the finding set is exactly the union of the standalone
sub-checks, so composition and parts cannot drift apart.

Restored by the w4s8 resume session (2026-10-26) to the recorded IMP-0113
contract.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from marketplace.checks import RULE_IDS, STANDALONE_MODULES, SUBCHECKS, standalone_findings

__all__ = [
    "RULE_IDS",
    "STANDALONE_MODULES",
    "SUBCHECKS",
    "Finding",
    "LintReport",
    "composition_sets",
    "lint_package",
]


@dataclass
class Finding:
    rule: str
    detail: str = ""


@dataclass
class LintReport:
    ok: bool
    findings: list


def composition_sets(root: str | Path | None = None, enabled=None) -> dict[str, Any]:
    """The rule set currently composed. Disabling a gate changes the set, and
    the missing rule id is exactly the disabled gate."""
    rules = list(RULE_IDS) if enabled is None else [r for r in RULE_IDS if r in set(enabled)]
    return {
        "rules": rules,
        "standalone": list(STANDALONE_MODULES),
        "composer_reuses": True,
        "root": str(root or ""),
    }


def lint_package(path: Path | str, enabled=None) -> LintReport:
    root = Path(path)
    active = list(RULE_IDS) if enabled is None else [r for r in RULE_IDS if r in set(enabled)]
    findings: list[Finding] = []
    for rule_id in active:
        for row in standalone_findings(rule_id, root):
            findings.append(Finding(rule=str(row.get("rule") or rule_id), detail=str(row.get("detail") or "")))
    ok = not findings
    return {
        "ok": ok,
        "accepted": ok,
        "findings": [{"rule": f.rule, "detail": f.detail} for f in findings],
        "rule_ids": [f.rule for f in findings],
    }
