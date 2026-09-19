"""Feature #1 -- ``biomni_run_history``: cross-backend task history."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .store import window_start

if TYPE_CHECKING:  # avoid import cycle at runtime
    from fastmcp import FastMCP

    from .context import HubContext


def _summarize(run: dict[str, Any], artifact_count: int) -> dict[str, Any]:
    prompt = run.get("prompt") or ""
    return {
        "run_id": run["run_id"],
        "backend": run["backend"],
        "status": run.get("status"),
        "prompt": prompt[:160] + ("..." if len(prompt) > 160 else ""),
        "project_id": run.get("project_id"),
        "session_id": run.get("session_id"),
        "task_id": run.get("task_id"),
        "model": run.get("model"),
        "created_at": run.get("created_at"),
        "duration_s": run.get("duration_s"),
        "cost_usd": round(
            (run.get("cost_usd") or 0.0) + (run.get("compute_usd") or 0.0), 6
        ),
        "artifacts": artifact_count,
    }


def register(mcp: FastMCP, ctx: HubContext) -> None:
    @mcp.tool()
    async def biomni_run_history(
        backend: str | None = None,
        status: str | None = None,
        project_id: str | None = None,
        since: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """List past Biomni tasks (across all backends) from the hub ledger.

        Args:
            backend: filter to one backend (``online``/``databricks``); omit for all.
            status: filter by status (``pending``/``running``/``completed``/``failed``).
            project_id: filter to one Biomni project.
            since: rolling window (``today``/``7d``/``30d``) or omit for all time.
            limit: max rows (1-1000).
        """
        await ctx.store.ensure_schema()
        cutoff = window_start(since) if since else 0.0
        runs = await ctx.store.list_runs(
            backend=backend, status=status, project_id=project_id,
            since=cutoff, limit=limit,
        )
        out: list[dict[str, Any]] = []
        for run in runs:
            n = await ctx.store.count_artifacts(run["run_id"])
            out.append(_summarize(run, n))
        return {
            "runs": out,
            "count": len(out),
            "backends_known": ctx.backends.names(),
            "filter": {"backend": backend, "status": status, "since": since},
        }
