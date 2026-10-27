"""TST-0282 gold set: 20 author-constructed cases (8 train + 12 heldout).

Rubric labels are assigned from the case KIND. The scorer never reads labels.
Fixture provenance: the receipt's original gold_set.json (92726 bytes) is
absent on this host; this builder is deterministic and documented.
"""
from __future__ import annotations

BODY_LONG = (
    "Measure the null delta by running the identical configuration ten times "
    "then publish the standard deviation of the measured deltas as the "
    "variance floor every later improvement claim must cite the floor is "
    "computed from the same harness same seed and same inputs with no change"
)
BODY_PAD = (
    "As per the above notes and existing discussions we should also remember "
    "to consider reviewing the broader context again later with the usual "
    "caveats and additional remarks about scope ownership timing and process "
    "considerations that were already mentioned elsewhere"
)


def _objective() -> dict:
    return {
        "subquestions": [{"id": "sq0"}, {"id": "sq1"}],
        "required_categories": ["cat0", "cat1"],
        "evidence_classes": ["ev0"],
    }


def _ans(sq_id, body, cats=None):
    d = {"subquestion_id": sq_id, "body": BODY_LONG if body == "long" else body}
    if cats is not None:
        d["categories"] = cats
    return d


FULL = [
    _ans("sq0", "long", ["cat0", "cat1"]),
    _ans("sq1", "long", ["cat0"]),
]
EV = {"evidence_class": "ev0", "cites": "probe"}
EV_NOCITE = {"evidence_class": "ev0"}
STUBS = [
    _ans("sq0", "TBD see note"),
    _ans("sq1", "as above"),
]
ONE_AXIS = [
    _ans("sq0", "long", ["cat0"]),
    _ans("sq1", "long", ["cat0"]),
]

# (id, kind, label10, answers, evidence)
CASES = [
    ("train.complete", "complete", 10, FULL, [EV]),
    ("train.empty", "empty", 0, [], []),
    ("train.padded-volume", "padded", 1, [{"subquestion_id": "sq0", "body": BODY_PAD}], []),
    ("train.stubs", "stubs", 1, STUBS, []),
    ("train.one-axis", "partial", 4, ONE_AXIS, []),
    ("train.gamed-cats", "gamed", 3, [_ans("sq0", "long", ["cat0", "cat1"])], [EV]),
    ("train.partial-half", "partial", 5,
     [_ans("sq0", "long", ["cat0", "cat1"]), _ans("sq1", "long", ["cat1"])], [EV]),
    ("train.missing-ev", "missing", 6, FULL, [dict(EV)]),
    ("heldout.complete-a", "complete", 10, FULL, [dict(EV)]),
    ("heldout.complete-b", "complete", 10, FULL, [dict(EV)]),
    ("heldout.empty", "empty", 0, [], []),
    ("heldout.padded-volume", "padded", 1,
     [{"subquestion_id": "sq0", "body": (BODY_PAD + " ") * 20}], []),
    ("heldout.stubs", "stubs", 1, STUBS, []),
    ("heldout.one-axis-sq", "partial", 3, ONE_AXIS, []),
    ("heldout.gamed-cats-ev", "gamed", 3, [_ans("sq0", "long", ["cat0", "cat1"])], [dict(EV)]),
    ("heldout.partial-half", "partial", 5,
     [_ans("sq0", "long", ["cat0", "cat1"]), _ans("sq1", "TBD stub")], [dict(EV)]),
    ("heldout.one-cat", "partial", 5, [_ans("sq1", "long", ["cat0", "cat1"])], [dict(EV)]),
    ("heldout.one-cat-missing-cite", "gamed-citation", 3, FULL, [EV_NOCITE]),
    ("heldout.complete-extra-pad", "complete", 10,
     FULL + [{"subquestion_id": "undeclared-x", "body": BODY_PAD}], [dict(EV)]),
    ("heldout.complete-extra-pad-2", "complete", 10,
     FULL + [{"subquestion_id": "undeclared-y", "body": BODY_PAD}], [dict(EV)]),
]


def build() -> dict:
    cases = []
    for cid, kind, label10, answers, evidence in CASES:
        cases.append({
            "id": cid,
            "kind": kind,
            "human_label": label10 / 10.0,
            "objective": _objective(),
            "output": {"answers": answers, "evidence": evidence},
        })
    train = [c for c in cases if c["id"].startswith("train.")]
    held = [c for c in cases if c["id"].startswith("heldout.")]
    return {
        "fixture": "gold_set",
        "label_provenance": (
            "Author-constructed fixture labels for TST-0282 (shard22-w4 "
            "reconstruction). Not a held-out production human panel. Rubric "
            "integers assigned from case kind; the scorer never reads them."
        ),
        "n": len(cases),
        "n_train": len(train),
        "n_heldout": len(held),
        "train": train,
        "heldout": held,
        "provenance_note": (
            "Receipt original gold_set.json is absent on this host; "
            "deterministic reconstruction; live validation runs against it."
        ),
    }


if __name__ == "__main__":
    import json
    from pathlib import Path

    g = build()
    out = Path(__file__).resolve().parent / "gold_set.json"
    out.write_text(json.dumps(g, indent=1), encoding="utf-8")
    print("gold_set.json", g["n"], g["n_train"], g["n_heldout"])
