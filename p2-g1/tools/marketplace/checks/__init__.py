"""Standalone sub-checks of the package linter (IMP-0113).

The composer (marketplace.package_linter) imports RULE_IDS / SUBCHECKS /
STANDALONE_MODULES from here and calls standalone_findings; it contains no
rule bodies of its own -- the union of the standalone checks IS the linter.
"""
from __future__ import annotations

from marketplace.checks import (  # noqa: F401
    license as license,
    manifest as manifest,
    name_grammar as name_grammar,
    permissions as permissions,
    secrets as secrets,
    size_budget as size_budget,
)

RULE_IDS = (
    "manifest-schema",
    "spdx-license",
    "permission-declaration",
    "size-budget",
    "secret-gate",
    "name-grammar",
)

SUBCHECKS = {
    "manifest-schema": manifest.standalone_findings,
    "spdx-license": license.standalone_findings,
    "permission-declaration": permissions.standalone_findings,
    "size-budget": size_budget.standalone_findings,
    "secret-gate": secrets.standalone_findings,
    "name-grammar": name_grammar.standalone_findings,
}

STANDALONE_MODULES = (
    "marketplace.checks.manifest",
    "marketplace.checks.license",
    "marketplace.checks.permissions",
    "marketplace.checks.size_budget",
    "marketplace.checks.secrets",
    "marketplace.checks.name_grammar",
)


def standalone_findings(rule_id: str, root):
    return SUBCHECKS[rule_id](root)
