"""Two-rail evidence checker for RES-0049.

A claim with fewer than two mechanically independent rails (structured
API probe + prose source) is E3 and may not be cited as measured fact.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

REQUIRED_RAIL_FIELDS = (
    "rail",
    "kind",
    "permalink",
    "fetch_timestamp",
    "http_status",
    "sha256",
    "captured_bytes_path",
)
STRUCTURED = frozenset({"structured-api-probe"})
PROSE = frozenset({"prose-source", "prose"})
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rail_ok(repo: Path, rail: dict) -> tuple[bool, str]:
    for key in REQUIRED_RAIL_FIELDS:
        if key not in rail:
            return False, f"missing-field:{key}"
        if key == "http_status":
            continue
        if rail.get(key) in (None, ""):
            return False, f"empty-field:{key}"
    rel = str(rail.get("captured_bytes_path") or "").replace("\\", "/")
    path = repo / rel
    if not path.is_file():
        return False, f"capture-missing:{rel}"
    live = digest_file(path)
    claimed = str(rail.get("sha256") or "")
    if live != claimed:
        return False, f"sha-mismatch:{rel}"
    kind = str(rail.get("kind") or "")
    status = rail.get("http_status")
    if kind in PROSE:
        if status != 200:
            return False, f"prose-http-status:{status}"
    elif kind in STRUCTURED:
        if status not in (None, 0) and status != 200:
            return False, f"structured-http-status:{status}"
    else:
        return False, f"bad-kind:{kind}"
    return True, "ok"


def grade_claim(repo: Path, claim: dict) -> tuple[str, str]:
    rails = claim.get("rails") or []
    if not isinstance(rails, list) or len(rails) < 2:
        return "E3", "fewer-than-two-rails"
    kinds = set()
    ids = []
    for i, rail in enumerate(rails):
        if not isinstance(rail, dict):
            return "E3", f"rail[{i}]-not-object"
        ok, why = _rail_ok(repo, rail)
        if not ok:
            return "E3", f"rail[{i}]:{why}"
        kinds.add(str(rail.get("kind") or ""))
        ids.append(str(rail.get("rail") or ""))
    if not (kinds & STRUCTURED):
        return "E3", "no-structured-api-probe"
    if not (kinds & PROSE):
        return "E3", "no-prose-source"
    if len(set(ids)) < 2:
        return "E3", "rails-not-independent-ids"
    return "E1", "two-independent-rails"


def check_rails(repo: Path, doc: dict[str, Any]) -> tuple[bool, str]:
    claims = doc.get("claims")
    if not isinstance(claims, list) or len(claims) < 3:
        return False, "claims-missing-or-short"
    for i, claim in enumerate(claims):
        if not isinstance(claim, dict):
            return False, f"claims[{i}]-not-object"
        grade, why = grade_claim(repo, claim)
        declared = str(claim.get("evidence_tier") or "")
        if grade != "E1":
            return False, f"claims[{i}]-{grade}:{why}"
        if declared != "E1":
            return False, f"claims[{i}]-declared-tier:{declared}"
        if str(claim.get("verdict") or "") == "CONFIRMED" and grade != "E1":
            return False, f"claims[{i}]-CONFIRMED-but-{grade}"
    return True, f"claims={len(claims)} all-E1"
