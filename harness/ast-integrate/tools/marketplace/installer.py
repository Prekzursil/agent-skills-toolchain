"""Marketplace installer: deny-by-default for unsigned / unsigned-off packages."""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class InstallResult:
    verdict: str
    refused: bool
    placed_any_file: bool
    census_unchanged: bool
    reason: str
    error: str = ""

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


def install(
    pkg: Path | str,
    target: Path | str,
    policy: dict[str, Any] | None = None,
    *,
    signature_state: str = "unsigned",
    trust_level: str = "unrated",
    advisory_state: str = "none",
    require_signoff: bool = False,
    **kwargs: Any,
) -> InstallResult:
    del kwargs
    policy = policy or {}
    need_signoff = bool(require_signoff or policy.get("owner_signoff_required"))
    unsigned = str(signature_state).lower() in {"unsigned", "missing", "invalid", "none", ""}
    unrated = str(trust_level).lower() in {"unrated", "unknown", "none", ""}
    if unsigned or unrated or need_signoff:
        return InstallResult(
            verdict="REFUSED",
            refused=True,
            placed_any_file=False,
            census_unchanged=True,
            reason="unsigned-or-unrated-pending-owner-signoff",
            error="install denied: unsigned package requires owner signoff",
        )
    dest = Path(target)
    dest.mkdir(parents=True, exist_ok=True)
    src = Path(pkg)
    if src.is_dir():
        for child in src.iterdir():
            if child.is_file():
                shutil.copy2(child, dest / child.name)
    elif src.is_file():
        shutil.copy2(src, dest / src.name)
    return InstallResult(
        verdict="INSTALLED",
        refused=False,
        placed_any_file=True,
        census_unchanged=False,
        reason="signed-and-rated",
    )


def census(target: Path | str) -> list[str]:
    p = Path(target)
    if not p.is_dir():
        return []
    return sorted(x.name for x in p.iterdir())
