"""Load labelled fixtures and score precision/recall."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
import kit  # noqa: E402

FIXTURES = HERE / "fixtures"
LABELLED = FIXTURES / "labelled.json"


def load_cases() -> list[dict]:
    rows = json.loads(LABELLED.read_text(encoding="utf-8"))
    out = []
    for row in rows:
        text = row.get("text")
        if not text:
            text = (FIXTURES / row["file"]).read_text(encoding="utf-8")
        out.append({**row, "text": text})
    return out


def score(cases: list[dict] | None = None) -> dict:
    cases = cases if cases is not None else load_cases()
    tp = fp = fn = tn = 0
    mismatches: list[dict] = []
    rows = []
    for case in cases:
        got = kit.roles(case["text"], case["token"])
        exp = list(case["expected"])
        ok = got == exp
        rows.append(
            {
                "id": case["id"],
                "token": case["token"],
                "expected": exp,
                "got": got,
                "ok": ok,
            }
        )
        if not ok:
            mismatches.append(rows[-1])
        n = max(len(got), len(exp))
        for i in range(n):
            g = got[i] if i < len(got) else None
            e = exp[i] if i < len(exp) else None
            if e is None and g is not None:
                fp += 1
                continue
            if g is None and e is not None:
                fn += 1
                continue
            use_e = e == "USE"
            use_g = g == "USE"
            if use_e and use_g:
                tp += 1
            elif use_g and not use_e:
                fp += 1
            elif use_e and not use_g:
                fn += 1
            else:
                tn += 1
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    exact = sum(1 for r in rows if r["ok"])
    return {
        "n_cases": len(rows),
        "exact_match_cases": exact,
        "tp_use": tp,
        "fp_use": fp,
        "fn_use": fn,
        "tn_use": tn,
        "precision_use": precision,
        "recall_use": recall,
        "all_exact": exact == len(rows) and not mismatches,
        "mismatches": mismatches,
        "rows": rows,
    }
