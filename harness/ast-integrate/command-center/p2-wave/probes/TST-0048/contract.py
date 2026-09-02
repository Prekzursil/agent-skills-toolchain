#!/usr/bin/env python3
"""Rollback contract rules for TST-0048 (tests written before broad implementation).

Restore vs preserve is explicit. Failure class :11347 (rollback removes existing
commands or user data) is a construction invariant, not a convention comment:
an inverse action may only target a path in the installer CreationSet.
"""
from __future__ import annotations

from typing import Any

# Catalog question (WORK-UNIT-CATALOG.json TST-0048).
QUESTION = (
    "Does the rollback contract specify exactly which state is restored and "
    "which is preserved, and is 'rollback removes existing commands or user "
    "data' (:11347) impossible by construction rather than by convention?"
)

SPEC_ANCHORS = {
    "contract_line": 10818,
    "tests_before_implementation": 10822,
    "failure_class_user_data": 11347,
}

# Restored: previous version / configuration / deployed tree of installer-managed paths.
RESTORE_CLASSES = (
    "previous-version",
    "previous-configuration",
    "previous-deployed-tree-installer-managed",
)

# Preserved: never destroyed, even when they sit inside the managed tree.
PRESERVE_CLASSES = (
    "owner-authored-edits",
    "user-data",
    "mcp-enable-disable-curation",
    "credential-stores",
    "pre-existing-commands-skills-settings",
)

RULES: tuple[dict[str, Any], ...] = (
    {
        "id": "R1-RESTORE-VERSION",
        "axis": "restore",
        "restores": "previous-version",
        "negative": "installer-managed version bytes differ from the pre-change backup",
    },
    {
        "id": "R2-RESTORE-CONFIG",
        "axis": "restore",
        "restores": "previous-configuration",
        "negative": "installer-managed configuration bytes differ from backup",
    },
    {
        "id": "R3-RESTORE-DEPLOYED-TREE",
        "axis": "restore",
        "restores": "previous-deployed-tree-installer-managed",
        "negative": "an installer-created path is missing or extra versus backup",
    },
    {
        "id": "R4-PRESERVE-OWNER-EDITS",
        "axis": "preserve",
        "preserves": "owner-authored-edits",
        "negative": "an owner-authored path is missing or its bytes changed",
    },
    {
        "id": "R5-PRESERVE-USER-DATA",
        "axis": "preserve",
        "preserves": "user-data",
        "negative": "a user-owned data path is missing after rollback",
    },
    {
        "id": "R6-PRESERVE-MCP-CURATION",
        "axis": "preserve",
        "preserves": "mcp-enable-disable-curation",
        "negative": "MCP enable/disable curation bytes changed or the file was removed",
    },
    {
        "id": "R7-PRESERVE-CREDENTIALS",
        "axis": "preserve",
        "preserves": "credential-stores",
        "negative": "credential-store path missing or bytes changed",
    },
    {
        "id": "R8-PRE-CHANGE-BACKUP",
        "axis": "procedure",
        "requires": "backup of installer-managed paths recorded before the first write",
        "negative": "a mutating write occurs with no backup recorded first",
    },
    {
        "id": "R9-PROOF-OF-RESTORE",
        "axis": "procedure",
        "requires": "post-restore content hash per restored path",
        "negative": "a restored path has no verification hash",
    },
    {
        "id": "R10-COMPLETE-ONLY-AFTER-VERIFY",
        "axis": "procedure",
        "requires": "rollback is not complete until verification passes",
        "negative": "complete=true while a restored hash mismatches the backup",
    },
    {
        "id": "R11-INVERSE-CREATION-SET",
        "axis": "construction-11347",
        "requires": "an inverse never removes a path the installer did not create",
        "negative": "unlink/remove of a path outside CreationSet",
    },
    {
        "id": "R12-INVERSE-PREEXISTING",
        "axis": "construction-11347",
        "requires": "an inverse never removes a command, skill or setting that pre-dated install",
        "negative": "a pre-existing command/skill/setting path is absent after rollback",
    },
)

RULE_IDS: tuple[str, ...] = tuple(r["id"] for r in RULES)


def rule_by_id(rid: str) -> dict[str, Any]:
    for row in RULES:
        if row["id"] == rid:
            return row
    raise KeyError(rid)
