#!/usr/bin/env python3
"""Probe 1: independent hold-out recompute + confusion matrix + constant-function control.

Signal A is mechanically independent of probe 2: it reloads the corpus, re-fits
thresholds on the train split only, and checks the artifact's stored numbers.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center"))

from foundry.routing.corpus import load_corpus  # noqa: E402
from foundry.routing.fit import OVERFIT_GAP, agreement, evaluate_corpus, fit_thresholds, split_holdout  # noqa: E402
from foundry.routing.gold import HUMAN_CLASSES, ROUTES, histogram_n  # noqa: E402

ART = REPO / "command-center/foundry/WFA-0146-find-repair-merge-build-recommendation-function.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0146-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:WFA-0146" not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if doc.get("unit_id") != "WFA-0146":
        return fail(f"unit_id={doc.get('unit_id')}")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    rows, meta = load_corpus()
    if len(rows) != histogram_n():
        return fail(f"corpus n={len(rows)}")
    train, hold = split_holdout(rows)
    thresholds, _fit = fit_thresholds(train)
    train_ag = agreement(train, thresholds)
    hold_ag = agreement(hold, thresholds)
    evaluated = evaluate_corpus(rows, thresholds)
    pred_counts = Counter(x["predicted_route"] for x in evaluated)

    art_t = doc.get("thresholds") or {}
    for k, v in thresholds.items():
        got = art_t.get(k)
        if got is None or abs(float(got) - float(v)) > 1e-9:
            return fail(f"threshold mismatch {k} live={v} artifact={got}")

    h = doc.get("holdout") or {}
    if abs(float(h.get("train_agreement")) - train_ag["agreement"]) > 1e-9:
        return fail("train_agreement mismatch")
    if abs(float(h.get("holdout_agreement")) - hold_ag["agreement"]) > 1e-9:
        return fail("holdout_agreement mismatch")
    if int(h.get("n_train")) != len(train) or int(h.get("n_holdout")) != len(hold):
        return fail("split size mismatch")
    gap = train_ag["agreement"] - hold_ag["agreement"]
    want_overfit = bool(gap > OVERFIT_GAP)
    if bool(h.get("overfit")) != want_overfit:
        return fail(f"overfit flag mismatch gap={gap} flag={h.get('overfit')}")

    if len(pred_counts) < 3:
        return fail(f"constant-function histogram={dict(pred_counts)}")
    if not (doc.get("constant_function_control") or {}).get("pass"):
        return fail("artifact constant_function_control.pass is not true")

    eval_rows = doc.get("evaluation_rows") or []
    if len(eval_rows) != histogram_n():
        return fail(f"evaluation_rows n={len(eval_rows)}")
    live_by_id = {x["id"]: x for x in evaluated}
    for stored in eval_rows:
        live = live_by_id.get(stored["id"])
        if live is None:
            return fail(f"extra stored id {stored['id']}")
        if stored.get("predicted_route") != live["predicted_route"]:
            return fail(f"route mismatch {stored['id']}")
        audit = stored.get("audit") or {}
        if audit.get("route") != stored.get("predicted_route"):
            return fail(f"audit route mismatch {stored['id']}")
        if stored.get("predicted_route") not in ROUTES:
            return fail(f"non-route {stored.get('predicted_route')}")

    cm = doc.get("confusion_matrix") or {}
    if cm.get("n") != histogram_n():
        return fail("confusion n")
    if list(cm.get("predicted_routes") or []) != list(ROUTES):
        return fail("confusion routes")
    if list(cm.get("human_classes") or []) != list(HUMAN_CLASSES):
        return fail("confusion classes")
    counts = cm.get("counts") or {}
    recomputed = {r: {c: 0 for c in HUMAN_CLASSES} for r in ROUTES}
    for x in evaluated:
        recomputed[x["predicted_route"]][x["classification"]] += 1
    for r in ROUTES:
        for c in HUMAN_CLASSES:
            if int((counts.get(r) or {}).get(c) or 0) != recomputed[r][c]:
                return fail(f"confusion cell {r}/{c}")

    disag_ids = {d["id"] for d in (doc.get("disagreements") or [])}
    want_disag = {x["id"] for x in evaluated if x["gold_route"] and x["predicted_route"] != x["gold_route"]}
    if disag_ids != want_disag:
        return fail(f"disagreement set mismatch extra={sorted(disag_ids - want_disag)[:5]} missing={sorted(want_disag - disag_ids)[:5]}")

    art_live = bool((doc.get("registry_source") or {}).get("live_present"))
    if art_live != bool(meta.get("live_present")):
        return fail("registry_source.live_present mismatch")
    if art_live is False and not (doc.get("honesty") or {}).get("does_not_claim_windows_path_per_id_disagreement"):
        return fail("reconstruction must not claim Windows-path per-id disagreement")

    out = {
        "probe": "probe1-holdout",
        "unit_id": "WFA-0146",
        "n": len(evaluated),
        "distinct_routes": len(pred_counts),
        "histogram": dict(pred_counts),
        "train_agreement": train_ag["agreement"],
        "holdout_agreement": hold_ag["agreement"],
        "overfit": want_overfit,
        "disagreements": len(want_disag),
        "live_present": bool(meta.get("live_present")),
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"n=284 distinct={len(pred_counts)} holdout={hold_ag['agreement']:.4f} "
        f"train={train_ag['agreement']:.4f} overfit={want_overfit} disag={len(want_disag)}"
    )
    print("SUCCESS:WFA-0146-probe1 holdout confusion-matrix constant-function-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
