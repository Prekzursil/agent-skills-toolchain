#!/usr/bin/env python3
"""Gold scoring and round-trip reader for WFA-0036."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from extractor import HONEST_NULL, extract, is_honest_null, render_prose  # noqa: E402

FIELDS = ("name", "inputs", "outputs", "gate", "fan_out_degree")


def load_corpus() -> list[dict[str, Any]]:
    doc = json.loads((HERE / "fixtures" / "corpus.json").read_text(encoding="utf-8"))
    return list(doc["records"])


def load_gold() -> dict[str, Any]:
    return json.loads((HERE / "fixtures" / "gold.json").read_text(encoding="utf-8"))


def _eq(got: Any, want: Any) -> bool:
    return json.dumps(got, sort_keys=True, default=str) == json.dumps(
        want, sort_keys=True, default=str
    )


def _score_record(extracted: Any, label: Any) -> dict[str, dict[str, int]]:
    tallies = {f: {"n": 0, "ok": 0} for f in FIELDS}
    if label == HONEST_NULL or is_honest_null(label):
        match = is_honest_null(extracted)
        for field in FIELDS:
            tallies[field]["n"] = 1
            tallies[field]["ok"] = 1 if match else 0
        return tallies
    if is_honest_null(extracted) or not isinstance(extracted, list):
        n = len(label) if isinstance(label, list) else 1
        for field in FIELDS:
            tallies[field]["n"] = n
            tallies[field]["ok"] = 0
        return tallies
    n = max(len(label), len(extracted))
    for i in range(n):
        want = label[i] if i < len(label) else None
        got = extracted[i] if i < len(extracted) else None
        for field in FIELDS:
            tallies[field]["n"] += 1
            if want is None or got is None:
                continue
            if _eq(got.get(field), want.get(field)):
                tallies[field]["ok"] += 1
    return tallies


def score_gold() -> dict[str, Any]:
    corpus = load_corpus()
    gold = load_gold()
    labels = gold["labels"]
    acc = {f: {"n": 0, "ok": 0} for f in FIELDS}
    rows = []
    for rec in corpus:
        rid = rec["id"]
        extracted = extract(rec["native"])
        label = labels[rid]
        part = _score_record(extracted, label)
        for field in FIELDS:
            acc[field]["n"] += part[field]["n"]
            acc[field]["ok"] += part[field]["ok"]
        rows.append(
            {
                "id": rid,
                "family": rec.get("family"),
                "extracted": extracted,
                "gold": label,
                "honest_null": is_honest_null(extracted),
            }
        )
    per_field = {}
    for field, row in acc.items():
        n = row["n"]
        ok = row["ok"]
        per_field[field] = {
            "n": n,
            "ok": ok,
            "accuracy": (ok / n) if n else 0.0,
        }
    return {
        "gold_id": gold.get("gold_id"),
        "n_records": len(corpus),
        "per_field": per_field,
        "rows": rows,
    }


def fan_out_is_numeric_or_null(extracted: Any) -> bool:
    if is_honest_null(extracted):
        return True
    if not isinstance(extracted, list):
        return False
    for stage in extracted:
        fan = stage.get("fan_out_degree")
        if fan is None:
            continue
        if isinstance(fan, bool) or not isinstance(fan, int):
            return False
    return True


def round_trip(n_decoys: int = 2) -> dict[str, Any]:
    corpus = load_corpus()
    trials = []
    correct = 0
    for i, rec in enumerate(corpus):
        extracted = extract(rec["native"])
        rendered = render_prose(extracted)
        decoys = []
        j = 1
        while len(decoys) < n_decoys:
            other = corpus[(i + j) % len(corpus)]
            if other["id"] != rec["id"]:
                decoys.append(other)
            j += 1
        options = [rec] + decoys
        picked = None
        best = -1
        for opt in options:
            opt_ex = extract(opt["native"])
            opt_render = render_prose(opt_ex)
            if opt_render == rendered:
                picked = opt["id"]
                break
            names = []
            if not is_honest_null(opt_ex):
                names = [str(s.get("name")) for s in opt_ex]
            score = sum(1 for name in names if name and name in rendered)
            if is_honest_null(opt_ex) and rendered == "NO-DECLARED-STAGES":
                score += 10
            if score > best:
                best = score
                picked = opt["id"]
        ok = picked == rec["id"]
        if ok:
            correct += 1
        trials.append(
            {
                "id": rec["id"],
                "picked": picked,
                "ok": ok,
                "rendered": rendered,
                "option_ids": [o["id"] for o in options],
            }
        )
    return {
        "n": len(trials),
        "correct": correct,
        "accuracy": correct / len(trials) if trials else 0.0,
        "trials": trials,
    }
