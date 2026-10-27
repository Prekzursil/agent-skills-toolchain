"""IMP-0201 probe 1 (source, both-states): cross-corpus comparison REFUSED.

A run captured under a DIFFERENT corpus_version is refused with the named
reason CROSS_CORPUS_REFUSED; the SAME per-case rows under the baseline
corpus_version are compared (delta computed from rows). The known-broken
control sibling with the corpus gate removed WOULD accept the pair, so the
corpus gate is load-bearing. A spec_version bump is refused separately.

Exit 0 iff refusal, acceptance, and control all hold.
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
    compare_ignoring_corpus_for_control,
    compare_to_baseline,
)

baseline = json.loads((HERE / "fixtures" / "baseline-certified.json").read_text(encoding="utf-8"))
cross = json.loads((HERE / "fixtures" / "run-cross-corpus.json").read_text(encoding="utf-8"))
same = json.loads((HERE / "fixtures" / "run-same-corpus.json").read_text(encoding="utf-8"))
spec_mm = json.loads((HERE / "fixtures" / "run-spec-mismatch.json").read_text(encoding="utf-8"))

refused = compare_to_baseline(cross, baseline)
accepted = compare_to_baseline(same, baseline)
control = compare_ignoring_corpus_for_control(cross, baseline)
spec_refused = compare_to_baseline(spec_mm, baseline)

checks = {
    "cross_corpus_refused": bool(refused.get("refused")) and refused.get("ok") is False,
    "named_reason": refused.get("reason") == "CROSS_CORPUS_REFUSED",
    "detail_names_both_versions": (
        "corpus.v2.retargeted" in str(refused.get("detail"))
        and "corpus.v1.matched-holdout" in str(refused.get("detail"))
    ),
    "same_corpus_accepted": accepted.get("ok") is True and accepted.get("refused") is False,
    "same_corpus_delta_from_rows": (
        accepted.get("mean_delta") == -5.0
        and accepted.get("mean_delta_numerator") == -20
        and accepted.get("mean_delta_denominator") == 4
    ),
    "summary_not_consulted": accepted.get("summary_consulted") is False,
    "control_sibling_would_accept": control.get("good_ok") is True
        and control.get("ungated_ok") is True,
    "spec_gate_still_on_in_control": control.get("spec_reason") == "",
    "spec_mismatch_refused": spec_refused.get("reason") == "SPEC_VERSION_MISMATCH_REFUSED",
    "both_states": bool(refused.get("refused")) and accepted.get("ok") is True,
}

result = {
    "probe": "probe1-cross-corpus",
    "unit_id": "IMP-0201",
    "checks": checks,
    "refused": refused,
    "accepted": accepted,
    "control": control,
    "spec_refused": spec_refused,
    "pass": all(checks.values()),
}
print(json.dumps(result, sort_keys=True))
if not result["pass"]:
    print("FAILED:IMP-0201-probe1 " + ",".join(k for k, v in checks.items() if not v))
    raise SystemExit(1)
print("SUCCESS:IMP-0201-probe1 cross-corpus refused with named reason; same-corpus compared")
