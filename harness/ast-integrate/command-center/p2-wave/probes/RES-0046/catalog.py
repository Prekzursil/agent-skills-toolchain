#!/usr/bin/env python3
"""Candidate table and two-rail claims for RES-0046."""
from __future__ import annotations

import json
from pathlib import Path

from rails import capture_map, needle_in, rail_record

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

SENTINEL = (
    "SUCCESS:RES-0046 in the receipt AND a candidate table with a "
    "daemon-liability column and an explicit corroborate-or-refute "
    "verdict on the existing Tier-2 grade"
)
QUESTION = (
    "Which existing MCP gateways or proxies solve per-session server "
    "multiplication and lazy tool activation, what does each cost "
    "operationally (a daemon is a liability with a self-healing tax), "
    "and does any of them beat the client's native deferred-tool mechanism?"
)
TIER2_PRESCRIPTION = "supervisor + degraded-mode fallback first"
BASELINE_ID = "native-deferred-tool"
DAEMON_COL = "daemon_liability"

# Exact substrings that must remain inside the frozen captures.
NEEDLES: dict[str, list[str]] = {
    "gh-api-docker-mcp-gateway": ['"full_name":"docker/mcp-gateway"'],
    "gh-api-ibm-mcp-context-forge": ['"full_name":"IBM/mcp-context-forge"'],
    "gh-api-sparfenyuk-mcp-proxy": ['"full_name":"sparfenyuk/mcp-proxy"'],
    "gh-api-supercorp-supergateway": ['"full_name":"supercorp-ai/supergateway"'],
    "gh-api-mcp-spec-repo": ['"full_name":"modelcontextprotocol/modelcontextprotocol"'],
    "gh-search-mcp-gateway-repos": ['"full_name":"docker/mcp-gateway"'],
    "prose-docker-mcp-gateway-readme": [
        "docker mcp gateway run",
        "service multiple clients if using either `sse` or `streaming` transports",
        "Dynamic Discovery",
    ],
    "prose-docker-mcp-gateway-docs": [
        "The MCP Gateway manages the server's entire lifecycle",
        "if the server isn't already running",
    ],
    "prose-ibm-contextforge-readme": [
        "federates MCP, A2A, and REST/gRPC APIs",
        "Redis-backed federation",
    ],
    "prose-ibm-pr-4074": [
        "Graceful fallback to in-memory cache during Redis outage",
        "circuit breaker pattern (opens after 3 failures, 30s cooldown)",
    ],
    "prose-sparfenyuk-mcp-proxy-readme": [
        "lets you switch between server transports",
        "spawns a local stdio server",
    ],
    "prose-supergateway-readme": ["MCP stdio-based servers"],
    "prose-anthropic-advanced-tool-use": ["defer_loading", "mcp_toolset"],
    "prose-anthropic-tool-search-docs": ["defer_loading: true"],
    "prose-mcp-spec-tools-2025-11-25": ["notifications/tools/list_changed"],
    "prose-mcp-client-best-practices": [
        "Progressive discovery extends beyond individual tools to entire servers",
        "defers injecting them into the model",
    ],
}


def _api(caps: dict, cid: str) -> dict:
    return json.loads((REPO / caps[cid]["path"]).read_text(encoding="utf-8"))


def _pair(caps: dict, api_id: str, prose_id: str) -> list[dict]:
    return [rail_record(caps[api_id]), rail_record(caps[prose_id])]


def verify_needles(caps: dict) -> list[str]:
    missing: list[str] = []
    for cid, needles in NEEDLES.items():
        row = caps.get(cid)
        if row is None:
            missing.append(f"{cid}:absent")
            continue
        if int(row.get("http_status") or 0) != 200:
            missing.append(f"{cid}:http-{row.get('http_status')}")
        for needle in needles:
            if not needle_in(row, needle):
                missing.append(f"{cid}:{needle[:48]}")
    return missing


def search_hits_e3(caps: dict) -> list[dict]:
    """GitHub search hits that are not two-railed in this unit (E3, not measured)."""
    payload = json.loads((REPO / caps["gh-search-mcp-gateway-repos"]["path"]).read_text(encoding="utf-8"))
    measured = {
        "docker/mcp-gateway",
        "IBM/mcp-context-forge",
        "sparfenyuk/mcp-proxy",
        "supercorp-ai/supergateway",
    }
    rows = []
    for item in payload.get("items") or []:
        name = str(item.get("full_name") or "")
        if not name or name in measured:
            continue
        rows.append(
            {
                "full_name": name,
                "stargazers_count": item.get("stargazers_count"),
                "description": item.get("description"),
                "html_url": item.get("html_url"),
                "evidence_grade": "E3",
                "why_not_measured": (
                    "single structured-api hit from the search rail; no independent "
                    "prose capture in this unit, so not cited as measured fact"
                ),
            }
        )
    return rows


def candidate_table(caps: dict) -> list[dict]:
    docker = _api(caps, "gh-api-docker-mcp-gateway")
    ibm = _api(caps, "gh-api-ibm-mcp-context-forge")
    proxy = _api(caps, "gh-api-sparfenyuk-mcp-proxy")
    super_g = _api(caps, "gh-api-supercorp-supergateway")
    spec = _api(caps, "gh-api-mcp-spec-repo")
    return [
        {
            "id": BASELINE_ID,
            "name": "Native deferred-tool / progressive discovery",
            "repo": spec.get("full_name"),
            "is_baseline": True,
            DAEMON_COL: "none-client-local",
            "requires_persistent_daemon": False,
            "when_daemon_dies": (
                "There is no shared gateway daemon. Ending the client session drops "
                "that session's tools only. Other sessions are unaffected."
            ),
            "solves_session_server_multiplication": "partial",
            "solves_session_server_multiplication_note": (
                "MCP client best-practices document connecting a server only when "
                "needed and disconnecting afterwards; this is per-session lazy "
                "connect, not a shared process pool"
            ),
            "solves_lazy_tool_activation": True,
            "beats_native_lazy_activation": False,
            "beats_native_process_axis": False,
            "operational_cost": (
                "no extra daemon; implementation lives in the host/API "
                "(defer_loading / search_tools)"
            ),
            "stars": spec.get("stargazers_count"),
            "evidence_claim_ids": ["C-NATIVE-DEFERRED"],
        },
        {
            "id": "docker-mcp-gateway",
            "name": "Docker MCP Gateway",
            "repo": docker.get("full_name"),
            "is_baseline": False,
            DAEMON_COL: "yes-gateway-process-plus-docker-daemon",
            "requires_persistent_daemon": True,
            "when_daemon_dies": (
                "docker mcp gateway run exiting drops the unified tool surface for "
                "every client attached to that gateway (stdio: one client; sse/"
                "streaming: all attached clients). Lazy-started server containers "
                "lose their supervisor; leftover containers are an orphan-tax, not "
                "a degraded client path."
            ),
            "solves_session_server_multiplication": True,
            "solves_session_server_multiplication_note": (
                "yes on sse/streaming: one gateway can service multiple clients; "
                "servers are started on demand as containers"
            ),
            "solves_lazy_tool_activation": (
                "partial: dynamic discovery from running servers; not equivalent to "
                "defer_loading (schemas of running servers still surface unless the "
                "client also defers)"
            ),
            "beats_native_lazy_activation": False,
            "beats_native_process_axis": False,
            "operational_cost": (
                "self-healing tax: Docker daemon + gateway process + container "
                "lifecycle; Desktop 4.59+ or DOCKER_MCP_IN_CONTAINER bypass"
            ),
            "stars": docker.get("stargazers_count"),
            "evidence_claim_ids": ["C-DOCKER-GATEWAY"],
        },
        {
            "id": "ibm-contextforge",
            "name": "IBM ContextForge MCP Gateway",
            "repo": ibm.get("full_name"),
            "is_baseline": False,
            DAEMON_COL: "yes-http-app-plus-postgres-plus-optional-redis",
            "requires_persistent_daemon": True,
            "when_daemon_dies": (
                "The federated endpoint is gone until the gateway (and its store) "
                "restart. Redis outage is a separate failure: PR 4074 added a "
                "circuit breaker and in-memory cache fallback, which is degraded "
                "mode for cache, not a replacement for the gateway process itself."
            ),
            "solves_session_server_multiplication": True,
            "solves_session_server_multiplication_note": (
                "one HTTP/SSE/stdio wrapper endpoint federates many MCP/A2A/REST "
                "backends; multi-cluster Redis-backed federation is optional"
            ),
            "solves_lazy_tool_activation": (
                "partial: centralized discovery/registry; not client defer_loading"
            ),
            "beats_native_lazy_activation": False,
            "beats_native_process_axis": False,
            "operational_cost": (
                "self-healing tax: app replicas + PostgreSQL + Redis + (often) "
                "Nginx; Redis failure required an explicit degraded fallback"
            ),
            "stars": ibm.get("stargazers_count"),
            "evidence_claim_ids": ["C-CONTEXTFORGE-FEDERATION"],
        },
        {
            "id": "sparfenyuk-mcp-proxy",
            "name": "sparfenyuk/mcp-proxy",
            "repo": proxy.get("full_name"),
            "is_baseline": False,
            DAEMON_COL: "yes-when-listening-on-a-port",
            "requires_persistent_daemon": True,
            "when_daemon_dies": (
                "stdio-to-SSE client mode: that one session's bridge dies. SSE-to-"
                "stdio / named-server mode: the listen port dies and every client "
                "using it loses the spawned stdio child(ren)."
            ),
            "solves_session_server_multiplication": False,
            "solves_session_server_multiplication_note": (
                "transport switch, not a fleet multiplexer. named-server mode can "
                "expose several stdio servers under /servers/<name>/ but still "
                "spawns a stdio child per named server behind one proxy"
            ),
            "solves_lazy_tool_activation": False,
            "beats_native_lazy_activation": False,
            "beats_native_process_axis": False,
            "operational_cost": "one extra process per bridge; no self-heal documented",
            "stars": proxy.get("stargazers_count"),
            "evidence_claim_ids": ["C-TRANSPORT-BRIDGES"],
        },
        {
            "id": "supercorp-supergateway",
            "name": "supercorp-ai/supergateway",
            "repo": super_g.get("full_name"),
            "is_baseline": False,
            DAEMON_COL: "yes-when-listening-on-a-port",
            "requires_persistent_daemon": True,
            "when_daemon_dies": (
                "The stdio-to-SSE/WS/HTTP listener dies; clients lose that one "
                "wrapped server. No multi-server federation."
            ),
            "solves_session_server_multiplication": False,
            "solves_lazy_tool_activation": False,
            "beats_native_lazy_activation": False,
            "beats_native_process_axis": False,
            "operational_cost": "one extra npx/docker process per wrapped server",
            "stars": super_g.get("stargazers_count"),
            "evidence_claim_ids": ["C-TRANSPORT-BRIDGES"],
        },
    ]


def claims(caps: dict) -> list[dict]:
    return [
        {
            "id": "C-NATIVE-DEFERRED",
            "claim": (
                "The native baseline for lazy tool activation is client/API deferred "
                "loading (Anthropic defer_loading / tool-search, MCP progressive "
                "discovery with search_tools) plus list_changed, not a gateway daemon. "
                "The same MCP client guide also describes lazy server connect."
            ),
            "verdict": "CONFIRMED",
            "evidence_grade": "E1",
            "rails": [
                rail_record(caps["gh-api-mcp-spec-repo"]),
                rail_record(caps["prose-mcp-client-best-practices"]),
                rail_record(caps["prose-anthropic-advanced-tool-use"]),
                rail_record(caps["prose-mcp-spec-tools-2025-11-25"]),
            ],
            "strongest_caveat": (
                "Native lazy-server-connect is a host implementation pattern. A client "
                "that ignores the guide and eagerly spawns every stdio server still "
                "pays sessions x servers. That is a client defect, not a reason to "
                "federate gateways first."
            ),
        },
        {
            "id": "C-DOCKER-GATEWAY",
            "claim": (
                "Docker MCP Gateway is a persistent CLI/gateway process that unifies "
                "many containerized MCP servers, can serve multiple clients on sse/"
                "streaming, and lazy-starts a server container when a tool is needed."
            ),
            "verdict": "CONFIRMED",
            "evidence_grade": "E1",
            "rails": _pair(
                caps, "gh-api-docker-mcp-gateway", "prose-docker-mcp-gateway-readme"
            )
            + [rail_record(caps["prose-docker-mcp-gateway-docs"])],
            "strongest_caveat": (
                "Lazy container start is still a daemon-supervised start. Docs do not "
                "show a client-side degraded path when the gateway process is dead."
            ),
        },
        {
            "id": "C-CONTEXTFORGE-FEDERATION",
            "claim": (
                "ContextForge is a persistent registry/proxy that federates MCP/A2A/"
                "REST backends, optionally with Redis-backed multi-cluster federation. "
                "Its own Redis-outage work added circuit-breaker plus in-memory "
                "fallback, which is degraded-mode for a dependency, not proof that "
                "federation should be the first architecture."
            ),
            "verdict": "CONFIRMED",
            "evidence_grade": "E1",
            "rails": _pair(
                caps, "gh-api-ibm-mcp-context-forge", "prose-ibm-contextforge-readme"
            )
            + [rail_record(caps["prose-ibm-pr-4074"])],
            "strongest_caveat": (
                "PR 4074's fallback covers Redis cache hangs, not a dead gateway "
                "replica or a lost Postgres. Multi-node session recovery remains a "
                "separate unfinished class in upstream issues."
            ),
        },
        {
            "id": "C-TRANSPORT-BRIDGES",
            "claim": (
                "mcp-proxy and supergateway are transport bridges (stdio <-> SSE/"
                "Streamable HTTP). They do not implement native deferred-tool "
                "activation. They add a process. named-server mode on mcp-proxy can "
                "front several stdio children but still spawns those children."
            ),
            "verdict": "CONFIRMED",
            "evidence_grade": "E1",
            "rails": [
                rail_record(caps["gh-api-sparfenyuk-mcp-proxy"]),
                rail_record(caps["prose-sparfenyuk-mcp-proxy-readme"]),
                rail_record(caps["gh-api-supercorp-supergateway"]),
                rail_record(caps["prose-supergateway-readme"]),
            ],
            "strongest_caveat": (
                "A transport bridge can be a prerequisite for putting an HTTP gateway "
                "in front of a stdio-only server. That is an adapter cost, not a "
                "lazy-activation win over the native mechanism."
            ),
        },
        {
            "id": "C-TIER2-VERDICT",
            "claim": (
                "The recorded 05-ECO Tier-2 grade on gateway federation "
                f"('{TIER2_PRESCRIPTION}') is CORROBORATED: every multiplexing "
                "candidate is a daemon with a self-healing tax; ContextForge had to "
                "add degraded Redis fallback; native deferred-tool already covers "
                "lazy activation without federation. No two-railed candidate beats "
                "the native mechanism on the lazy-activation axis."
            ),
            "verdict": "CORROBORATE",
            "evidence_grade": "E1",
            "rails": [
                rail_record(caps["prose-ibm-pr-4074"]),
                rail_record(caps["prose-mcp-client-best-practices"]),
                rail_record(caps["prose-docker-mcp-gateway-docs"]),
                rail_record(caps["gh-search-mcp-gateway-repos"]),
            ],
            "strongest_caveat": (
                "RES-0037 (live sessions x servers process count on this box) is "
                "absent. This corroboration is from public prior-art rails, not a "
                "local process-table measurement. A later local count could change "
                "the operational-cost magnitudes, not the daemon-liability polarity."
            ),
        },
    ]


def two_rail_ok(claim: dict) -> bool:
    kinds = {str(r.get("kind")) for r in (claim.get("rails") or [])}
    return "structured-api" in kinds and "prose-source" in kinds


def baseline_is_native(doc: dict) -> bool:
    return str(doc.get("comparison_baseline") or "") == BASELINE_ID


def mutant_doing_nothing(doc: dict) -> dict:
    clone = json.loads(json.dumps(doc))
    clone["comparison_baseline"] = "doing-nothing"
    return clone


def build() -> dict:
    caps = capture_map()
    missing = verify_needles(caps)
    if missing:
        raise RuntimeError(f"capture needles missing: {missing}")
    table = candidate_table(caps)
    if any(DAEMON_COL not in row for row in table):
        raise RuntimeError("daemon_liability column missing")
    built_claims = claims(caps)
    bad = [c["id"] for c in built_claims if not two_rail_ok(c)]
    if bad:
        raise RuntimeError(f"single-rail claims {bad}")
    for claim in built_claims:
        for rail in claim["rails"]:
            if int(rail.get("http_status") or 0) != 200:
                raise RuntimeError(f"non-200 rail {rail.get('id')}")
            if not rail.get("sha256") or not rail.get("permalink"):
                raise RuntimeError(f"incomplete rail {rail.get('id')}")
    return {
        "caps": caps,
        "candidate_table": table,
        "claims": built_claims,
        "search_hits_e3": search_hits_e3(caps),
        "search_total_count": json.loads(
            (REPO / caps["gh-search-mcp-gateway-repos"]["path"]).read_text(encoding="utf-8")
        ).get("total_count"),
    }
