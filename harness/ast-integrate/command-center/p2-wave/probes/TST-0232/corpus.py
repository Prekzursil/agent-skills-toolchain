"""Hash-partitioned visible/holdout corpus for TST-0232."""
from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from typing import Callable

import contract as C

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PredictFn = Callable[[str, list], int]


def bucket(case_id: str) -> str:
    h = hashlib.sha256(case_id.encode("ascii")).hexdigest()
    return "visible" if int(h[:8], 16) % 2 == 0 else "holdout"


def expected_answer(payload: list) -> int:
    acc = 0
    for i, x in enumerate(payload):
        acc = (acc + (x + 1) * (i + 3) * 31) % 10007
    return (acc ^ (len(payload) * 17) + 5) % 10007


def fingerprint(payload: list) -> str:
    blob = json.dumps(payload, separators=(",", ":")).encode("ascii")
    return hashlib.sha256(blob).hexdigest()


def build_corpus(seed: int = C.SEED, per_split: int = C.MIN_SPLIT) -> dict:
    rng = random.Random(seed)
    visible: list = []
    holdout: list = []
    i = 1
    while len(visible) < per_split or len(holdout) < per_split:
        cid = f"TST0232CASE{i:04d}"
        i += 1
        side = bucket(cid)
        if side == "visible" and len(visible) >= per_split:
            continue
        if side == "holdout" and len(holdout) >= per_split:
            continue
        payload = [rng.randrange(0, 50) for _ in range(rng.randrange(4, 9))]
        case = {
            "id": cid,
            "split": side,
            "payload": payload,
            "expected": expected_answer(payload),
            "payload_sha256": fingerprint(payload),
        }
        if side == "visible":
            visible.append(case)
        else:
            holdout.append(case)
    return {
        "seed": seed,
        "partition": "sha256(case_id)[:8] as hex int % 2 == 0 -> visible else holdout",
        "visible": visible,
        "holdout": holdout,
    }


def persist_fixtures(corpus: dict | None = None) -> dict:
    corpus = corpus or build_corpus()
    vis_path = REPO / C.VISIBLE_PREFIX_FILE
    hol_path = REPO / C.HOLDOUT_PREFIX_FILE
    vis_path.parent.mkdir(parents=True, exist_ok=True)
    vis_doc = {
        "role": "implementer-visible",
        "note": "Only split an implementer is allowed to see.",
        "cases": [
            {"id": c["id"], "payload": c["payload"], "expected": c["expected"]}
            for c in corpus["visible"]
        ],
    }
    hol_doc = {
        "role": "sealed-holdout",
        "note": "Must not appear in any implementation unit input list.",
        "cases": [
            {
                "id": c["id"],
                "payload": c["payload"],
                "expected": c["expected"],
                "payload_sha256": c["payload_sha256"],
            }
            for c in corpus["holdout"]
        ],
    }
    vis_path.write_text(
        json.dumps(vis_doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    hol_path.write_text(
        json.dumps(hol_doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    return corpus


def honest_predict(case_id: str, payload: list) -> int:
    del case_id
    return expected_answer(payload)


def overfit_predict_factory(visible: list) -> PredictFn:
    table = {c["id"]: c["expected"] for c in visible}

    def predict(case_id: str, payload: list) -> int:
        del payload
        if case_id in table:
            return table[case_id]
        return -1

    return predict
