#!/usr/bin/env python3
"""Independent span auditor: substring + token-subset, no template regexes.

This is the second mechanical signal. It does not import protocol.TEMPLATES.
A TRANSFORMABLE claim is accepted only when required slots are contiguous
substrings of the source and introduce no extra tokens.
"""
from __future__ import annotations

import re
from typing import Any

TOKEN_RE = re.compile(r"[A-Za-z0-9_./:+-]+")
WS_RE = re.compile(r"\s+")
GLUE = frozenset(
    {"locally", "and", "check", "whether", "by", "performing", "looking", "for"}
)


def _norm(text: str) -> str:
    return WS_RE.sub(" ", (text or "").strip()).lower()


def _tokens(text: str) -> list[str]:
    out: list[str] = []
    for m in TOKEN_RE.finditer(text or ""):
        tok = m.group(0).lower().strip(".,;:")
        if tok:
            out.append(tok)
    return out


def is_contiguous_span(source: str, span: str) -> bool:
    if not span or not source:
        return False
    return _norm(span) in _norm(source)


def extra_tokens(source: str, field: str, allow: frozenset[str] | None = None) -> list[str]:
    allow = allow or frozenset()
    src = set(_tokens(source))
    extra = []
    for tok in _tokens(field):
        if tok not in src and tok not in allow:
            extra.append(tok)
    return extra


def audit_transform(source: str, result: dict[str, Any]) -> dict[str, Any]:
    """Audit one protocol result against its source text."""
    errors: list[str] = []
    disp = result.get("disposition")
    if disp == "NOT-TRANSFORMABLE":
        if result.get("claim") is not None:
            errors.append("not-transformable-but-claim-present")
        return {"ok": not errors, "errors": errors, "disposition": disp}

    if disp != "TRANSFORMABLE":
        return {"ok": False, "errors": [f"unknown-disposition:{disp}"], "disposition": disp}

    claim = result.get("claim") or {}
    pre = claim.get("precondition") or ""
    obs = claim.get("observable") or ""
    exp = claim.get("local_experiment") or {}
    if not is_contiguous_span(source, pre):
        errors.append("precondition-not-contiguous-span")
    if not is_contiguous_span(source, obs):
        errors.append("observable-not-contiguous-span")
    if extra_tokens(source, pre):
        errors.append(f"precondition-extra-tokens:{extra_tokens(source, pre)}")
    if extra_tokens(source, obs):
        errors.append(f"observable-extra-tokens:{extra_tokens(source, obs)}")
    if exp.get("do") != pre:
        errors.append("experiment-do-mismatch")
    if exp.get("look_for") != obs:
        errors.append("experiment-look_for-mismatch")
    proc = exp.get("procedure") or ""
    if extra_tokens(source, proc, allow=GLUE):
        errors.append(f"procedure-extra-tokens:{extra_tokens(source, proc, allow=GLUE)}")
    inferred = result.get("inferred_labels") or []
    if not any(x.get("label") == "claim_kind" and "INFERRED" in str(x).upper() or x.get("inference") for x in inferred):
        # require at least one stated inference on the classification label
        if not any(x.get("inference") for x in inferred):
            errors.append("classification-inference-unstated")
    diff = result.get("source_diff") or {}
    for slot in ("precondition", "observable"):
        block = diff.get(slot) or {}
        if block.get("inferred"):
            errors.append(f"required-slot-inferred:{slot}")
    return {"ok": not errors, "errors": errors, "disposition": disp}


def fabricate(source: str) -> dict[str, Any]:
    """Always-claim protocol: the negative control a honest protocol must beat."""
    return {
        "protocol_id": "fabricator-v0",
        "disposition": "TRANSFORMABLE",
        "reason": "always-claim",
        "precondition": "did Y",
        "observable": "X broke",
        "claim": {
            "precondition": "did Y",
            "observable": "X broke",
            "local_experiment": {
                "kind": "local-reproduce",
                "do": "did Y",
                "look_for": "X broke",
                "procedure": "Locally did Y and check whether X broke.",
            },
            "source_span_verified": False,
        },
        "source_diff": {
            "precondition": {"inferred": [{"token": "Y", "inference": "invented"}]},
            "observable": {"inferred": [{"token": "X", "inference": "invented"}]},
            "procedure": {"inferred": []},
        },
        "inferred_labels": [],
        "local_experiment": {
            "kind": "local-reproduce",
            "do": "did Y",
            "look_for": "X broke",
            "procedure": "Locally did Y and check whether X broke.",
        },
    }


audit_transform = audit_transform
extra_tokens = extra_tokens
fabricate = fabricate
is_contiguous_span = is_contiguous_span
