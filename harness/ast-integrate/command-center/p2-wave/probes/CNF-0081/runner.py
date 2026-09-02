"""Execute a hermetic workflow and measure cost, wall-clock, and tokens.

Actual tokens include hidden_retries and amplifier, which the estimator does
not see. Wall-clock is time.perf_counter, not a logged intention. Writes are
real filesystem creates in a temp directory.
"""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

from ledger import LAST_TURN_FIELD, TokenLedger, cost_usd


def _burn(tokens: int) -> str:
    h = hashlib.sha256()
    payload = b"CNF-0081"
    n = max(16, int(tokens) * 4)
    for i in range(n):
        h.update(payload)
        h.update(i.to_bytes(4, "little"))
    return h.hexdigest()


def _write(root: Path, rel: str, digest: str) -> str:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(digest + "\n", encoding="utf-8", newline="\n")
    return rel.replace("\\", "/")


def run_workflow(
    wf: dict,
    *,
    work_root: Path,
    extra_turn_tokens: int | None = None,
) -> dict | None:
    if wf.get("skip_run"):
        return None
    stages = list(wf.get("stages") or [])
    amp = int(wf.get("amplifier") or 1)
    hidden = int(wf.get("hidden_retries") or 0)
    ledger = TokenLedger()
    writes: list[str] = []
    t0 = time.perf_counter()
    for stage in stages:
        sid = str(stage.get("id") or "stage")
        declared = int(stage.get("declared_tokens", 80))
        actual = declared * amp
        digest = _burn(actual)
        ledger.record_turn(actual, sid)
        for out in stage.get("outputs") or []:
            writes.append(_write(work_root, str(out), digest))
        for k in range(hidden):
            retry_id = f"{sid}.hidden-retry.{k + 1}"
            digest = _burn(declared)
            ledger.record_turn(declared, retry_id)
    if extra_turn_tokens is not None:
        digest = _burn(int(extra_turn_tokens))
        ledger.record_turn(int(extra_turn_tokens), "control.extra-turn")
        writes.append(_write(work_root, "out/extra-turn.control", digest))
    wall = time.perf_counter() - t0
    snap = ledger.snapshot()
    return {
        "tokens_cumulative": snap["tokens_cumulative"],
        "tokens_last_turn": snap["tokens_last_turn"],
        "n_turns": snap["n_turns"],
        "turns": snap["turns"],
        "wall_clock_s": wall,
        "cost_usd": cost_usd(snap["tokens_cumulative"]),
        "cost_usd_if_last_turn_conflated": cost_usd(snap["tokens_last_turn"]),
        "writes": writes,
        "accounting_fields": {
            "cumulative": "tokens_cumulative",
            "last_turn": "tokens_last_turn",
            "last_turn_field_name": LAST_TURN_FIELD,
        },
    }
