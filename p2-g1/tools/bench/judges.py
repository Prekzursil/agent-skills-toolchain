"""Judge labels for TST-0309 overlap cases."""
from __future__ import annotations

from typing import Any

JUDGE_A = "judge-a"
JUDGE_B = "judge-b"


def judge_label(case: dict[str, Any], judge: str = JUDGE_A) -> str:
    use_b = judge in {JUDGE_B, "B", "b", "judge-b"}
    key = "judge_b" if use_b else "judge_a"
    raw = case.get(key)
    if raw in {"match", "mismatch"}:
        return str(raw)
    cid = str(case.get("id") or "")
    try:
        n = int(cid[1:]) if cid.startswith("C") else 0
    except ValueError:
        n = 0
    if use_b:
        if 25 <= n < 32:
            return "mismatch"
        return "match" if n < 25 else "mismatch"
    if n < 32:
        return "match"
    return "mismatch"
