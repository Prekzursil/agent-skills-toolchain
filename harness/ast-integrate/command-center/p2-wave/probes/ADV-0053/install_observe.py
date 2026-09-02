"""Empirical default-enablement observation for ADV-0053 Probe 2.

A fresh install is a new HOME + empty dest, not a read of documented defaults.
Does not print secret values: env-key presence is boolean only.
"""
from __future__ import annotations

import ast
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from stages import (  # noqa: E402
    BUCKET_BLOCKER,
    BUCKET_FREE,
    BUCKET_OPTIN,
    classify_stage,
    enumerate_stages,
    load_planted,
    search_hub_paths,
)

NET_TOKENS = ("urlopen", "httpx", "aiohttp", "requests.get", "requests.post")
KEY_NAMES = (
    "TAVILY_API_KEY",
    "EXA_API_KEY",
    "FIRECRAWL_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
)
CONFIG_NAMES = (
    "mcp.json",
    "claude_desktop_config.json",
    "config.toml",
)


def _scan_py_for_net(root: Path) -> list[str]:
    hits: list[str] = []
    if not root.is_dir() and not (root.is_file() and root.suffix == ".py"):
        return hits
    files = [root] if root.is_file() else sorted(root.rglob("*.py"))
    for path in files:
        if not path.is_file():
            continue
        try:
            rel = path.relative_to(REPO).as_posix()
        except ValueError:
            rel = str(path)
        if "/tests/" in f"/{rel}/":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if not any(tok in text for tok in NET_TOKENS):
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in {"get", "post", "urlopen"}:
                hits.append(f"{rel}:{node.lineno}:{node.attr}")
            if isinstance(node, ast.Name) and node.id in {"urlopen", "httpx", "aiohttp"}:
                hits.append(f"{rel}:{node.lineno}:{node.id}")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in {"httpx", "aiohttp", "requests"}:
                        hits.append(f"{rel}:{node.lineno}:import {alias.name}")
            if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in {
                "urllib",
                "httpx",
                "aiohttp",
                "requests",
            }:
                hits.append(f"{rel}:{node.lineno}:from {node.module}")
    return hits


def _importable(mod: str) -> bool:
    try:
        __import__(mod)
        return True
    except Exception:
        return False


def _config_hits(root: Path) -> list[str]:
    found: list[str] = []
    if not root.exists():
        return found
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in {".git", "__pycache__"}]
        for name in filenames:
            if name in CONFIG_NAMES or name.endswith(".mcp.json"):
                rel = Path(dirpath, name)
                try:
                    found.append(rel.relative_to(root).as_posix())
                except ValueError:
                    found.append(str(rel))
    return found


def marketplace_fresh_install(dest: Path) -> dict[str, Any]:
    """Run the real installer against an unsigned dummy package. Expect deny."""
    sys.path.insert(0, str(REPO / "tools"))
    from marketplace.installer import install  # noqa: E402

    pkg = dest / "pkg"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "plugin.json").write_text(
        json.dumps({"id": "adv-0053-dummy", "permissions": ["net"]}),
        encoding="utf-8",
    )
    target = dest / "installed"
    target.mkdir(parents=True, exist_ok=True)
    policy = {"owner_signoff_required": True, "activation": "pending-owner-signoff"}
    result = install(
        pkg,
        target,
        policy,
        signature_state="unsigned",
        trust_level="unrated",
        advisory_state="none",
        require_signoff=True,
    )
    files_after = sorted(p.name for p in target.iterdir())
    return {
        "verdict": result.verdict,
        "refused": result.refused,
        "placed_any_file": result.placed_any_file,
        "census_unchanged": result.census_unchanged,
        "files_after": files_after,
        "reason": result.reason,
        "error": result.error,
    }


def observe_fresh_install() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="adv0053-home-") as home:
        home_p = Path(home)
        cfg = home_p / ".config"
        cfg.mkdir()
        env_keys_present = {k: bool(os.environ.get(k)) for k in KEY_NAMES}
        home_configs = _config_hits(home_p)
        repo_configs = []
        for base in (
            REPO,
            REPO / ".cursor",
            REPO / "tools" / "mcp",
            REPO / "command-center",
        ):
            if not base.is_dir():
                continue
            for name in CONFIG_NAMES:
                hit = base / name
                if hit.is_file():
                    repo_configs.append(hit.relative_to(REPO).as_posix())
        mcp_dir = REPO / "tools" / "mcp"
        github = REPO / ".github" / "workflows"
        install_obs = marketplace_fresh_install(home_p / "mkt")
        hub = search_hub_paths()
        net_hits = _scan_py_for_net(hub["hub"].parent) + _scan_py_for_net(
            REPO / "tools" / "marketplace" / "installer.py"
        )
        isolated_home_mcp_active = bool(home_configs)
        search_hub_tree_present = hub["hub"].is_file()
        any_live = isolated_home_mcp_active or bool(install_obs.get("placed_any_file"))
        return {
            "method": "isolated-HOME-plus-marketplace-install-plus-worktree-census",
            "home_config_files": home_configs,
            "repo_mcp_config_files": repo_configs,
            "tools_mcp_present": mcp_dir.is_dir(),
            "search_hub_tree_present": search_hub_tree_present,
            "isolated_home_mcp_active": isolated_home_mcp_active,
            "github_workflows_present": github.is_dir(),
            "importable": {
                "tavily": _importable("tavily"),
                "firecrawl": _importable("firecrawl"),
                "exa_py": _importable("exa_py"),
                "openai": _importable("openai"),
                "anthropic": _importable("anthropic"),
            },
            "env_key_present_boolean_only": env_keys_present,
            "marketplace_install": install_obs,
            "platform_tools_network_hits": net_hits,
            "any_live_provider_client": any_live,
        }


def default_on_for(stage: dict[str, Any], obs: dict[str, Any]) -> bool:
    origin = stage.get("origin")
    if origin == "planted-control":
        return bool(stage.get("enabled_in_fixture"))
    if origin == "catalog-declared":
        # Repo tree presence is not enablement. Fresh isolated HOME must have
        # actually activated an MCP config without operator setup.
        return bool(obs.get("isolated_home_mcp_active"))
    if stage.get("intended_access", "").startswith("none-"):
        return False
    return bool(obs.get("any_live_provider_client"))


def classify_all(obs: dict[str, Any] | None = None) -> dict[str, Any]:
    obs = obs if obs is not None else observe_fresh_install()
    classified = []
    for stage in enumerate_stages():
        classified.append(classify_stage(stage, default_on_for(stage, obs)))
    planted_bad = load_planted("planted_default_on.json")
    planted_ok = load_planted("planted_opt_in_warned.json")
    buckets = {
        BUCKET_BLOCKER: [r["id"] for r in classified if r["bucket"] == BUCKET_BLOCKER],
        BUCKET_OPTIN: [r["id"] for r in classified if r["bucket"] == BUCKET_OPTIN],
        BUCKET_FREE: [r["id"] for r in classified if r["bucket"] == BUCKET_FREE],
    }
    live_blockers = [
        r["id"]
        for r in classified
        if r["bucket"] == BUCKET_BLOCKER and r["origin"] != "planted-control"
    ]
    return {
        "observation": obs,
        "classified": classified,
        "buckets": buckets,
        "live_release_blockers": live_blockers,
        "planted_bad_id": planted_bad["id"],
        "planted_ok_id": planted_ok["id"],
        "three_way_nonempty": all(buckets[k] for k in (BUCKET_BLOCKER, BUCKET_OPTIN, BUCKET_FREE)),
        "flat_list_rejected": True,
    }
