"""Count M-NN ids that appear in both option-universe and architecture slices."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_ID = re.compile(r"\bM-(\d{2})\b")


def _ids(text: str) -> set[str]:
    return {f"M-{m.group(1)}" for m in _ID.finditer(text)}


def collision_count(option_text: str, arch_text: str) -> int:
    return len(_ids(option_text) & _ids(arch_text))


def live_snapshot(
    repo: Path | None = None,
    option_path: Path | None = None,
    arch_path: Path | None = None,
) -> dict[str, Any]:
    del repo
    opt = Path(option_path).read_text(encoding="utf-8") if option_path else ""
    arch = Path(arch_path).read_text(encoding="utf-8") if arch_path else ""
    option_ids = sorted(_ids(opt))
    return {
        "collision_count": collision_count(opt, arch),
        "option_family_m_count": len(option_ids),
        "option_ids": option_ids,
    }
