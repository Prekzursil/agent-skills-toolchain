"""CNF-0130-style blinding: confirmer sees source, tests, and the claim statement.

Implementer receipts, review verdicts, planted labels, and prior confirmations
are excluded. Attestation = sha256(canonical payload || allow-list ruleset).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"

ALLOW_RULES: dict[str, Any] = {
    "allow_payload_keys": [
        "claim_id",
        "statement",
        "cited_revision",
        "source_files",
        "test_files",
        "instructions",
    ],
    "deny_path_substrings": [
        "receipts/",
        "implementer-receipt",
        "review-verdict",
        "prior-confirmation",
        "planted_oracle",
    ],
    "deny_payload_keys": [
        "planted",
        "ground_truth",
        "implementer_verdict",
        "prior_confirmation",
        "oracle_label",
    ],
}

INSTRUCTIONS = (
    "You are a cross-vendor confirmer. Starting from raw source and tests "
    "only, evaluate the claim STATEMENT. Emit one confirmation-record JSON "
    "object. Do not read implementer receipts or prior confirmations. "
    "Never treat a [codex] progress stream as the result; write only the "
    "confirmation record to the output-last-message file."
)


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def is_denied_rel(rel: str) -> bool:
    norm = rel.replace("\\", "/")
    return any(s in norm for s in ALLOW_RULES["deny_path_substrings"])


def attestation_of(payload: dict[str, Any]) -> str:
    raw = canonical(payload) + b"\n" + canonical(ALLOW_RULES)
    return hashlib.sha256(raw).hexdigest()


def assemble(
    claim: dict[str, Any],
    *,
    extra_candidates: dict[str, str] | None = None,
    exclusion_enabled: bool = True,
) -> dict[str, Any]:
    src_rel = claim["source_rel"]
    test_rel = claim["test_rel"]
    src_root = FIXTURES
    source_files: dict[str, str] = {}
    test_files: dict[str, str] = {}
    excluded: list[str] = []

    def take(rel: str, bucket: dict[str, str]) -> None:
        if exclusion_enabled and is_denied_rel(rel):
            excluded.append(rel)
            return
        bucket[rel] = (src_root / rel).read_text(encoding="utf-8")

    take(src_rel, source_files)
    take(test_rel, test_files)

    extras_kept: dict[str, str] = {}
    for rel, content in (extra_candidates or {}).items():
        if exclusion_enabled and is_denied_rel(rel):
            excluded.append(rel)
            continue
        extras_kept[rel] = content

    payload = {
        "claim_id": claim["claim_id"],
        "statement": claim["statement"],
        "cited_revision": claim["cited_revision"],
        "source_files": source_files,
        "test_files": test_files,
        "instructions": INSTRUCTIONS,
    }
    if extras_kept:
        payload["source_files"] = {**source_files, **extras_kept}

    leaked = [k for k in ALLOW_RULES["deny_payload_keys"] if k in payload]
    if leaked:
        raise RuntimeError(f"blinding leaked deny keys: {leaked}")

    att = attestation_of(payload)
    return {
        "payload": payload,
        "attestation": att,
        "excluded": excluded,
        "allow_rules": ALLOW_RULES,
    }
