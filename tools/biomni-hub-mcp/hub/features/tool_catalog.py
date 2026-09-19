"""Feature #4 -- ``biomni_tool_catalog``: introspect Biomni's ~150 tools/skills."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .backend import CAP_LIST_SKILLS

if TYPE_CHECKING:
    from fastmcp import FastMCP

    from .context import HubContext


def _normalize(raw: dict[str, Any]) -> dict[str, Any]:
    """Coerce a backend skill record into the hub's flat schema."""
    return {
        "name": raw.get("name") or raw.get("id") or raw.get("tool") or "?",
        "category": raw.get("category") or raw.get("module") or raw.get("group"),
        "description": raw.get("description") or raw.get("summary") or "",
        "enabled": bool(raw.get("enabled", raw.get("status", "enabled") != "disabled")),
        "source": raw.get("source") or raw.get("origin"),
    }


def register(mcp: FastMCP, ctx: HubContext) -> None:
    @mcp.tool()
    async def biomni_tool_catalog(
        backend: str | None = None,
        category: str | None = None,
        query: str | None = None,
        include_disabled: bool = True,
        refresh: bool = False,
        limit: int = 500,
    ) -> dict[str, Any]:
        """List/search Biomni's tool & skill registry for a backend.

        Args:
            backend: which backend to introspect (default resolves from env).
            category: filter to one category/module.
            query: case-insensitive substring match on name/description.
            include_disabled: include skills currently toggled off.
            refresh: force a live ``list_skills`` fetch and re-cache; otherwise
                served from the local cache when present (works offline).
            limit: max rows returned.

        The catalog is cached in the hub store so it is queryable even when a
        self-host cluster is cold.
        """
        await ctx.store.ensure_schema()
        client = ctx.backends.resolve(backend)
        bname = client.name

        cached = await ctx.store.read_catalog(bname, include_disabled=include_disabled)
        if refresh or not cached:
            if CAP_LIST_SKILLS in client.capabilities():
                try:
                    raw = await client.list_skills()
                    norm = [_normalize(r) for r in raw]
                    if norm:
                        await ctx.store.cache_catalog(bname, norm)
                        cached = await ctx.store.read_catalog(
                            bname, include_disabled=include_disabled
                        )
                except Exception as exc:  # noqa: BLE001 (fall back to cache)
                    if not cached:
                        return {
                            "backend": bname, "tools": [], "count": 0,
                            "categories": {}, "error": str(exc),
                        }

        tools = cached
        if category:
            cat_lower = category.lower()
            tools = [
                t for t in tools if (t.get("category") or "").lower() == cat_lower
            ]
        if query:
            q = query.lower()
            tools = [
                t for t in tools
                if q in (t.get("name") or "").lower()
                or q in (t.get("description") or "").lower()
            ]

        categories: dict[str, int] = {}
        for t in tools:
            cat = t.get("category") or "uncategorized"
            categories[cat] = categories.get(cat, 0) + 1

        return {
            "backend": bname,
            "tools": tools[: max(1, int(limit))],
            "count": len(tools),
            "categories": dict(sorted(categories.items())),
            "cached": not refresh,
        }
