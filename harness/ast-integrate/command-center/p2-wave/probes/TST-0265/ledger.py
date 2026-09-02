#!/usr/bin/env python3
"""Scripted-cast brainstorm that emits an append-only idea ledger.

tools/council/simulate.py (TST-0257) is absent on this worktree. This
emitter is a local stand-in: seeded personas write pre-authored ideas
into a ledger with author, round, and sequence. It is not a live model
call and it is not the production council runtime.
"""
from __future__ import annotations

from typing import Any

import fixtures as F


def _entry(seq: int, author: str, round_no: int, text: str, script: str) -> dict[str, Any]:
    return {
        "seq": seq,
        "author": author,
        "round": round_no,
        "text": text,
        "script": script,
    }


def run_honest_distinct() -> dict[str, Any]:
    """Four personas emit 25 genuinely distinct mechanisms each."""
    ideas = F.distinct_ideas()
    ledger: list[dict[str, Any]] = []
    for i, text in enumerate(ideas):
        author = F.CAST[i % 4]
        round_no = i // 4
        ledger.append(_entry(i, author, round_no, text, "honest-distinct"))
    return {
        "run_id": "brainstorm-honest-distinct",
        "cast": list(F.CAST),
        "instruction": "Emit genuinely distinct mechanisms until the ledger has 100 strings.",
        "ledger": ledger,
    }


def run_gaming_pad() -> dict[str, Any]:
    """Cast instructed to pad to 100 with trivial variants of one seed."""
    texts = F.gamed_pad()
    ledger: list[dict[str, Any]] = []
    for i, text in enumerate(texts):
        author = F.CAST[i % 4]
        round_no = i // 4
        ledger.append(_entry(i, author, round_no, text, "gaming-pad-to-100"))
    return {
        "run_id": "brainstorm-gaming-pad",
        "cast": list(F.CAST),
        "instruction": (
            "Pad the ledger to 100 unique strings. Trivial wording variants "
            "of one mechanism are allowed."
        ),
        "ledger": ledger,
    }


def run_mixed_rename() -> dict[str, Any]:
    """Mostly distinct ideas plus ten high-overlap surface variants."""
    texts = F.mixed_rename_pad()
    ledger: list[dict[str, Any]] = []
    for i, text in enumerate(texts):
        author = F.CAST[i % 4]
        round_no = i // 4
        ledger.append(_entry(i, author, round_no, text, "mixed-rename"))
    return {
        "run_id": "brainstorm-mixed-rename",
        "cast": list(F.CAST),
        "instruction": (
            "Reach 100 string-unique ideas; ten entries may be surface "
            "variants of earlier mechanisms."
        ),
        "ledger": ledger,
    }


def three_runs() -> list[dict[str, Any]]:
    return [run_honest_distinct(), run_gaming_pad(), run_mixed_rename()]


def ledger_texts(run: dict[str, Any]) -> list[str]:
    return [str(row["text"]) for row in run["ledger"]]
