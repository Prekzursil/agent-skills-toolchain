"""Feature #3 -- ``biomni_cost``: per-run + rolling cost meter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .backend import CAP_BILLING
from .pricing import estimate_compute_cost, estimate_token_cost, normalize_model
from .store import window_start

if TYPE_CHECKING:
    from fastmcp import FastMCP

    from .context import HubContext


def _run_cost(run: dict[str, Any]) -> dict[str, Any]:
    ti = int(run.get("tokens_in") or 0)
    to = int(run.get("tokens_out") or 0)
    model = run.get("model")
    token_usd = run.get("cost_usd")
    if not token_usd:
        token_usd = estimate_token_cost(ti, to, model)
    compute_usd = run.get("compute_usd")
    if not compute_usd and run.get("duration_s") and run.get("backend") != "online":
        compute_usd = estimate_compute_cost(float(run["duration_s"]))
    compute_usd = compute_usd or 0.0
    return {
        "run_id": run["run_id"],
        "backend": run.get("backend"),
        "model": normalize_model(model),
        "tokens_in": ti,
        "tokens_out": to,
        "duration_s": run.get("duration_s"),
        "token_usd": round(token_usd, 6),
        "compute_usd": round(compute_usd, 6),
        "total_usd": round(token_usd + compute_usd, 6),
        "estimated": not run.get("cost_usd"),
    }


def register(mcp: FastMCP, ctx: HubContext) -> None:
    @mcp.tool()
    async def biomni_cost(
        run_id: str | None = None,
        backend: str | None = None,
        window: str = "all",
        include_balance: bool = True,
    ) -> dict[str, Any]:
        """Report cost for one run, or a rolling meter across runs/backends.

        Args:
            run_id: if set, return the per-run cost breakdown for that run.
            backend: filter the rolling meter to one backend.
            window: rolling window (``all``/``today``/``7d``/``30d``).
            include_balance: also fetch the online backend's live credit balance.

        Token USD is authoritative when recorded on the run, else estimated from
        the pricing table; compute USD is estimated from wall-clock for self-host
        backends. Live balance (when available) is the source of truth.
        """
        await ctx.store.ensure_schema()

        if run_id:
            run = await ctx.store.get_run(run_id)
            if not run:
                return {"scope": "run", "status": "not_found", "run_id": run_id}
            return {"scope": "run", **_run_cost(run)}

        cutoff = window_start(window) if window and window != "all" else 0.0
        rollup = await ctx.store.cost_rollup(backend=backend, since=cutoff)
        by_backend: dict[str, Any] = {}
        total = 0.0
        runs_counted = 0
        for row in rollup:
            token_usd = float(row["cost_usd"])
            compute_usd = float(row["compute_usd"])
            # Backfill estimates where the run rows carried tokens but no cost.
            if token_usd == 0.0 and row["tokens_in"]:
                token_usd = estimate_token_cost(
                    int(row["tokens_in"]), int(row["tokens_out"]), None
                )
            if compute_usd == 0.0 and row["backend"] != "online" and row["duration_s"]:
                compute_usd = estimate_compute_cost(float(row["duration_s"]))
            subtotal = round(token_usd + compute_usd, 6)
            by_backend[row["backend"]] = {
                "runs": int(row["runs"]),
                "tokens_in": int(row["tokens_in"]),
                "tokens_out": int(row["tokens_out"]),
                "token_usd": round(token_usd, 6),
                "compute_usd": round(compute_usd, 6),
                "total_usd": subtotal,
            }
            total += subtotal
            runs_counted += int(row["runs"])

        result: dict[str, Any] = {
            "scope": "rolling",
            "window": window,
            "total_usd": round(total, 6),
            "runs_counted": runs_counted,
            "by_backend": by_backend,
        }

        if include_balance:
            client = ctx.backends.resolve(backend)
            if CAP_BILLING in client.capabilities():
                try:
                    result["balance"] = await client.billing_balance()
                    result["balance_backend"] = client.name
                except Exception as exc:  # noqa: BLE001 (best-effort, never fatal)
                    result["balance_error"] = str(exc)
        return result
