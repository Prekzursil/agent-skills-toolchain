#!/usr/bin/env python3
"""Blinding dispatcher: confirmer payload from source + tests + statement only.

Per dispatch it answers, from stored bytes rather than agent assurance: did
the confirmer's input contain a conclusion from the party being confirmed?
"""
from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Any

from allowlist import (
    ATTESTATION_SEP,
    CLAIM_DROP_KEYS,
    CLAIM_KEEP_KEYS,
    CONCLUSION_NEEDLES,
    DENY_NAME_FRAGMENTS,
    DENY_PATH_PARTS,
    RECEIPT_SHAPE_ALL,
    RECEIPT_SHAPE_ANY,
    SKIP_DIR_NAMES,
    SOURCE_PREFIXES,
    SOURCE_SUFFIXES,
    TEST_NAME_PREFIXES,
    TEST_PREFIXES,
    attestation_formula,
    canonical_rules_bytes,
    lf_bytes,
    posix_rel,
)

CLAIM_FILENAMES = ("CLAIM.json", "claim.json")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def attestation_material(payload: bytes, rules: bytes | None = None) -> bytes:
    rules = rules if rules is not None else canonical_rules_bytes()
    return rules + ATTESTATION_SEP + lf_bytes(payload)


def attest(payload: bytes, rules: bytes | None = None) -> str:
    return sha256_hex(attestation_material(payload, rules))


def verify(payload: bytes, expected: str, rules: bytes | None = None) -> bool:
    got = attest(payload, rules)
    if not isinstance(expected, str) or len(expected) != len(got):
        return False
    return hmac.compare_digest(got, expected)


def _parts(rel: str) -> list[str]:
    return [p for p in posix_rel(rel).split("/") if p]


def _name(rel: str) -> str:
    parts = _parts(rel)
    return parts[-1] if parts else ""


def _deny_path_rule(rel: str) -> tuple[str, str] | None:
    rel_l = posix_rel(rel).lower()
    name_l = _name(rel).lower()
    parts_l = [p.lower() for p in _parts(rel)]
    for rule_id, tokens in DENY_PATH_PARTS.items():
        for tok in tokens:
            if tok in parts_l:
                return rule_id, f"path-part:{tok}"
    for rule_id, frags in DENY_NAME_FRAGMENTS.items():
        for frag in frags:
            if frag in name_l:
                return rule_id, f"name-fragment:{frag}"
    if rel_l.endswith(".json") and "receipt" in rel_l:
        return "A4", "path-receipt-json"
    return None


def _looks_like_receipt(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if any(needle in text for needle in CONCLUSION_NEEDLES):
        return True
    if stripped[:1] not in "{[":
        return False
    try:
        doc = json.loads(stripped)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return False
    if not isinstance(doc, dict):
        return False
    if all(k in doc for k in RECEIPT_SHAPE_ALL) and any(k in doc for k in RECEIPT_SHAPE_ANY):
        return True
    if any(k in doc for k in CLAIM_DROP_KEYS) and ("unit_id" in doc or "claim_id" in doc):
        return True
    return False


def _include_role(rel: str) -> str | None:
    rel_p = posix_rel(rel)
    name = _name(rel_p)
    lower = rel_p.lower()
    if any(lower.startswith(p) for p in TEST_PREFIXES) or name.startswith(TEST_NAME_PREFIXES):
        return "test"
    if any(lower.startswith(p) for p in SOURCE_PREFIXES):
        if any(lower.endswith(s) for s in SOURCE_SUFFIXES) or lower.endswith(".json"):
            return "source"
        return "source"
    return None


def classify(rel: str, data: bytes) -> tuple[str | None, str | None, str | None]:
    """Return (role, exclude_reason, rule_id). role is set when included."""
    rel_p = posix_rel(rel)
    if _name(rel_p) in CLAIM_FILENAMES:
        return None, "claim-file-parsed-separately", "A1"
    deny = _deny_path_rule(rel_p)
    if deny:
        return None, deny[1], deny[0]
    text = lf_bytes(data).decode("utf-8", errors="replace")
    if _looks_like_receipt(text):
        return None, "content-receipt-shape", "A7"
    role = _include_role(rel_p)
    if role:
        return role, None, "A3" if role == "test" else "A2"
    return None, "not-on-allow-list", "A12"


def walk_files(root: Path) -> list[tuple[str, Path]]:
    out: list[tuple[str, Path]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        rel = posix_rel(path.relative_to(root).as_posix())
        out.append((rel, path))
    out.sort(key=lambda item: item[0])
    return out


def load_claim(root: Path) -> dict[str, Any] | None:
    for name in CLAIM_FILENAMES:
        path = root / name
        if path.is_file():
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return None
            if isinstance(doc, dict):
                return doc
    return None


def _sanitize_statement(statement: str) -> tuple[str, list[str]]:
    dropped: list[str] = []
    kept: list[str] = []
    for line in statement.splitlines():
        if any(needle in line for needle in CONCLUSION_NEEDLES):
            dropped.append(line)
            continue
        kept.append(line)
    return "\n".join(kept).strip(), dropped


def _claim_section(claim: dict[str, Any] | None, exclusion_enabled: bool) -> tuple[str, list[str]]:
    if not claim:
        return "", []
    if not exclusion_enabled:
        blob = json.dumps(claim, sort_keys=True, indent=2, ensure_ascii=True)
        return f"claim_full_json:\n{blob}\n", []
    statement = str(claim.get("statement") or claim.get("question") or "")
    clean, dropped = _sanitize_statement(statement)
    claim_id = str(claim.get("claim_id") or claim.get("id") or "")
    lines = ["claim_id: " + claim_id, "statement:", clean]
    extra = [k for k in claim.keys() if k not in CLAIM_KEEP_KEYS and k in CLAIM_DROP_KEYS]
    return "\n".join(lines) + "\n", extra + dropped


def assemble_payload(
    included: list[dict[str, Any]],
    claim_section: str,
) -> bytes:
    chunks = ["# CNF-0130 blinded confirmation prompt", claim_section.rstrip(), ""]
    for item in included:
        chunks.append(f"## {item['role']}: {item['path']}")
        body = item["text"]
        if body and not body.endswith("\n"):
            body += "\n"
        chunks.append(body)
    text = "\n".join(chunks)
    if not text.endswith("\n"):
        text += "\n"
    return lf_bytes(text.encode("utf-8"))


def diff_vs_excluded(payload: bytes, excluded_bodies: list[tuple[str, bytes]]) -> list[dict[str, str]]:
    """Second signal: payload must not contain any excluded artifact's bytes."""
    hits: list[dict[str, str]] = []
    payload_text = lf_bytes(payload).decode("utf-8", errors="replace")
    for path, body in excluded_bodies:
        raw = lf_bytes(body)
        if not raw.strip():
            continue
        text = raw.decode("utf-8", errors="replace")
        if raw in payload or (len(text.strip()) >= 24 and text.strip() in payload_text):
            hits.append({"path": path, "how": "body-substring"})
            continue
        for needle in CONCLUSION_NEEDLES:
            if needle in text and needle in payload_text:
                hits.append({"path": path, "how": f"needle:{needle}"})
                break
    return hits


def dispatch(
    root: Path,
    *,
    exclusion_enabled: bool = True,
    claim: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(root)
    claim = claim if claim is not None else load_claim(root)
    included: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    excluded_bodies: list[tuple[str, bytes]] = []
    for rel, path in walk_files(root):
        data = lf_bytes(path.read_bytes())
        role, reason, rule_id = classify(rel, data)
        rec = {
            "path": rel,
            "bytes": len(data),
            "sha256": sha256_hex(data),
            "rule_id": rule_id,
        }
        if exclusion_enabled and reason:
            rec["reason"] = reason
            excluded.append(rec)
            # The claim file is parsed into statement-only text. Its body
            # necessarily overlaps the payload, so it is not part of the
            # excluded-artifact union used for the empty-diff signal.
            if reason != "claim-file-parsed-separately":
                excluded_bodies.append((rel, data))
            continue
        if exclusion_enabled and not role:
            rec["reason"] = reason or "not-on-allow-list"
            excluded.append(rec)
            excluded_bodies.append((rel, data))
            continue
        if not exclusion_enabled:
            role = role or "unfiltered"
        rec["role"] = role
        rec["text"] = data.decode("utf-8", errors="replace")
        included.append(rec)
    claim_section, claim_drops = _claim_section(claim, exclusion_enabled)
    payload = assemble_payload(included, claim_section)
    rules = canonical_rules_bytes()
    hits = diff_vs_excluded(payload, excluded_bodies) if exclusion_enabled else []
    record = {
        "claim_id": (claim or {}).get("claim_id") or (claim or {}).get("id"),
        "exclusion_enabled": exclusion_enabled,
        "payload": payload.decode("utf-8"),
        "payload_sha256": sha256_hex(payload),
        "attestation": attest(payload, rules),
        "attestation_formula": attestation_formula(),
        "allow_list_source": "command-center/p2-wave/probes/CNF-0130/allowlist.py",
        "rules_sha256": sha256_hex(rules),
        "canonical_rules_json": rules.decode("utf-8"),
        "included": [
            {k: v for k, v in item.items() if k != "text"} for item in included
        ],
        "excluded": excluded,
        "claim_fields_dropped": claim_drops,
        "payload_vs_excluded_hits": hits,
        "contamination_free": exclusion_enabled and not hits,
        "question": (
            "Can we prove, from the artifact and not from the agent's assurance, "
            "that the confirmer's input contained no conclusion from the party "
            "being confirmed?"
        ),
        "answer_from_artifact": bool(exclusion_enabled)
        and not hits
        and not any(n in payload.decode("utf-8") for n in CONCLUSION_NEEDLES),
    }
    return record


def recompute_attestation(payload: bytes | str, rules_json: str | bytes) -> str:
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    if isinstance(rules_json, str):
        rules_json = rules_json.encode("utf-8")
    return attest(payload, rules_json)
