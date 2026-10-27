#!/usr/bin/env python3
"""Assign gold labels from the semver X.0.0 contract. Does not import detector.

A note is gold-positive iff parse_semver(tag) is (X, 0, 0) with X >= 1.
That is the semver-major release event, taken from the version identifier
not from changelog wording. Control negatives are adjacent patch steps
(same major.minor, patch == previous.patch + 1), first 20 by id sort.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import CORPUS, LABELS, dump_json, is_x_0_0, load_json, sha256_file  # noqa: E402
from contract import N_CONTROL_NEGATIVES  # noqa: E402

RATIONALE_POS = (
    "Gold-positive: parsed version is X.0.0 (major>=1). Semver §4 treats a "
    "major increment as the incompatible-API event. Assigned from the tag, "
    "not from changelog prose."
)
RATIONALE_NEG = (
    "Gold-negative: parsed version is not X.0.0. Not labelled from detector "
    "features."
)
RATIONALE_CTRL = (
    "Control-negative: adjacent patch step (X.Y.Z -> X.Y.(Z+1)) and not "
    "X.0.0. Selected by version arithmetic, not by changelog wording."
)


def _assert_no_detector_import() -> None:
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "detector" or alias.name.startswith("detector."):
                    raise RuntimeError("labels.py must not import detector")
        if isinstance(node, ast.ImportFrom):
            if node.module == "detector" or (node.module or "").startswith("detector."):
                raise RuntimeError("labels.py must not import detector")


def is_patch_step(note: dict) -> bool:
    cur = note.get("semver")
    prev = note.get("previous_semver") or note.get("previous_semver")
    if not isinstance(cur, list) or not isinstance(prev, list):
        return False
    if len(cur) < 3 or len(prev) < 3:
        return False
    return (
        int(cur[0]) == int(prev[0])
        and int(cur[1]) == int(prev[1])
        and int(cur[2]) == int(prev[2]) + 1
        and not is_x_0_0((int(cur[0]), int(cur[1]), int(cur[2])))
    )


def assign(corpus: dict) -> dict:
    notes = corpus["notes"]
    rows = []
    for note in notes:
        sem = tuple(note["semver"])
        positive = is_x_0_0(sem)
        rows.append(
            {
                "id": note["id"],
                "tag": note["tag"],
                "semver": list(sem),
                "gold_breaking": bool(positive),
                "control_negative": False,
                "rationale": RATIONALE_POS if positive else RATIONALE_NEG,
                "labelled_from": "semver-X.0.0-tag",
            }
        )
    patch_ids = sorted(n["id"] for n in notes if is_patch_step(n))
    control_ids = patch_ids[:N_CONTROL_NEGATIVES]
    by_id = {r["id"]: r for r in rows}
    for cid in control_ids:
        by_id[cid]["control_negative"] = True
        by_id[cid]["rationale"] = RATIONALE_CTRL
    n_pos = sum(1 for r in rows if r["gold_breaking"])
    return {
        "unit_id": "RES-0141",
        "label_rule": (
            "gold_breaking := parsed tag is X.0.0 with X>=1. Independent of "
            "detector.py. Control negatives := first 20 adjacent patch steps "
            f"by id sort (need {N_CONTROL_NEGATIVES})."
        ),
        "n_notes": len(rows),
        "n_gold_positive": n_pos,
        "n_gold_negative": len(rows) - n_pos,
        "n_control_negative": len(control_ids),
        "control_ids": control_ids,
        "labels": rows,
    }


def main() -> int:
    _assert_no_detector_import()
    corpus = load_json(CORPUS)
    doc = assign(corpus)
    if doc["n_gold_positive"] < 10:
        print("FAILED:labels too few gold positives", doc["n_gold_positive"])
        return 1
    if doc["n_control_negative"] < N_CONTROL_NEGATIVES:
        print("FAILED:labels too few controls", doc["n_control_negative"])
        return 1
    dump_json(LABELS, doc)
    sha, n = sha256_file(LABELS)
    print(
        f"wrote {LABELS} positives={doc['n_gold_positive']} "
        f"controls={doc['n_control_negative']} sha256={sha} bytes={n}"
    )
    print("SUCCESS:RES-0141-labels")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
