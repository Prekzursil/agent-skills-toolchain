"""IMP-0201 probe 2 (source): delta recomputed from per-case ROWS.

delta_from_rows recomputes mean_delta from the per-case rows (it has no
summary parameter to misuse). Stored summaries 999 and 1 would have
produced -998 if trusted; the row-recomputed delta is -20/4 = -5.0. A
summary-only freeze is refused with SUMMARY_ONLY_REFUSED - a digest is a
claim, not a receipt.

Exit 0 iff both recompute paths agree and the summary-only freeze refuses.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE
for _ in range(6):
    if (REPO / "command-center" / "p2-wave").is_dir():
        break
    REPO = REPO.parent
for _p in (str(REPO), str(REPO / "tools" / "agentspec")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from agentspec.evals.baseline import (  # noqa: E402
    compare_to_baseline,
    delta_from_rows,
    freeze_baseline,
)

baseline = json.loads((HERE / "fixtures" / "baseline-certified.json").read_text(encoding="utf-8"))
same = json.loads((HERE / "fixtures" / "run-same-corpus.json").read_text(encoding="utf-8"))
summary_only = json.loads((HERE / "fixtures" / "baseline-summary-only.json").read_text(encoding="utf-8"))

row_delta = delta_from_rows(same["per_case_rows"], baseline["per_case_rows"])
cmp_delta = compare_to_baseline(same, baseline)

refused = freeze_baseline(summary_only)
accepted_freeze = freeze_baseline(baseline)

checks = {
    "row_delta_is_minus_5": row_delta.get("mean_delta") == -5.0,
    "numerator_denominator": row_delta.get("mean_delta_numerator") == -20
        and row_delta.get("mean_delta_denominator") == 4,
    "n_cases_4": row_delta.get("n_cases") == 4,
    "summary_not_consulted": row_delta.get("summary_consulted") is False,
    "compare_path_agrees": cmp_delta.get("mean_delta") == row_delta.get("mean_delta"),
    "would_have_been_minus_998": (1 - 999) == -998,
    "summary_only_freeze_refused": bool(refused.get("refused"))
        and refused.get("reason") == "SUMMARY_ONLY_REFUSED",
    "rowful_freeze_accepted": accepted_freeze.get("ok") is True
        and accepted_freeze.get("n_cases") == 4,
    "no_summary_parameter": "summary" not in delta_from_rows.__code__.co_varnames,
}

result = {
    "probe": "probe2-per-case-delta",
    "unit_id": "IMP-0201",
    "checks": checks,
    "row_delta": row_delta,
    "compare_delta": {k: cmp_delta.get(k) for k in ("mean_delta", "n_cases", "summary_consulted")},
    "summary_only_refusal": refused,
    "freeze": {"ok": accepted_freeze.get("ok"), "n_cases": accepted_freeze.get("n_cases")},
    "pass": all(checks.values()),
}
print(json.dumps(result, sort_keys=True))
if not result["pass"]:
    print("FAILED:IMP-0201-probe2 " + ",".join(k for k, v in checks.items() if not v))
    raise SystemExit(1)
print("SUCCESS:IMP-0201-probe2 delta recomputed from rows; summary-only freeze refused")
