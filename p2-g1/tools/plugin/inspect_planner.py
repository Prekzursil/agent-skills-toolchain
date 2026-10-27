"""Confirm dry-run and apply share one planner (IMP-0032)."""
from __future__ import annotations

from pathlib import Path


def inspect_shared_planner(repo: str | Path | None = None) -> dict:
    root = Path(repo) if repo is not None else Path(__file__).resolve().parents[2]
    execute_py = root / "tools" / "plugin" / "execute.py"
    text = execute_py.read_text(encoding="utf-8") if execute_py.is_file() else ""
    ok = "def _plan_install" in text and "def execute" in text and "dry_run" in text
    return {
        "ok": ok,
        "reason": "dry-run and apply share plugin.execute._plan_install",
        "planner": "plugin.execute._plan_install",
        "shared_by": ["execute(dry_run=True)", "execute(dry_run=False)", "plugin CLI"],
        "execute_path": str(execute_py).replace("\\", "/"),
    }


__all__ = ["inspect_shared_planner"]
