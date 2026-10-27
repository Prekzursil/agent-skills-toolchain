"""Score detector combinations against frozen gold labels."""
from __future__ import annotations

import itertools
from typing import Iterable

import detector as _detector
from detector import SIGNAL_IDS, fires

signals_for = getattr(_detector, "signals_for", None) or getattr(
    _detector, "signals_for"
)


def prf(tp: int, fp: int, fn: int) -> dict:
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": None,
        "precision": round(prec, 6),
        "recall": round(rec, 6),
        "f1": round(f1, 6),
    }


def combo_metrics(notes: list[dict], labels: dict[str, dict], combo: tuple[str, ...]) -> dict:
    tp = fp = fn = tn = 0
    control_fp: list[str] = []
    for note in notes:
        row = labels[note["id"]]
        gold = bool(row.get("gold_breaking", row.get("gold_breaking")))
        pred = fires(note["text"], combo)
        if pred and gold:
            tp += 1
        elif pred and not gold:
            fp += 1
        elif (not pred) and gold:
            fn += 1
        else:
            tn += 1
        if pred and (row.get("control_negative") or row.get("control_negative")):
            control_fp.append(note["id"])
    stats = prf(tp, fp, fn)
    stats["tn"] = tn
    stats["combo"] = list(combo)
    stats["control_fp_ids"] = control_fp
    stats["control_fp"] = len(control_fp)
    stats["silent_on_controls"] = len(control_fp) == 0
    return stats


def all_combos(ids: Iterable[str] = SIGNAL_IDS) -> list[tuple[str, ...]]:
    names = list(ids)
    out: list[tuple[str, ...]] = []
    for r in range(1, len(names) + 1):
        out.extend(itertools.combinations(names, r))
    return out


def evaluate(notes: list[dict], label_rows: list[dict]) -> dict:
    labels = {r["id"]: r for r in label_rows}
    per_note = []
    for note in notes:
        row = labels[note["id"]]
        sig = signals_for(note["text"])
        gold = bool(row.get("gold_breaking", row.get("gold_breaking")))
        per_note.append(
            {
                "id": note["id"],
                "gold_breaking": gold,
                "control_negative": bool(
                    row.get("control_negative") or row.get("control_negative")
                ),
                "signals": sig,
            }
        )
    combo_rows = [combo_metrics(notes, labels, c) for c in all_combos()]
    silent = [r for r in combo_rows if r["silent_on_controls"]]
    unconstrained_best = max(combo_rows, key=lambda r: (r["f1"], r["precision"], r["recall"]))
    if silent:
        best = max(silent, key=lambda r: (r["f1"], r["precision"], r["recall"]))
    else:
        best = unconstrained_best
    n_pos = sum(
        1 for r in label_rows if r.get("gold_breaking", r.get("gold_breaking"))
    )
    n_ctrl = sum(
        1
        for r in label_rows
        if r.get("control_negative") or r.get("control_negative")
    )
    return {
        "n_notes": len(notes),
        "n_gold_positive": n_pos,
        "n_control_negative": n_ctrl,
        "per_note": per_note,
        "combinations": combo_rows,
        "best_silent_on_controls": best,
        "best_unconstrained": unconstrained_best,
        "any_combo_silent_on_controls": bool(silent),
    }
