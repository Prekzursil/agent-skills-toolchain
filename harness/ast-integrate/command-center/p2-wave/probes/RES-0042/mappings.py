"""Declared MCP fleet and pinned upstream URLs for RES-0042.

The Linux worktree has no ~/.mcp.json. The installed fleet is the unique
mcp__<server>__* names the catalog already grants this program. Each public
URL is a snapshot-dated claim; last-release dates decay on write.
"""
from __future__ import annotations

UNIT = "RES-0042"
OUT_REL = "command-center/research/RES-0042.json"
SCHEMA_REL = "command-center/schema/research-registry.schema.json"
SENTINEL = (
    "SUCCESS:RES-0042 in the receipt AND a per-server row carrying final URL, "
    "HTTP status, last release date and a snapshot timestamp"
)
QUESTION = (
    "For each installed MCP server, when was its upstream last released, is "
    "its repository archived or renamed, does it still resolve, and which "
    "installed servers are effectively abandoned dependencies?"
)
INVALID_URL = "https://res-0042-deliberately-unresolvable.invalid/upstream"
ABANDON_DAYS = 365

# Catalog-declared MCP servers (mcp__<id>__tool). mapping_kind is explicit so
# an in-estate wrapper is not silently treated as a public GitHub repo.
UPSTREAMS: dict[str, dict] = {
    "github": {
        "declared_url": "https://github.com/github/github-mcp-server",
        "mapping_kind": "public-github",
        "mapping_note": "Official GitHub MCP server (local + remote).",
    },
    "context7": {
        "declared_url": "https://github.com/upstash/context7-mcp",
        "mapping_kind": "public-github",
        "mapping_note": (
            "Declared as context7-mcp; a rename/merge onto upstash/context7 "
            "is recorded as a redirect, never followed silently."
        ),
    },
    "deepwiki": {
        "declared_url": "https://docs.devin.ai/work-with-devin/deepwiki-mcp",
        "mapping_kind": "hosted-remote",
        "live_endpoint": "https://mcp.deepwiki.com/mcp",
        "mapping_note": (
            "Cognition hosted DeepWiki MCP; no public git SHA for the service."
        ),
    },
    "brightdata": {
        "declared_url": "https://github.com/brightdata/brightdata-mcp",
        "mapping_kind": "public-github",
        "mapping_note": "Bright Data official MCP server.",
    },
    "basic-memory": {
        "declared_url": "https://github.com/basicmachines-co/basic-memory",
        "mapping_kind": "public-github",
        "mapping_note": "basicmachines-co/basic-memory.",
    },
    "repomix": {
        "declared_url": "https://github.com/yamadashy/repomix",
        "mapping_kind": "public-github",
        "mapping_note": "yamadashy/repomix (pack_remote_repository).",
    },
    "qlty": {
        "declared_url": "https://github.com/qltysh/qlty",
        "mapping_kind": "public-github",
        "mapping_note": "qltysh/qlty.",
    },
    "searxng": {
        "declared_url": "https://github.com/ihor-sokoliuk/mcp-searxng",
        "mapping_kind": "public-github",
        "mapping_note": "Community SearXNG MCP (not SearXNG core).",
    },
    "paper-search": {
        "declared_url": "https://github.com/openags/paper-search-mcp",
        "mapping_kind": "public-github",
        "mapping_note": "openags/paper-search-mcp.",
    },
    "figma": {
        "declared_url": "https://developers.figma.com/docs/figma-mcp-server/",
        "mapping_kind": "hosted-docs",
        "mapping_note": "Official Figma MCP docs surface (hosted, not a git pin).",
    },
    "agent-mail": {
        "declared_url": "https://github.com/Dicklesworthstone/mcp_agent_mail",
        "mapping_kind": "public-github",
        "mapping_note": "mcp_agent_mail; identity is a mapping claim, snapshot-dated.",
    },
    "codex": {
        "declared_url": "https://github.com/openai/codex",
        "mapping_kind": "public-github",
        "mapping_note": (
            "openai/codex CLI ships experimental `codex mcp-server`; not a "
            "standalone MCP package."
        ),
    },
    "search-hub": {
        "declared_url": "https://github.com/firecrawl/firecrawl-mcp-server",
        "mapping_kind": "in-estate-aggregator",
        "mapping_note": (
            "search-hub is an in-estate aggregator (firecrawl/tavily/exa). "
            "The public Firecrawl MCP repo is the primary remote of the "
            "aggregator, not a claim that search-hub IS firecrawl."
        ),
        "components": [
            "https://github.com/firecrawl/firecrawl-mcp-server",
            "https://github.com/tavily-ai/tavily-mcp",
            "https://github.com/exa-labs/exa-mcp-server",
        ],
    },
    "scholarly-access": {
        "declared_url": "UNMAPPED",
        "mapping_kind": "in-estate-no-public-upstream",
        "in_estate_path": "tools/scholarly-access-mcp",
        "mapping_note": (
            "In-estate tools/scholarly-access-mcp on this worktree; README "
            "names no public git upstream. Recorded UNMAPPED, not skipped."
        ),
    },
    "cloud-hub": {
        "declared_url": "UNMAPPED",
        "mapping_kind": "in-estate-no-public-upstream",
        "in_estate_path": "tools/mcp/cloud-hub",
        "mapping_note": (
            "cloud-hub is an in-estate aggregator at tools/mcp/cloud-hub; "
            "no public MCP upstream URL is claimed."
        ),
    },
}

CONFIG_SURFACES = (
    "~/.mcp.json",
    "~/.claude.json",
    "~/.claude/settings.json",
    "~/.cursor/mcp.json",
    ".mcp.json",
    ".cursor/mcp.json",
)

P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0042/probe1_resolve_every_upstream.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0042/probe2_invalid_url_not_skipped.py"
)
