"""Signal B: independent adjacency-matrix transpose comparison (WFA-0004).

Deliberately a different derivation from counts.py: builds the boolean
adjacency matrix and compares it to its transpose element-wise.
"""
from __future__ import annotations

from typing import Any

CODE_PATH = "tools/wfa_compat/transpose.py"


def matrix_equals_transpose(adj: dict[str, set[str]]) -> dict[str, Any]:
    ids = sorted(set(adj.keys()) | {t for v in adj.values() for t in v})
    index = {nid: i for i, nid in enumerate(ids)}
    n = len(ids)
    matrix = [[False] * n for _ in range(n)]
    for src, targets in adj.items():
        for dst in targets:
            matrix[index[src]][index[dst]] = True
    mismatches: list[tuple[str, str]] = []
    for i in range(n):
        for j in range(i + 1, n):
            if matrix[i][j] != matrix[j][i]:
                mismatches.append((ids[i], ids[j]))
    return {
        "M_equals_MT": not mismatches,
        "n": n,
        "mismatch_count": len(mismatches),
        "mismatch_sample": mismatches[:5],
        "code_path": CODE_PATH,
    }


__all__ = ["CODE_PATH", "matrix_equals_transpose"]
