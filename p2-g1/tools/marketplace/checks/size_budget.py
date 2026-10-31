"""Rule size-budget: package payload must fit the declared ceiling."""
from __future__ import annotations

SIZE_CEILING_BYTES = 512 * 1024


def standalone_findings(root):
    from pathlib import Path

    root = Path(root)
    total = sum(p.stat().st_size for p in root.rglob("*") if p.is_file())
    if total > SIZE_CEILING_BYTES:
        return [
            {
                "rule": "size-budget",
                "detail": "package size %d exceeds ceiling %d" % (total, SIZE_CEILING_BYTES),
            }
        ]
    return []
