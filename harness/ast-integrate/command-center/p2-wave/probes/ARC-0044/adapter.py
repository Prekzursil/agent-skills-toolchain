"""Two-vendor adapter for the permission-gated-write work-unit class.

The claimed A6 contract puts permission_semantics in GUARANTEED and treats a
schema-valid SUCCESS artifact as interchangeable across vendors.

That claim NECESSARILY lies: Claude-like confirmation semantics and Codex-like
declared-is-approved semantics cannot be the same rule. Both adapters still
satisfy the harness predicate (state + sentinel + schema), so the harness
reports SUCCESS while the side effect differs.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SCHEMA = "arc-0044-vendor-run/v1"
SENTINEL = "SUCCESS:PERMISSION-WRITE"
MARKER = "ARC-0044-SIDE-EFFECT"
WORK_UNIT = {
    "id": "WU-ARC-0044-PERM-WRITE",
    "class": "permission-gated-write",
    "declared_tier": "GUARANTEED",
    "tool_permissions": ["Write"],
    "target_rel": "marker.txt",
    "body": MARKER,
    "sentinel": SENTINEL,
}


def effect_digest(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def harness_predicate(art: dict[str, Any]) -> bool:
    """The lying predicate: schema + sentinel + SUCCESS, no effect compare."""
    return (
        art.get("schema") == SCHEMA
        and art.get("state") == "SUCCESS"
        and art.get("sentinel") == SENTINEL
        and isinstance(art.get("unit_id"), str)
        and art.get("unit_id") == WORK_UNIT["id"]
    )


def semantic_key(art: dict[str, Any]) -> tuple[Any, ...]:
    return (
        int(art.get("writes_applied") or 0),
        str(art.get("body") or ""),
        str(art.get("effect_digest") or ""),
    )


def effect_identity_guard(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """The catching check A6's own downgrade-refusal test would require."""
    same = a.get("effect_digest") == b.get("effect_digest")
    if same:
        return {"ok": True, "marker": "IDENTICAL-effect.digest"}
    return {
        "ok": False,
        "marker": "FAILED:ARC-0044 MISMATCH effect.digest",
        "left": a.get("effect_digest"),
        "right": b.get("effect_digest"),
    }


def dispatch(vendor: str, work: dict[str, Any], runs_dir: Path, effects_dir: Path) -> dict[str, Any]:
    if vendor == "claude-confirm":
        applied = False
        reason = (
            "permission_semantics: Write is declared but a confirmation hook is "
            "required; no confirm token is present, so the write is skipped"
        )
        permission_model = "confirm-to-write"
    elif vendor == "codex-auto":
        applied = True
        reason = "permission_semantics: Write declared means auto-approved; the write is applied"
        permission_model = "declared-is-approved"
    else:
        raise ValueError(f"unknown vendor {vendor}")

    body = work["body"] if applied else ""
    art = {
        "schema": SCHEMA,
        "unit_id": work["id"],
        "work_unit_class": work["class"],
        "declared_tier": work["declared_tier"],
        "vendor": vendor,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "writes_applied": 1 if applied else 0,
        "body": body,
        "effect_digest": effect_digest(body),
        "permission_model": permission_model,
        "reason": reason,
        "target_rel": work["target_rel"],
    }
    runs_dir.mkdir(parents=True, exist_ok=True)
    run_path = runs_dir / f"{vendor}.json"
    run_path.write_text(json.dumps(art, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    fx = effects_dir / vendor
    fx.mkdir(parents=True, exist_ok=True)
    marker = fx / work["target_rel"]
    if applied:
        marker.write_text(body + "\n", encoding="utf-8")
    elif marker.exists():
        marker.unlink()
    return art
