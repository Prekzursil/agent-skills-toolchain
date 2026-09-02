"""One-click unreviewed marketplace install + review-field detector control."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

REVIEW_RE = re.compile(r"review|sign|sbom|approv|attest|hash.?pin|provenance", re.I)

SCHEMA_REL = "command-center/p2-wave/probes/ARC-0010/registry.schema.json"
REGISTRY_REL = "command-center/p2-wave/probes/ARC-0010/registry.json"
GENERATOR_DIR_REL = "command-center/p2-wave/probes/ARC-0010"
FIXTURE_REVIEW_REL = (
    "command-center/p2-wave/probes/ARC-0055/fixtures/schema-with-review.json"
)


def _keys_in(obj: Any, acc: set[str] | None = None) -> set[str]:
    found = acc if acc is not None else set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            found.add(str(k))
            _keys_in(v, found)
    elif isinstance(obj, list):
        for item in obj:
            _keys_in(item, found)
    return found


def review_like_keys(obj: Any) -> list[str]:
    return sorted(k for k in _keys_in(obj) if REVIEW_RE.search(k))


def load_marketplace_entry_def(schema: dict[str, Any]) -> dict[str, Any]:
    defs = schema.get("definitions") or {}
    entry = defs.get("marketplace_entry")
    if not isinstance(entry, dict):
        raise ValueError("marketplace_entry-definition-missing")
    return entry


def measure_schema(repo: Path) -> dict[str, Any]:
    live_path = repo / SCHEMA_REL
    live = json.loads(live_path.read_text(encoding="utf-8"))
    entry = load_marketplace_entry_def(live)
    props = entry.get("properties") or {}
    live_review = review_like_keys(entry)
    live_prop_names = sorted(str(k) for k in props)
    fixture_path = repo / FIXTURE_REVIEW_REL
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    fixture_review = review_like_keys(fixture)
    return {
        "computed_not_asserted": True,
        "live_schema": SCHEMA_REL,
        "live_marketplace_property_names": live_prop_names,
        "live_review_like_keys": live_review,
        "live_review_like_count": len(live_review),
        "additionalProperties": entry.get("additionalProperties"),
        "fixture_schema": FIXTURE_REVIEW_REL,
        "fixture_review_like_keys": fixture_review,
        "fixture_review_like_count": len(fixture_review),
        "detector_fires_on_known_review_field": len(fixture_review) >= 1,
        "detector_silent_on_live": len(live_review) == 0,
    }


def one_click_install(repo: Path) -> dict[str, Any]:
    """Install the live registry into a scratch tree with zero review prompts."""
    gen_dir = repo / GENERATOR_DIR_REL
    sys.path.insert(0, str(gen_dir))
    import generator as G  # noqa: E402

    registry = json.loads((repo / REGISTRY_REL).read_text(encoding="utf-8"))
    files = G.generate(registry)
    root = repo / "command-center/p2-wave/probes/ARC-0055/fixtures/one-click-install"
    G.write_tree(files, root)
    written = sorted(files)
    prompts = 0  # generate() has no owner-prompt call site
    return {
        "computed_not_asserted": True,
        "method": (
            "Call ARC-0010 generate() then write_tree() into an ARC-0055 scratch "
            "dir. No review_status field is consulted because the live schema "
            "has none (additionalProperties false). Prompt count is the number "
            "of owner-approval call sites invoked; generate() invokes zero."
        ),
        "registry": REGISTRY_REL,
        "scratch_root": "command-center/p2-wave/probes/ARC-0055/fixtures/one-click-install",
        "files_written": written,
        "files_written_count": len(written),
        "owner_prompts_invoked": prompts,
        "unreviewed": True,
        "marketplace_listing": "marketplace/marketplace.harness.json",
        "marketplace_listing_present": "marketplace/marketplace.harness.json" in files,
        "hook_enabled_installed": any(p.startswith("hooks/") for p in written),
    }
