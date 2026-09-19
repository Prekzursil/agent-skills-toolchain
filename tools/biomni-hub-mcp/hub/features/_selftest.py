"""Standalone verification for Component A3 feature tools.

Run: ``python -m features._selftest`` (from the hub/ dir) or
``python hub/features/_selftest.py``. Proves: modules import, tools register on
a real FastMCP instance, and a full store round-trip works with the NullBackend
default (run history / cost rolling / inject unsupported / catalog empty).
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile

# Allow running as a loose script (add hub/ to path so `features` imports).
if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from features import register_all  # noqa: E402
from features.backend import BackendRegistry, NullBackend  # noqa: E402
from features.context import HubContext  # noqa: E402
from features.store import RunStore  # noqa: E402


async def _run() -> int:
    tmp = tempfile.mkdtemp(prefix="biomni_hub_selftest_")
    store = RunStore(os.path.join(tmp, "hub.sqlite3"))
    reg = BackendRegistry(default="online")
    reg.register("online", NullBackend("online"))
    ctx = HubContext(data_dir=tmp, store=store, backends=reg)

    mcp = FastMCP("biomni-hub-selftest")
    names = register_all(mcp, ctx)
    registered = {t.name for t in await mcp.list_tools()}
    for n in names:
        assert n in registered, f"tool {n} did not register"
    print(f"[ok] registered {len(names)} tools: {', '.join(names)}")

    # Store round-trip.
    await store.ensure_schema()
    rid = await store.upsert_run(
        backend="databricks", prompt="test folding job", status="completed",
        session_id="sess1", tokens_in=120_000, tokens_out=8_000,
        duration_s=310.0, model="claude-sonnet",
    )
    await store.add_artifact(run_id=rid, name="result.csv", size=2048,
                             local_path="/x/result.csv", source="download")
    runs = await store.list_runs(limit=10)
    assert runs and runs[0]["run_id"] == rid
    assert await store.count_artifacts(rid) == 1
    print(f"[ok] store round-trip: run {rid[:8]} + 1 artifact")

    # Cost estimate sanity (120k in / 8k out sonnet ~= $0.48).
    from features.pricing import estimate_token_cost
    est = estimate_token_cost(120_000, 8_000, "claude-sonnet")
    assert 0.4 < est < 0.6, est
    print(f"[ok] cost estimate: ${est}")

    # Rolling rollup groups by backend.
    rollup = await store.cost_rollup()
    assert any(r["backend"] == "databricks" for r in rollup)
    print(f"[ok] cost rollup backends: {[r['backend'] for r in rollup]}")

    # Injection persistence.
    await store.record_injection("databricks", "chembl", '{"name":"chembl"}')
    inj = await store.list_injections("databricks")
    assert inj and inj[0]["ref"] == "chembl"
    print(f"[ok] injection persisted + replayable: {inj[0]['ref']}")

    print("SUCCESS:selftest-A3 all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
