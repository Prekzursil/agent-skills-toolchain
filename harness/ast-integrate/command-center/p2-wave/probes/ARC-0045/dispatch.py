#!/usr/bin/env python3
"""Proposed A7 dispatch wrappers.

Each wrapper is a capability entry. The side effect runs only after
evaluator.require_grant(). This file is the proposed design's choke-crossing
surface; the current tree is not rewritten.
"""
from __future__ import annotations

from typing import Any, Callable, Mapping

from evaluator import require_grant

# Mechanical enumerator looks for this decorator name and for require_grant/evaluate calls.
CAPABILITY_ENTRIES: list[str] = []


def capability_entry(family: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def wrap(fn: Callable[..., Any]) -> Callable[..., Any]:
        CAPABILITY_ENTRIES.append(f"{fn.__module__.split('.')[-1]}.{fn.__name__}:{family}")
        fn.a7_family = family  # type: ignore[attr-defined]
        fn.a7_entry = True  # type: ignore[attr-defined]
        return fn

    return wrap


def _run(invocation: Mapping[str, Any], grants: list[dict[str, str]], side_effect: str) -> dict[str, Any]:
    decision = require_grant(invocation, grants)
    return {"ok": True, "side_effect": side_effect, "decision": decision}


@capability_entry("marketplace.install")
def marketplace_install(invocation: Mapping[str, Any], grants: list[dict[str, str]]) -> dict[str, Any]:
    return _run(invocation, grants, "marketplace.install")


@capability_entry("marketplace.dispatch")
def marketplace_dispatch(invocation: Mapping[str, Any], grants: list[dict[str, str]]) -> dict[str, Any]:
    return _run(invocation, grants, "marketplace.dispatch")


@capability_entry("plugin.activate")
def plugin_activate(invocation: Mapping[str, Any], grants: list[dict[str, str]]) -> dict[str, Any]:
    return _run(invocation, grants, "plugin.activate")


@capability_entry("plugin.mcp_call")
def plugin_mcp_call(invocation: Mapping[str, Any], grants: list[dict[str, str]]) -> dict[str, Any]:
    return _run(invocation, grants, "plugin.mcp_call")


@capability_entry("plugin.register")
def plugin_register(invocation: Mapping[str, Any], grants: list[dict[str, str]]) -> dict[str, Any]:
    return _run(invocation, grants, "plugin.register")


@capability_entry("council.invoke")
def council_invoke(invocation: Mapping[str, Any], grants: list[dict[str, str]]) -> dict[str, Any]:
    return _run(invocation, grants, "council.invoke")


@capability_entry("workflow.execute")
def workflow_execute(invocation: Mapping[str, Any], grants: list[dict[str, str]]) -> dict[str, Any]:
    return _run(invocation, grants, "workflow.execute")


@capability_entry("foundry.scout")
def foundry_scout(invocation: Mapping[str, Any], grants: list[dict[str, str]]) -> dict[str, Any]:
    return _run(invocation, grants, "foundry.scout")


@capability_entry("foundry.forge")
def foundry_forge(invocation: Mapping[str, Any], grants: list[dict[str, str]]) -> dict[str, Any]:
    return _run(invocation, grants, "foundry.forge")


@capability_entry("foundry.tournament")
def foundry_tournament(invocation: Mapping[str, Any], grants: list[dict[str, str]]) -> dict[str, Any]:
    return _run(invocation, grants, "foundry.tournament")


@capability_entry("mcp.cloud_hub")
def mcp_cloud_hub(invocation: Mapping[str, Any], grants: list[dict[str, str]]) -> dict[str, Any]:
    return _run(invocation, grants, "mcp.cloud_hub")


@capability_entry("mcp.search_hub")
def mcp_search_hub(invocation: Mapping[str, Any], grants: list[dict[str, str]]) -> dict[str, Any]:
    return _run(invocation, grants, "mcp.search_hub")


@capability_entry("mcp.social_hub")
def mcp_social_hub(invocation: Mapping[str, Any], grants: list[dict[str, str]]) -> dict[str, Any]:
    return _run(invocation, grants, "mcp.social_hub")


@capability_entry("mcp.http_host")
def mcp_http_host(invocation: Mapping[str, Any], grants: list[dict[str, str]]) -> dict[str, Any]:
    return _run(invocation, grants, "mcp.http_host")


@capability_entry("mcp.apply")
def mcp_apply(invocation: Mapping[str, Any], grants: list[dict[str, str]]) -> dict[str, Any]:
    return _run(invocation, grants, "mcp.apply")


@capability_entry("crcp.dispatch")
def crcp_dispatch(invocation: Mapping[str, Any], grants: list[dict[str, str]]) -> dict[str, Any]:
    return _run(invocation, grants, "crcp.dispatch")


@capability_entry("agentrail.dispatch")
def agentrail_dispatch(invocation: Mapping[str, Any], grants: list[dict[str, str]]) -> dict[str, Any]:
    return _run(invocation, grants, "agentrail.dispatch")


FAMILIES = (
    "marketplace.install",
    "marketplace.dispatch",
    "plugin.activate",
    "plugin.mcp_call",
    "plugin.register",
    "council.invoke",
    "workflow.execute",
    "foundry.scout",
    "foundry.forge",
    "foundry.tournament",
    "mcp.cloud_hub",
    "mcp.search_hub",
    "mcp.social_hub",
    "mcp.http_host",
    "mcp.apply",
    "crcp.dispatch",
    "agentrail.dispatch",
)
