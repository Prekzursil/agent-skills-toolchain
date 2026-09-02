"""Stage inventory, clause mapping, and three-way ToS classification for ADV-0053.

Restricted actions (catalog question): automated access, scraping, rate evasion,
multiple accounts, credential sharing — as those terms restrict them.

Official API use that the provider sells is not 'unauthorized automated access'.
Scraping the provider's own surface, sharing keys, spinning extra accounts to
evade a single-account rule, or retrying 429 with no backoff are restricted.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from clauses import clause

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

BUCKET_BLOCKER = "restricted-and-default-on"
BUCKET_OPTIN = "restricted-and-opt-in-with-documented-warning"
BUCKET_FREE = "unrestricted"

RESTRICTED = frozenset(
    {
        "automated_access",
        "scraping",
        "rate_evasion",
        "multiple_accounts",
        "credential_sharing",
    }
)


def _fanin_stage(slug: str) -> dict[str, Any]:
    rel = f"platform/lib/fanin/{slug}.py"
    path = REPO / rel
    return {
        "id": f"fanin.{slug.replace('_', '-')}",
        "kind": "fanin-reducer",
        "path": rel,
        "present": path.is_file(),
        "provider": None,
        "declared_tools": [],
        "intended_access": "none-local-reducer",
        "origin": "live-tree",
    }


def search_hub_paths() -> dict[str, Path]:
    hub = REPO / "tools" / "mcp" / "search-hub"
    return {
        "hub": hub / "hub.py",
        "providers": hub / "providers.py",
        "rotation": hub / "rotation.py",
        "readme": hub / "README.md",
    }


def search_hub_rate_policy() -> dict[str, Any]:
    """Static read of search-hub's 429 policy (not a documented-default claim)."""
    paths = search_hub_paths()
    rot = paths["rotation"]
    text = rot.read_text(encoding="utf-8") if rot.is_file() else ""
    return {
        "path": "tools/mcp/search-hub/rotation.py",
        "present": rot.is_file(),
        "does_not_cool_on_429": "A 429 rate-limit does NOT cool the key" in text,
        "records_429_without_cooling": "Record a 429 WITHOUT cooling" in text,
        "official_stdio_front": (paths["providers"]).is_file(),
    }


def catalog_declared_mcp() -> list[dict[str, Any]]:
    """Stages the catalog names as provider-touching MCP tools.

    On this worktree search-hub lives at tools/mcp/search-hub and fronts the
    official Exa/Tavily/Firecrawl/SearXNG stdio servers. Presence of that tree
    is not default-on: Probe 2 measures whether a fresh HOME activates it.
    """
    rows = [
        {
            "id": "mcp.search-hub.tavily-search",
            "provider": "tavily",
            "declared_tools": ["mcp__search-hub__tavily_search"],
            "intended_access": "official-api",
            "clauses_if_official_api": ["tavily-key-share", "tavily-load", "tavily-multi-account"],
            "clauses_if_naive": ["tavily-scrape-services"],
        },
        {
            "id": "mcp.search-hub.web-search-exa",
            "provider": "exa",
            "declared_tools": ["mcp__search-hub__web_search_exa"],
            "intended_access": "official-api",
            "clauses_if_official_api": ["exa-account"],
            "clauses_if_naive": ["exa-scrape-services", "exa-bots"],
        },
        {
            "id": "mcp.search-hub.firecrawl-scrape",
            "provider": "firecrawl",
            "declared_tools": ["mcp__search-hub__firecrawl_scrape"],
            "intended_access": "official-api",
            "clauses_if_official_api": ["firecrawl-account", "firecrawl-unlawful"],
            "clauses_if_naive": ["firecrawl-account"],
        },
        {
            "id": "mcp.search-hub.firecrawl-crawl",
            "provider": "firecrawl",
            "declared_tools": ["mcp__search-hub__firecrawl_crawl"],
            "intended_access": "official-api",
            "clauses_if_official_api": ["firecrawl-account", "firecrawl-unlawful"],
            "clauses_if_naive": ["firecrawl-account"],
        },
        {
            "id": "mcp.search-hub.firecrawl-map",
            "provider": "firecrawl",
            "declared_tools": ["mcp__search-hub__firecrawl_map"],
            "intended_access": "official-api",
            "clauses_if_official_api": ["firecrawl-account", "firecrawl-unlawful"],
            "clauses_if_naive": ["firecrawl-account"],
        },
        {
            "id": "mcp.searxng.web-search",
            "provider": "searxng",
            "declared_tools": ["mcp__searxng__searxng_web_search"],
            "intended_access": "self-hosted-or-instance",
            "clauses_if_official_api": [],
            "clauses_if_naive": ["exa-scrape-services"],
        },
    ]
    hub = search_hub_paths()["hub"]
    hub_present = hub.is_file()
    out = []
    for row in rows:
        item = dict(row)
        item["kind"] = "catalog-declared-mcp"
        item["path"] = "tools/mcp/search-hub/hub.py"
        item["present"] = hub_present
        item["origin"] = "catalog-declared"
        out.append(item)
    return out


def planted_stages() -> list[dict[str, Any]]:
    return [
        {
            "id": "planted.restricted-default-on",
            "kind": "fixture",
            "path": "command-center/p2-wave/probes/ADV-0053/fixtures/planted_default_on.json",
            "present": True,
            "provider": "exa",
            "declared_tools": ["firecrawl_scrape", "web_search_exa"],
            "intended_access": "scrape-provider-surface",
            "origin": "planted-control",
            "credential_mode": "shared-plaintext-team-key",
            "retry_on_429": "immediate-no-backoff",
            "opt_in_required": False,
            "documented_warning": None,
            "enabled_in_fixture": True,
        },
        {
            "id": "planted.restricted-opt-in-warned",
            "kind": "fixture",
            "path": "command-center/p2-wave/probes/ADV-0053/fixtures/planted_opt_in_warned.json",
            "present": True,
            "provider": "anthropic",
            "declared_tools": ["confirm"],
            "intended_access": "consumer-automated-without-api-key",
            "origin": "planted-control",
            "credential_mode": "per-user-oauth",
            "retry_on_429": "exponential-backoff",
            "opt_in_required": True,
            "documented_warning": (
                "Anthropic Consumer Terms prohibit automated or non-human "
                "access except via an Anthropic API Key."
            ),
            "enabled_in_fixture": False,
        },
    ]


def live_tree_stages() -> list[dict[str, Any]]:
    stages = [
        _fanin_stage("local_runner"),
        _fanin_stage("cloud_dispatcher"),
        _fanin_stage("monitor"),
        _fanin_stage("harvester"),
        _fanin_stage("workflow_fanin"),
        _fanin_stage("cross_vendor_adapter"),
        _fanin_stage("final_synthesis"),
        {
            "id": "marketplace.installer",
            "kind": "local-install",
            "path": "tools/marketplace/installer.py",
            "present": (REPO / "tools/marketplace/installer.py").is_file(),
            "provider": None,
            "declared_tools": [],
            "intended_access": "none-local-copy",
            "origin": "live-tree",
        },
        {
            "id": "cnf.vendor-adapter.anthropic",
            "kind": "local-oracle",
            "path": "command-center/p2-wave/probes/CNF-0156/confirm.py",
            "present": (REPO / "command-center/p2-wave/probes/CNF-0156/confirm.py").is_file(),
            "provider": "anthropic",
            "declared_tools": [],
            "intended_access": "none-local-hash-oracle",
            "origin": "live-tree",
        },
        {
            "id": "cnf.vendor-adapter.openai",
            "kind": "local-oracle",
            "path": "command-center/p2-wave/probes/CNF-0156/confirm.py",
            "present": (REPO / "command-center/p2-wave/probes/CNF-0156/confirm.py").is_file(),
            "provider": "openai",
            "declared_tools": [],
            "intended_access": "none-local-stat-oracle",
            "origin": "live-tree",
        },
        {
            "id": "blueprint.customer-council.compose",
            "kind": "pure-compute",
            "path": "tools/blueprints/product/customer_council/workflow.json",
            "present": (
                REPO / "tools/blueprints/product/customer_council/workflow.json"
            ).is_file(),
            "provider": None,
            "declared_tools": [],
            "intended_access": "none-pure-compute",
            "origin": "live-tree",
        },
        {
            "id": "candidates.freshness-scheduler",
            "kind": "scheduler",
            "path": "tools/candidates/freshness.py",
            "present": (REPO / "tools/candidates/freshness.py").is_file(),
            "provider": None,
            "declared_tools": [],
            "intended_access": "none-network-forbidden",
            "origin": "live-tree",
        },
    ]
    return stages


def enumerate_stages() -> list[dict[str, Any]]:
    return live_tree_stages() + catalog_declared_mcp() + planted_stages()


def restricted_actions_for(stage: dict[str, Any]) -> list[str]:
    """Which restricted actions this stage actually performs (not 'could')."""
    access = stage.get("intended_access")
    origin = stage.get("origin")
    if origin == "planted-control" and stage["id"] == "planted.restricted-default-on":
        return ["scraping", "rate_evasion", "credential_sharing"]
    if origin == "planted-control" and stage["id"] == "planted.restricted-opt-in-warned":
        return ["automated_access"]
    if access in {
        "none-local-reducer",
        "none-local-copy",
        "none-local-hash-oracle",
        "none-local-stat-oracle",
        "none-pure-compute",
        "none-network-forbidden",
    }:
        return []
    if access == "official-api":
        # Official API is the permitted automated path. The stage does not
        # itself scrape the provider, share keys, or evade rate limits.
        return []
    if access == "self-hosted-or-instance":
        return []
    return []


def clauses_for(stage: dict[str, Any]) -> list[dict[str, Any]]:
    access = stage.get("intended_access")
    origin = stage.get("origin")
    ids: list[str] = []
    if origin == "planted-control" and stage["id"] == "planted.restricted-default-on":
        ids = ["exa-scrape-services", "openai-rate-evasion", "tavily-key-share"]
    elif origin == "planted-control" and stage["id"] == "planted.restricted-opt-in-warned":
        ids = ["anthropic-automated", "anthropic-credentials"]
    elif access == "official-api":
        ids = list(stage.get("clauses_if_official_api") or [])
    elif access == "self-hosted-or-instance":
        ids = []
    elif stage.get("provider") == "anthropic" and access == "none-local-hash-oracle":
        ids = ["anthropic-automated"]
    elif stage.get("provider") == "openai" and access == "none-local-stat-oracle":
        ids = ["openai-extract", "openai-rate-evasion"]
    return [clause(i) for i in ids]


def classify_stage(stage: dict[str, Any], default_on: bool) -> dict[str, Any]:
    actions = restricted_actions_for(stage)
    warning = stage.get("documented_warning")
    opt_in = bool(stage.get("opt_in_required"))
    restricted = bool(actions)
    if restricted and default_on:
        bucket = BUCKET_BLOCKER
        release_blocker = True
    elif restricted and (opt_in or not default_on) and warning:
        bucket = BUCKET_OPTIN
        release_blocker = False
    else:
        bucket = BUCKET_FREE
        release_blocker = False
    mapping = clauses_for(stage)
    claim_default_on_restricted = restricted and default_on
    if stage.get("origin") == "planted-control" and claim_default_on_restricted:
        verdict = "CONFIRMED"
    elif restricted and not default_on and warning:
        verdict = "CONFIRMED"
    elif not restricted:
        verdict = "CONFIRMED"
    else:
        verdict = "PARTIAL"
    return {
        "id": stage["id"],
        "kind": stage.get("kind"),
        "path": stage.get("path"),
        "present": bool(stage.get("present")),
        "origin": stage.get("origin"),
        "provider": stage.get("provider"),
        "intended_access": stage.get("intended_access"),
        "restricted_actions": actions,
        "default_on": default_on,
        "opt_in_required": opt_in,
        "documented_warning": warning,
        "bucket": bucket,
        "release_blocker": release_blocker,
        "verdict": verdict,
        "clauses": mapping,
    }


def buckets_from(classified: list[dict[str, Any]]) -> dict[str, list[str]]:
    out = {
        BUCKET_BLOCKER: [],
        BUCKET_OPTIN: [],
        BUCKET_FREE: [],
    }
    for row in classified:
        out[row["bucket"]].append(row["id"])
    return out


def load_planted(name: str) -> dict[str, Any]:
    path = HERE / "fixtures" / name
    return json.loads(path.read_text(encoding="utf-8"))
