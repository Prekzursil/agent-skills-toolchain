"""Re-open path:line anchors and confirm the stored quote is on that line."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def resolve_quote(repo: Path, path: str, line: int, quote: str) -> tuple[bool, str]:
    rel = str(path or "").replace("\\", "/")
    if not rel or not quote:
        return False, "empty-anchor"
    fp = Path(rel)
    if not fp.is_absolute():
        fp = repo / rel
    if not fp.is_file():
        return False, f"missing:{rel}"
    lines = fp.read_text(encoding="utf-8").splitlines()
    if line < 1 or line > len(lines):
        return False, f"line-oob:{rel}:{line}:n={len(lines)}"
    if quote not in lines[line - 1]:
        return False, f"snippet-miss:{rel}:{line}"
    return True, f"{rel}:{line}"


def sample_ids(records: list[dict[str, Any]], start: int, count: int, seed: int) -> list[str]:
    ids = sorted(str(r.get("claim_id") or "") for r in records if r.get("claim_id"))
    if not ids:
        return []
    # Deterministic shuffle (Fisher-Yates) so author and reviewer can split one deck.
    order = list(ids)
    rng = seed & 0xFFFFFFFF
    for i in range(len(order) - 1, 0, -1):
        rng = (1103515245 * rng + 12345) & 0x7FFFFFFF
        j = rng % (i + 1)
        order[i], order[j] = order[j], order[i]
    return order[start : start + count]


def check_record(repo: Path, rec: dict[str, Any]) -> tuple[int, int, list[str]]:
    ok = 0
    n = 0
    misses: list[str] = []
    for row in rec.get("source_lineage") or []:
        if not isinstance(row, dict):
            continue
        n += 1
        good, why = resolve_quote(
            repo,
            str(row.get("path") or ""),
            int(row.get("line") or 0),
            str(row.get("quote") or ""),
        )
        if good:
            ok += 1
        else:
            misses.append(f"{rec.get('claim_id')}:{why}")
    return ok, n, misses
