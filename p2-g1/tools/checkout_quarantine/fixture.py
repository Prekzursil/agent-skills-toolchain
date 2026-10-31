"""Plant clean vs hostile checkouts carrying auto-load agent config."""
from __future__ import annotations

from pathlib import Path

from checkout_quarantine.surfaces import EXPECTED


def plant_clean_checkout(root: str | Path) -> Path:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text("clean\n", encoding="utf-8")
    return root


def plant_hostile_checkout(root: str | Path) -> Path:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    (root / ".claude").mkdir(exist_ok=True)
    (root / ".claude" / "settings.json").write_text("{}\n", encoding="utf-8")
    (root / ".codex").mkdir(exist_ok=True)
    (root / ".codex" / "config.toml").write_text("x=1\n", encoding="utf-8")
    (root / ".mcp.json").write_text("{}\n", encoding="utf-8")
    (root / "hooks").mkdir(exist_ok=True)
    (root / "hooks" / "PostToolUse").write_text("echo planted\n", encoding="utf-8")
    return root


__all__ = ["plant_clean_checkout", "plant_hostile_checkout", "EXPECTED"]
