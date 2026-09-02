"""Planted census pair: NUL, path>260, live-only, repo-only, shared."""
from __future__ import annotations

from pathlib import Path

from deploy_map import ENTRIES


def long_rel() -> str:
    # Each component stays under typical 255-byte NAME_MAX; joined rel > 260.
    parts = [f"longseg-{'x' * 40}" for _ in range(6)]
    parts.append("deep.md")
    rel = "/".join(parts)
    if len(rel) <= 260:
        raise RuntimeError(f"long_rel too short: {len(rel)}")
    return rel


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8", newline="\n")


def build_census_fixture(root: Path) -> dict:
    """Identity-mapped pair: repo/<kind> <-> live_home/.claude/<kind>."""
    repo = root / "repo"
    live_home = root / "live_home"
    claude_agents = live_home / ".claude" / "agents"

    _write(repo / "agents" / "shared.md", "# shared\nboth sides\n")
    _write(claude_agents / "shared.md", "# shared\nboth sides\n")
    _write(repo / "agents" / "never-deployed.md", "# repo only\nnever deployed\n")
    _write(claude_agents / "orphan-live.md", "# live only\narchitecturally orphaned\n")
    _write(claude_agents / "NUL", "reserved-name plant AUD-0017\n")
    _write(claude_agents / long_rel(), "path-length plant AUD-0017\n")

    # Empty kind dirs still exist on one side so the map is exercised.
    (repo / "commands").mkdir(parents=True, exist_ok=True)
    (live_home / ".claude" / "commands").mkdir(parents=True, exist_ok=True)

    return {
        "repo": str(repo),
        "live_home": str(live_home),
        "planted": {
            "shared": "agents/shared.md",
            "repo_only": "agents/never-deployed.md",
            "live_only": "agents/orphan-live.md",
            "nul": "agents/NUL",
            "long_rel": "agents/" + long_rel(),
            "long_rel_len": len("agents/" + long_rel()),
        },
        "kinds_in_map": [e["kind"] for e in ENTRIES],
    }
