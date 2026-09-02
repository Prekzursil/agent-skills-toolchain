"""Blind two-definition discrimination test (evidence B).

A reader given ONLY two mechanism definitions (no alias table) must
assign 20 held-out example strings. Two definitions that cannot be
told apart must be merged before the vocabulary is frozen.
"""
from __future__ import annotations

from typing import Any

from mapper import score_against
from vocab import DISCRIMINATION_FLOOR, MECHANISMS, by_id

HELDOUT: tuple[dict[str, str], ...] = (
    {
        "text": (
            "CI stays green after the guarded defaults object is deleted "
            "because require_complete defaults to false"
        ),
        "gold": "MX-0001",
        "distractor": "MX-0003",
    },
    {
        "text": (
            "An empty guarded block is treated as a pass because no rows "
            "remained to check"
        ),
        "gold": "MX-0001",
        "distractor": "MX-0009",
    },
    {
        "text": (
            "Windows autocrlf rewrites the working copy to CRLF so hashing "
            "the checkout disagrees with Linux"
        ),
        "gold": "MX-0002",
        "distractor": "MX-0001",
    },
    {
        "text": (
            "The token M-16 names both an option record and an architecture card"
        ),
        "gold": "MX-0003",
        "distractor": "MX-0002",
    },
    {
        "text": (
            "Reviewer B is given a disjoint file partition and must not "
            "read reviewer A's notes"
        ),
        "gold": "MX-0004",
        "distractor": "MX-0005",
    },
    {
        "text": (
            "Two readers score the same item from private sources with no "
            "shared warrant list"
        ),
        "gold": "MX-0004",
        "distractor": "MX-0005",
    },
    {
        "text": (
            "The second judge is handed the first judge's full transcript "
            "before scoring"
        ),
        "gold": "MX-0005",
        "distractor": "MX-0004",
    },
    {
        "text": (
            "Council members iterate in a shared channel until they echo "
            "one conclusion"
        ),
        "gold": "MX-0005",
        "distractor": "MX-0004",
    },
    {
        "text": (
            "Re-running the recorded seed produces the same artifact bytes "
            "on a second machine"
        ),
        "gold": "MX-0006",
        "distractor": "MX-0007",
    },
    {
        "text": (
            "Given the same inputs and seed, the adapter emits a "
            "byte-identical IR"
        ),
        "gold": "MX-0006",
        "distractor": "MX-0007",
    },
    {
        "text": (
            "Raising temperature above zero yields different completions "
            "for one prompt"
        ),
        "gold": "MX-0007",
        "distractor": "MX-0006",
    },
    {
        "text": (
            "Sampling from a distribution produces a different candidate "
            "on each draw"
        ),
        "gold": "MX-0007",
        "distractor": "MX-0006",
    },
    {
        "text": (
            "The parent spawns workers and continues without waiting for "
            "their artifacts"
        ),
        "gold": "MX-0008",
        "distractor": "MX-0009",
    },
    {
        "text": (
            "Dispatch writes a background receipt and never joins the "
            "child process"
        ),
        "gold": "MX-0008",
        "distractor": "MX-0009",
    },
    {
        "text": (
            "The parent blocks at a join until every worker file exists "
            "and the reducer runs"
        ),
        "gold": "MX-0009",
        "distractor": "MX-0008",
    },
    {
        "text": (
            "A fan-in barrier refuses to complete while any worker is still "
            "running and the reducer has not joined"
        ),
        "gold": "MX-0009",
        "distractor": "MX-0008",
    },
    {
        "text": (
            "A handbook that describes fan-in barriers is not an "
            "implementation of a barrier"
        ),
        "gold": "MX-0010",
        "distractor": "MX-0012",
    },
    {
        "text": (
            "Licence class stays attached to the IR node after fusion "
            "rewrites the tree"
        ),
        "gold": "MX-0011",
        "distractor": "MX-0002",
    },
    {
        "text": (
            "Two workflows with identical MX id sets collapse even when "
            "their prose differs"
        ),
        "gold": "MX-0012",
        "distractor": "MX-0010",
    },
    {
        "text": (
            "Dedup is an exact set operation on vocabulary ids, not a "
            "similarity judgement"
        ),
        "gold": "MX-0012",
        "distractor": "MX-0003",
    },
)

GAP_STRINGS: tuple[str, ...] = (
    "CRDT merge of concurrent workflow edits across replicas",
    "GPU kernel fusion for CUDA graphs at launch time",
)


def _mech_view(mid: str) -> dict[str, Any]:
    src = by_id()[mid]
    return {
        "id": src["id"],
        "definition": src["definition"],
        "discriminating_example": src["discriminating_example"],
        "keys": src["keys"],
        "aliases": (),
    }


def assign_two(text: str, left_id: str, right_id: str) -> str:
    left = _mech_view(left_id)
    right = _mech_view(right_id)
    s_left = score_against(text, left, aliases=False)
    s_right = score_against(text, right, aliases=False)
    if s_left == s_right:
        return "TIE"
    return left_id if s_left > s_right else right_id


def run_blind(heldout: tuple[dict[str, str], ...] | None = None) -> dict[str, Any]:
    items = heldout if heldout is not None else HELDOUT
    rows = []
    correct = 0
    for item in items:
        got = assign_two(item["text"], item["gold"], item["distractor"])
        ok = got == item["gold"]
        if ok:
            correct += 1
        rows.append(
            {
                "text": item["text"],
                "gold": item["gold"],
                "distractor": item["distractor"],
                "got": got,
                "ok": ok,
            }
        )
    n = len(items)
    score = correct / n if n else 0.0
    return {
        "n": n,
        "correct": correct,
        "score": round(score, 4),
        "floor": DISCRIMINATION_FLOOR,
        "passed": score >= DISCRIMINATION_FLOOR,
        "rows": rows,
    }


def indistinguishable_pair() -> dict[str, Any]:
    """Clone MX-0004's definition with synonym swaps; must not freeze as a second id."""
    gold = by_id()["MX-0004"]
    clone = {
        "id": "MX-CLONE",
        "definition": (
            "A first pass in which every reader works from a private source "
            "partition and never sees the other reader's notes or warrants."
        ),
        "discriminating_example": (
            "Two reviewers receive disjoint file partitions and are "
            "forbidden from reading each other's transcripts before scoring."
        ),
        "keys": gold["keys"],
        "aliases": (),
    }
    real = _mech_view("MX-0004")
    examples = [h["text"] for h in HELDOUT if h["gold"] == "MX-0004"]
    # Also score MX-0004 aliases as if they were held-out against the clone pair.
    examples.extend(str(a) for a in gold["aliases"])
    clone_wins = 0
    real_wins = 0
    ties = 0
    for text in examples:
        s_real = score_against(text, real, aliases=False)
        s_clone = score_against(text, clone, aliases=False)
        if s_real > s_clone:
            real_wins += 1
        elif s_clone > s_real:
            clone_wins += 1
        else:
            ties += 1
    n = len(examples)
    # Accuracy of "pick the originally labelled id" is not defined for a clone;
    # separability is the fraction not tied and not split near 50/50.
    majority = max(real_wins, clone_wins)
    separability = majority / n if n else 0.0
    must_merge = separability < DISCRIMINATION_FLOOR
    frozen_ids = [str(m["id"]) for m in MECHANISMS]
    clone_admitted = "MX-CLONE" in frozen_ids
    return {
        "pair": ["MX-0004", "MX-CLONE"],
        "n_examples": n,
        "real_wins": real_wins,
        "clone_wins": clone_wins,
        "ties": ties,
        "separability": round(separability, 4),
        "floor": DISCRIMINATION_FLOOR,
        "must_merge": must_merge,
        "clone_admitted_to_frozen_vocab": clone_admitted,
        "merged_before_freeze": must_merge and not clone_admitted,
    }
