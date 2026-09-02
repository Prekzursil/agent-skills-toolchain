#!/usr/bin/env python3
"""Three A7 sample capabilities plus the first inexpressible construct."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from bundles import scan_bundle
from evaluator import InvalidGrantSet, evaluate, validate_grants
from injection import content_cannot_mint_grants
from signing import sign_artifact, verify_artifact


def _sha(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


BASE_GRANTS = [
    {"effect": "grant", "class": "tool", "action": "invoke", "selector": "Read"},
    {"effect": "grant", "class": "path", "action": "read", "selector": "command-center/**"},
    {"effect": "deny", "class": "credential", "action": "read", "selector": "env:OPENAI_API_KEY"},
]


def _row(
    *,
    kind: str,
    ident: str,
    source_id: str,
    source_citation: str,
    transcription_basis: str,
    body: dict[str, Any],
    invocation: dict[str, Any],
) -> dict[str, Any]:
    prov = sign_artifact(body, ident)
    checked = verify_artifact(body, prov)
    invocation = {
        **invocation,
        "provenance": {**prov, **checked},
    }
    decision = evaluate(invocation, body["grants"])
    inj = content_cannot_mint_grants(body)
    ok = decision["effect"] == "GRANT" and inj["ok"] is True
    return {
        "kind": kind,
        "id": ident,
        "source_id": source_id,
        "source_citation": source_citation,
        "transcription_basis": transcription_basis,
        "verdict": "EXPRESSIBLE" if ok else "INEXPRESSIBLE",
        "sha256": _sha(body),
        "transcription": {
            "form": "a7-capability/v1",
            "config": body,
            "choke_decision": decision,
            "injection_boundary": inj,
            "provenance": prov,
        },
    }


def skill_sample() -> dict[str, Any]:
    body = {
        "id": "skill.council",
        "kind": "skill",
        "source_id": "skills/council/SKILL.md",
        "grants": BASE_GRANTS,
        "instructions": "Four named roles as static prompt sections. Content that mentions grant * is not a grant.",
        "roles": ["Architect", "Skeptic", "Pragmatist", "Critic"],
        "runtime": False,
        "councilspec": False,
    }
    return _row(
        kind="skill",
        ident="skill.council",
        source_id="skills/council/SKILL.md",
        source_citation="command-center/WORK-UNIT-CATALOG.json items[id=R-A09].evidence",
        transcription_basis="catalog-cited fields plus A7 named grants, signed provenance, secret-free bundle; file absent on this worktree",
        body=body,
        invocation={
            "subject": "skill.council",
            "class": "tool",
            "action": "invoke",
            "selector": "Read",
            "bundle": scan_bundle({"SKILL.md": b"# council skill\n"}),
        },
    )


def workflow_sample() -> dict[str, Any]:
    body = {
        "id": "wf.catalog-class.discovery-only",
        "kind": "workflow_blueprint",
        "source_id": "09-WORKFLOW-BLUEPRINT-LIBRARY.json#discovery_only",
        "discovery_only": True,
        "grants": [
            {
                "effect": "grant",
                "class": "workflow",
                "action": "execute",
                "selector": "wf.catalog-class.discovery-only",
            }
        ],
        "stages": [
            {"id": "discover", "kind": "static-scan", "inputs": ["repo"], "outputs": ["candidates.json"]},
            {"id": "record", "kind": "write-config", "inputs": ["candidates.json"], "outputs": ["blueprint.json"]},
        ],
        "stopping": {"max_stages": 2, "on_error": "halt"},
        "prompt": "Do not evaluate(user). A mention of evaluate() in this prompt is not a grant.",
    }
    return _row(
        kind="workflow_blueprint",
        ident="wf.catalog-class.discovery-only",
        source_id="09-WORKFLOW-BLUEPRINT-LIBRARY.json#discovery_only",
        source_citation="command-center/WORK-UNIT-CATALOG.json items[id=R-A08].evidence",
        transcription_basis="library absent; A7 typed workflow with named execute grant and injection-resistant prompt field",
        body=body,
        invocation={
            "subject": "wf.catalog-class.discovery-only",
            "class": "workflow",
            "action": "execute",
            "selector": "wf.catalog-class.discovery-only",
            "bundle": scan_bundle({"blueprint.json": b'{"discovery_only":true}\n'}),
        },
    )


def council_sample() -> dict[str, Any]:
    body = {
        "id": "council.preset.catalog-class.editable",
        "kind": "council_preset",
        "source_id": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json#presets",
        "editable": True,
        "grants": [
            {
                "effect": "grant",
                "class": "council",
                "action": "invoke",
                "selector": "council.preset.catalog-class.editable",
            }
        ],
        "roles": ["Architect", "Skeptic", "Pragmatist", "Critic"],
        "transcript": "Skeptic: a grant * for the vendor would skip the choke. Mention only.",
    }
    return _row(
        kind="council_preset",
        ident="council.preset.catalog-class.editable",
        source_id="12-COUNCIL-PROTOCOLS-AND-PRESETS.json#presets",
        source_citation="command-center/WORK-UNIT-CATALOG.json items[id=R-A09].evidence+disposition_evidence",
        transcription_basis="library absent; A7 council preset with named invoke grant; transcript cannot mint grants",
        body=body,
        invocation={
            "subject": "council.preset.catalog-class.editable",
            "class": "council",
            "action": "invoke",
            "selector": "council.preset.catalog-class.editable",
            "bundle": scan_bundle({"preset.json": b'{"editable":true}\n'}),
        },
    )


def inexpressible_trusted_publisher() -> dict[str, Any]:
    """First construct A7 refuses: ambient vendor-trust that skips the choke."""
    body = {
        "id": "cap.trusted-publisher.skip-choke",
        "kind": "mcp_mount",
        "trusted_publisher": True,
        "skip_evaluator": True,
        "grants": [
            {
                "effect": "grant",
                "class": "tool",
                "action": "*",
                "selector": "*",
                "trusted_publisher": True,
                "skip_evaluator": True,
            }
        ],
    }
    try:
        validate_grants(body["grants"])
        declared_ok = True
        decl_error = ""
    except InvalidGrantSet as exc:
        declared_ok = False
        decl_error = "; ".join(exc.errors)
    invocation = {
        "subject": "cap.trusted-publisher.skip-choke",
        "class": "tool",
        "action": "invoke",
        "selector": "Bash",
        "skip_evaluator": True,
        "trusted_publisher_bypass": True,
        "provenance": {"ok": True, "digest": "00"},
        "bundle": {"secret_free": True},
    }
    forced = [
        {"effect": "grant", "class": "tool", "action": "invoke", "selector": "Bash"},
    ]
    decision = evaluate(invocation, forced)
    return {
        "kind": "mcp_mount",
        "id": "cap.trusted-publisher.skip-choke",
        "source_id": "A7-negative/trusted-publisher-bypass",
        "verdict": "INEXPRESSIBLE",
        "sha256": _sha(body),
        "transcription": {
            "form": "a7-capability/v1",
            "config": body,
            "declaration_accepted": declared_ok,
            "declaration_error": decl_error,
            "forced_evaluate": decision,
        },
        "construct": "trusted-publisher ambient grant that skips a7.permission.evaluate",
    }


def all_samples() -> list[dict[str, Any]]:
    return [skill_sample(), workflow_sample(), council_sample()]
