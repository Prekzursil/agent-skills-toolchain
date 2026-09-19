"""Feature #5 -- ``biomni_inject_mcp``: register a fleet MCP into self-host Biomni.

Biomni OSS exposes ``A1.add_mcp(config)`` so the agent can *consume* other MCP
servers as extra tools. This tool resolves a short fleet name (or an explicit
spec) to an MCP launch config and hands it to the backend adapter's
``add_mcp``. The injection is persisted in the hub store so the hub can *replay*
it after an ephemeral databricks cluster restart (see WIRING below).

WIRING (self-host warm-up replay):
  1. ``biomni_inject_mcp("chembl", backend="databricks")`` resolves a spec and
     calls ``databricks_adapter.add_mcp(spec)``, which appends the server to the
     ``A1`` agent's MCP config (``add_mcp`` on the live in-process A1 object held
     by the Command/Context API session).
  2. The spec is written to ``injected_mcps`` (backend, ref, spec_json).
  3. On the next cluster cold-start, the hub calls
     ``store.list_injections(backend)`` and re-invokes ``add_mcp`` for each so
     the warm A1 object regains the fleet tools -- injections survive the
     ephemeral cluster. ``biomni_inject_mcp(..., persist=False)`` opts out.

The online managed Lab does not accept external MCP injection, so this tool
returns ``unsupported`` for that backend. FAILS CLOSED.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from .backend import CAP_ADD_MCP, BackendUnsupported

if TYPE_CHECKING:
    from fastmcp import FastMCP

    from .context import HubContext

# Known fleet MCPs -> launch spec. stdio unless a URL is given. These mirror the
# user's cloud-hub / claude.ai fleet and are the ones Biomni benefits from most.
FLEET_REGISTRY: dict[str, dict[str, Any]] = {
    "chembl": {
        "name": "chembl", "transport": "stdio",
        "command": "uvx", "args": ["chembl-mcp-server"],
        "description": "ChEMBL bioactivity / compound / target / ADMET",
    },
    "open_targets": {
        "name": "open_targets", "transport": "stdio",
        "command": "uvx", "args": ["open-targets-mcp-server"],
        "description": "Open Targets genetics / disease-target association GraphQL",
    },
    "paper-search": {
        "name": "paper-search", "transport": "stdio",
        "command": "uvx", "args": ["paper-search-mcp"],
        "description": "Multi-source literature search (PubMed/arXiv/bioRxiv/...)",
    },
    "rdkit": {
        "name": "rdkit", "transport": "stdio",
        "command": "uvx", "args": ["rdkit-mcp-server"],
        "description": "RDKit cheminformatics (descriptors/fingerprints/similarity)",
    },
    "scholarly-access": {
        "name": "scholarly-access", "transport": "stdio",
        "command": "uvx", "args": ["scholarly-access-mcp"],
        "description": "Lawful OA paper resolve / metadata / citation graph",
    },
}


def _build_spec(
    mcp_ref: str,
    *,
    command: str | None,
    args: list[str] | None,
    env: dict[str, str] | None,
    url: str | None,
    transport: str,
) -> dict[str, Any]:
    """Resolve a fleet name from the registry, or assemble an explicit spec."""
    if url or command:
        spec: dict[str, Any] = {"name": mcp_ref, "transport": transport}
        if url:
            spec["url"] = url
            spec["transport"] = transport if transport != "stdio" else "sse"
        if command:
            spec["command"] = command
            spec["args"] = args or []
        if env:
            spec["env"] = env
        return spec
    known = FLEET_REGISTRY.get(mcp_ref)
    if known is None:
        raise KeyError(mcp_ref)
    spec = dict(known)
    if env:
        spec["env"] = {**spec.get("env", {}), **env}
    if args:
        spec["args"] = args
    return spec


def register(mcp: FastMCP, ctx: HubContext) -> None:
    @mcp.tool()
    async def biomni_inject_mcp(
        mcp_ref: str,
        backend: str | None = None,
        command: str | None = None,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        url: str | None = None,
        transport: str = "stdio",
        persist: bool = True,
    ) -> dict[str, Any]:
        """Inject another fleet MCP into a self-hosted Biomni agent.

        Args:
            mcp_ref: a known fleet name (``chembl``, ``open_targets``,
                ``paper-search``, ``rdkit``, ``scholarly-access``) or a logical
                id when supplying an explicit ``command``/``url``.
            backend: target backend; must support ``add_mcp`` (self-host only).
            command/args/env: explicit stdio launch (overrides the registry).
            url/transport: explicit http/sse endpoint instead of stdio.
            persist: record the injection for cluster-restart replay.

        Returns ``injected`` | ``unsupported`` | ``unknown_ref`` | ``error``.
        """
        await ctx.store.ensure_schema()
        client = ctx.backends.resolve(backend)
        if CAP_ADD_MCP not in client.capabilities():
            return {
                "status": "unsupported",
                "backend": client.name,
                "reason": (
                    "This backend cannot consume external MCPs. The online Biomni "
                    "Lab is managed; use a self-hosted backend (databricks/oss)."
                ),
                "available_fleet": sorted(FLEET_REGISTRY),
            }
        try:
            spec = _build_spec(
                mcp_ref, command=command, args=args, env=env, url=url,
                transport=transport,
            )
        except KeyError:
            return {
                "status": "unknown_ref",
                "mcp_ref": mcp_ref,
                "available_fleet": sorted(FLEET_REGISTRY),
                "hint": "pass an explicit command/args or url for a custom MCP",
            }
        try:
            res = await client.add_mcp(spec)
        except BackendUnsupported as exc:
            return {"status": "unsupported", "backend": client.name, "reason": str(exc)}
        except Exception as exc:  # noqa: BLE001 (surface, never crash the hub)
            return {"status": "error", "backend": client.name, "error": str(exc)}

        if persist:
            await ctx.store.record_injection(
                client.name, mcp_ref, json.dumps(spec), status="active"
            )
        return {
            "status": "injected",
            "backend": client.name,
            "mcp_ref": mcp_ref,
            "spec": spec,
            "persisted": persist,
            "backend_result": res,
        }
