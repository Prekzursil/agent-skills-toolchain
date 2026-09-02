#!/usr/bin/env python3
"""Four engineering blueprints 13-16 as contract-gated registrations."""
from __future__ import annotations

from typing import Any

import marketplace_conformance as mkt
import plugin_conformance as plug
from contract import omission_matrix, register
from go_no_go import release_go_no_go
from rollback import rehearse

PLUGIN = {
    "name": "plugin-conformance",
    "workflow": {
        "id": "wf.engineering.plugin-conformance",
        "kind": "workflow_blueprint",
        "discovery_only": False,
        "stages": [
            {"id": "unpack", "kind": "read-package", "inputs": ["package.zip"], "outputs": ["tree"]},
            {"id": "lint", "kind": "plugin-lint", "inputs": ["tree"], "outputs": ["lint.json"]},
        ],
        "stopping": {"max_stages": 2, "on_error": "halt"},
    },
    "example": {
        "id": "ex.plugin-conformance.benign",
        "input": {"package": "fixtures/plugin-benign-1.0.0.zip"},
        "expect": {"ok": True},
    },
    "preset": {
        "id": "preset.plugin-conformance.strict",
        "bindings": {"additionalProperties": False, "install_hooks": "reject"},
    },
    "stopping_rules": {
        "max_stages": 2,
        "on_error": "halt",
        "documented": "Halt on first lint rule fire; do not install a rejected package.",
    },
    "smoke_test": plug.smoke,
    "capability_vector": ["plugin.lint", "plugin.schema", "plugin.package-root"],
}

MARKETPLACE = {
    "name": "marketplace-conformance",
    "workflow": {
        "id": "wf.engineering.marketplace-conformance",
        "kind": "workflow_blueprint",
        "discovery_only": False,
        "stages": [
            {
                "id": "compare-versions",
                "kind": "listing-lint",
                "inputs": ["listing.json", "plugin.json"],
                "outputs": ["lint.json"],
            },
            {
                "id": "resolve-evidence",
                "kind": "ledger-lookup",
                "inputs": ["lint.json", "ledger.json"],
                "outputs": ["verdict.json"],
            },
        ],
        "stopping": {"max_stages": 2, "on_error": "halt"},
    },
    "example": {
        "id": "ex.marketplace-conformance.resolved-evidence",
        "input": {"listing": "benign_listing", "ledger": "LEDGER"},
        "expect": {"ok": True},
    },
    "preset": {
        "id": "preset.marketplace-conformance.ledger-evidence",
        "bindings": {"evidence_shape": "ledger-reference", "free_text": "reject"},
    },
    "stopping_rules": {
        "max_stages": 2,
        "on_error": "halt",
        "documented": "Unresolved or free-text evidence is a hard halt, not a warning.",
    },
    "smoke_test": mkt.smoke,
    "capability_vector": ["marketplace.lint", "marketplace.evidence-ledger", "marketplace.version-agree"],
}

GO_NO_GO = {
    "name": "release-go-no-go",
    "workflow": {
        "id": "wf.engineering.release-go-no-go",
        "kind": "workflow_blueprint",
        "discovery_only": False,
        "stages": [
            {
                "id": "gather-evidence",
                "kind": "read-disk",
                "inputs": ["receipt", "manifest"],
                "outputs": ["evidence.json"],
            },
            {
                "id": "oracle-judge",
                "kind": "shared-completion-predicate",
                "inputs": ["evidence.json"],
                "outputs": ["verdict.json"],
            },
        ],
        "stopping": {"max_stages": 2, "on_error": "halt"},
    },
    "example": {
        "id": "ex.release-go-no-go.complete",
        "input": {"evidence": "fixture-complete"},
        "expect": {"decision": "GO"},
    },
    "preset": {
        "id": "preset.release-go-no-go.shared-oracle",
        "bindings": {"reducer": "oracle.judge", "local_checklist": False},
    },
    "stopping_rules": {
        "max_stages": 2,
        "on_error": "halt",
        "documented": "NO-GO when the shared oracle returns INCOMPLETE, including NOT-CHECKED.",
    },
    "smoke_test": {"callable": release_go_no_go},
    "capability_vector": ["release.go-no-go", "completion.oracle.judge"],
}

ROLLBACK = {
    "name": "rollback-rehearsal",
    "workflow": {
        "id": "wf.engineering.rollback-rehearsal",
        "kind": "workflow_blueprint",
        "discovery_only": False,
        "stages": [
            {
                "id": "install-v1",
                "kind": "package-install",
                "inputs": ["v1.zip"],
                "outputs": ["profile"],
            },
            {
                "id": "plant-user-data",
                "kind": "write-user-data",
                "inputs": ["profile"],
                "outputs": ["planted.bin"],
            },
            {
                "id": "upgrade-v2",
                "kind": "package-install",
                "inputs": ["v2.zip", "profile"],
                "outputs": ["profile"],
            },
            {
                "id": "rollback-v1",
                "kind": "packaged-artifact-restore",
                "inputs": ["v1.zip", "profile"],
                "outputs": ["inventory-diff.json"],
            },
        ],
        "stopping": {"max_stages": 4, "on_error": "halt"},
    },
    "example": {
        "id": "ex.rollback-rehearsal.userdata-survives",
        "input": {"planted": "user-data/notes.txt"},
        "expect": {"hash_match": True},
    },
    "preset": {
        "id": "preset.rollback-rehearsal.additive-restore",
        "bindings": {"touch_user_data": False, "source": "packaged-artifact"},
    },
    "stopping_rules": {
        "max_stages": 4,
        "on_error": "halt",
        "documented": "Any user-data path present before and absent after is a hard failure.",
    },
    "smoke_test": {"callable": rehearse},
    "capability_vector": ["release.rollback", "userdata.preserve", "package.restore"],
}

ALL = (PLUGIN, MARKETPLACE, GO_NO_GO, ROLLBACK)


def register_all() -> list[dict[str, Any]]:
    return [register(bp) for bp in ALL]


def contract_omission_controls() -> dict[str, Any]:
    rows = {}
    for bp in ALL:
        matrix = omission_matrix(bp)
        ids = [r["rejection"] for r in matrix]
        rows[bp["name"]] = {
            "distinct": len(set(ids)) == 6,
            "all_rejected": all(r["ok"] is False for r in matrix),
            "rejections": ids,
        }
    return rows
