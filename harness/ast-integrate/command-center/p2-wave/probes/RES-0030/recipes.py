"""Goose recipes surface (distinct from lead/worker fallback)."""
from __future__ import annotations

import hashlib
from typing import Any

from constants import FIXTURES, RECIPE_REF_MAIN_RAW, RECIPE_REF_REL, SESSION_RECIPES_MAIN_RAW
from fetchutil import fetch_body, lineage


REQUIRED_FIELDS = ("title", "description", "instructions")


def extract_recipes() -> dict[str, Any]:
    live = fetch_body(RECIPE_REF_MAIN_RAW)
    fixture = FIXTURES / "recipe-reference.md"
    fixture_sha = hashlib.sha256(fixture.read_bytes()).hexdigest() if fixture.is_file() else None
    if live.get("status") == 200 and live.get("body"):
        text = live["body"].decode("utf-8")
        sha = live["sha256"]
        status = live["status"]
        fetched_at = live["fetched_at"]
        url = RECIPE_REF_MAIN_RAW
        source = "live-main"
    else:
        if not fixture.is_file():
            raise RuntimeError("recipe-reference.md neither live nor fixture")
        text = fixture.read_text(encoding="utf-8")
        sha = fixture_sha
        status = None
        fetched_at = "fixture-only"
        url = str(fixture)
        source = "fixture-fallback"

    missing = [f for f in REQUIRED_FIELDS if f"`{f}`" not in text and f"| `{f}`" not in text]
    # Table uses `description`, `instructions`, `title`.
    if "title" not in text.lower() or "description" not in text.lower():
        missing.append("core-schema-table")
    has_retry = "`retry`" in text or "| `retry`" in text or "### Retry" in text
    has_yaml = ".yaml" in text
    has_json = ".json" in text
    if not has_yaml or not has_json:
        raise RuntimeError("recipe docs no longer claim yaml/json formats")
    if missing:
        raise RuntimeError(f"recipe required fields missing from docs: {missing}")

    result = {
        "formats": [".yaml (recommended)", ".json"],
        "required_fields": list(REQUIRED_FIELDS),
        "retry_is_distinct_from_lead_worker": True,
        "retry_field_present": has_retry,
        "retry_note": (
            "Recipe `retry.max_retries` re-runs the same recipe after failed success "
            "checks. That is same-worker retry, not lead/worker model escalation."
        ),
        "docs_rel": RECIPE_REF_REL,
        "source": source,
        "fixture_sha256": fixture_sha,
        "live_sha256": sha,
        "live_matches_fixture": sha == fixture_sha,
        "source_lineage": [
            lineage(url, status, sha, fetched_at, "prose-docs"),
        ],
    }
    session = fetch_body(SESSION_RECIPES_MAIN_RAW)
    if session.get("status") == 200 and session.get("body"):
        stext = session["body"].decode("utf-8")
        if "/recipe" not in stext and "recipe.yaml" not in stext:
            raise RuntimeError("session-recipes.md missing recipe creation surface")
        result["source_lineage"].append(
            lineage(
                SESSION_RECIPES_MAIN_RAW,
                session["status"],
                session["sha256"],
                session["fetched_at"],
                "prose-docs",
            )
        )
    if len(result["source_lineage"]) < 2:
        raise RuntimeError("recipes extract missing second prose rail")
    return result
