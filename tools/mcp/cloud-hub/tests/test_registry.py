#!/usr/bin/env python3
"""Pure-logic tests for the plan builder: collision detection, name merging,
routing, and degraded-backend handling. No child processes are spawned."""

from __future__ import annotations

import json
import os
import sys

HUB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HUB_DIR)

from backends import BackendSpec, default_backends  # noqa: E402
from registry import build_plan  # noqa: E402


def _spec(bid: str, prefix: str, cache: str) -> BackendSpec:
    return BackendSpec(
        id=bid, label=f"lbl-{bid}", prefix=prefix, cmd=("noop",), cache=cache
    )


def _write_cache(cache_dir: str, fname: str, tools: list[str]) -> None:
    payload = {
        "initialize": {"protocolVersion": "2024-11-05"},
        "tools": {
            "tools": [
                {
                    "name": t,
                    "description": f"desc {t}",
                    "inputSchema": {"type": "object"},
                }
                for t in tools
            ]
        },
    }
    with open(os.path.join(cache_dir, fname), "w", encoding="utf-8") as fh:
        json.dump(payload, fh)


def test_unique_names_keep_original(tmp_path):
    specs = [_spec("a", "aa", "a.json"), _spec("b", "bb", "b.json")]
    _write_cache(str(tmp_path), "a.json", ["only_a", "shared"])
    _write_cache(str(tmp_path), "b.json", ["only_b"])
    plan = build_plan(specs, str(tmp_path))
    names = {t["name"] for t in plan.tools}
    # 'shared' appears in only one backend here -> keeps its original name.
    assert names == {"only_a", "shared", "only_b"}
    assert plan.collisions == {}
    assert plan.routing["only_a"].backend_id == "a"
    assert plan.routing["only_a"].renamed is False


def test_collision_gets_prefixed_both_sides(tmp_path):
    specs = [_spec("a", "aa", "a.json"), _spec("b", "bb", "b.json")]
    _write_cache(str(tmp_path), "a.json", ["shared", "only_a"])
    _write_cache(str(tmp_path), "b.json", ["shared", "only_b"])
    plan = build_plan(specs, str(tmp_path))
    names = {t["name"] for t in plan.tools}
    assert names == {"aa_shared", "only_a", "bb_shared", "only_b"}
    assert plan.collisions == {"shared": ["a", "b"]}
    assert plan.routing["aa_shared"].backend_id == "a"
    assert plan.routing["aa_shared"].original_name == "shared"
    assert plan.routing["aa_shared"].renamed is True
    assert plan.routing["bb_shared"].original_name == "shared"
    assert plan.routing["only_a"].renamed is False


def test_missing_cache_marks_degraded(tmp_path):
    specs = [_spec("a", "aa", "a.json"), _spec("b", "bb", "missing.json")]
    _write_cache(str(tmp_path), "a.json", ["only_a"])
    plan = build_plan(specs, str(tmp_path))
    assert "b" in plan.degraded
    assert "a" not in plan.degraded
    assert {t["name"] for t in plan.tools} == {"only_a"}


def test_real_committed_caches_build_a_clean_plan():
    """Locks the committed surface: 9 backends, no collisions, none degraded."""
    specs = default_backends()
    plan = build_plan(specs, os.path.join(HUB_DIR, "caches"))
    per: dict[str, int] = {}
    for route in plan.routing.values():
        per[route.backend_id] = per.get(route.backend_id, 0) + 1
    # Deterministic backends: the three built wrappers, the single-tool gcloud
    # MCP, the hand-authored azure subset, and the vendored OVH TS server.
    assert per["modal"] == 41 and per["lightning"] == 9
    assert per["gcloud"] == 1 and per["azure"] == 14
    assert per["ovh"] == 27
    # Databricks built FastMCP wrapper (databricks-sdk): full dbx_* surface.
    assert per["databricks"] == 65
    # Live-enumerated adopt backends: present and substantial (re-running
    # `hub.py --refresh` may shift these as upstream packages evolve).
    assert per["runpod"] >= 40 and per["kaggle"] >= 40 and per["rclone"] >= 40
    # Names are preserved verbatim; no cross-backend collision; nothing degraded.
    assert plan.collisions == {} and not plan.degraded
    for name in (
        "modal_run",
        "lightning_machine_types",
        "lightning_studio_switch_machine",
        "lightning_studio_upload_file",
        "run_gcloud_command",
        "list-pods",
        "azmcp_subscription_list",
        "ovh_ssh_exec",
        "ovh_api_raw",
        "dbx_run_on_cluster",
        "dbx_api_raw",
    ):
        assert name in plan.routing and plan.routing[name].renamed is False


def test_backend_specs_ovh_and_kaggle_fix():
    """Locks the OVH backend wiring + the Kaggle seed_env audit fix."""
    specs = {s.id: s for s in default_backends()}
    # OVH backend present, env-mode rotator seeded with the API-key trio.
    assert "ovh" in specs
    ovh = specs["ovh"]
    assert ovh.prefix == "ov" and ovh.account is not None
    assert ovh.account.platform == "ovh" and ovh.account.mode == "env"
    assert ovh.account.seed_env == (
        "OVH_APPLICATION_KEY",
        "OVH_APPLICATION_SECRET",
        "OVH_CONSUMER_KEY",
    )
    # Kaggle seed_env fixed to the real two-var auth (regression guard: was the
    # single, useless KAGGLE_API_TOKEN that matched neither the platform nor the
    # accounts.example bundle).
    assert specs["kaggle"].account.seed_env == ("KAGGLE_USERNAME", "KAGGLE_KEY")
    # Prefixes stay unique across all 9 backends.
    prefixes = [s.prefix for s in specs.values()]
    assert len(prefixes) == len(set(prefixes)) == 9


def test_backend_specs_databricks():
    """Locks the Databricks backend wiring (built databricks-sdk FastMCP wrapper)."""
    specs = {s.id: s for s in default_backends()}
    assert "databricks" in specs
    dbx = specs["databricks"]
    # Prefix `db`; enumerates offline (lazy SDK import) like modal/lightning.
    assert dbx.prefix == "db" and dbx.can_enumerate_offline is True
    assert dbx.cache == "databricks.json"
    # Env-mode rotator seeded with the workspace host + PAT.
    assert dbx.account is not None
    assert dbx.account.platform == "databricks" and dbx.account.mode == "env"
    assert dbx.account.seed_env == ("DATABRICKS_HOST", "DATABRICKS_TOKEN")
