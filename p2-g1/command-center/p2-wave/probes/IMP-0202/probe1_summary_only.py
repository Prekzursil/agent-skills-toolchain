"""IMP-0202 probe 1 (source, both-states): a summary-only confirmation is
REJECTED by the gate; a same-author confirmation is rejected as not
independent; a raw-citing confirmation recomputes the digest and is ACCEPTED.

Exit 0 iff all three states hold.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from confirmation_hook import confirm  # noqa: E402

RAW = HERE / "probe1-summary-only.raw.txt"
claimed = json.loads((HERE / "claim.json").read_text(encoding="utf-8"))

summary_only = confirm({
    "author_id": "wf-author", "reviewer_id": "fresh-reviewer",
    "citations": {"summary": ["author_summary.json"]},
    "claimed_digest": claimed["claimed_digest"],
}, workspace=HERE)

same_author = confirm({
    "author_id": "wf-author", "reviewer_id": "wf-author",
    "citations": {"raw": ["raw/per_case_rows.json"]},
    "claimed_digest": claimed["claimed_digest"],
}, workspace=HERE)

artifact_citing = confirm({
    "author_id": "wf-author", "reviewer_id": "fresh-reviewer",
    "citations": {"raw": ["raw/per_case_rows.json"]},
    "claimed_digest": claimed["claimed_digest"],
}, workspace=HERE)

lines = [json.dumps({"probe": "probe1-summary-only-both-states", "unit_id": "IMP-0202",
                     "summary_only": {"verdict": summary_only["verdict"],
                                      "blocked_by": summary_only.get("blocked_by"),
                                      "reason": summary_only["reason"]},
                     "same_author": {"verdict": same_author["verdict"],
                                     "independent": same_author["independent"],
                                     "reason": same_author["reason"]},
                     "artifact_citing": {"verdict": artifact_citing["verdict"],
                                         "certified": artifact_citing["certified"],
                                         "reason": artifact_citing["reason"],
                                         "raw_citations": artifact_citing.get("raw_citations"),
                                         "recomputed": artifact_citing["recomputed"]},
                     "same_author_rejected": same_author["verdict"] == "REJECT",
                     "citing_accepted": artifact_citing["verdict"] == "ACCEPT",
                     "both_states": True, "pass": True})]
assert summary_only["verdict"] == "REJECT", "summary-only confirmation accepted"
assert summary_only.get("blocked_by") == "independent_confirmation_hook"
assert same_author["verdict"] == "REJECT" and same_author["independent"] is False
assert artifact_citing["verdict"] == "ACCEPT" and artifact_citing["certified"] is True
assert artifact_citing["recomputed"] == {"mean_delta": 0.25, "n": 8, "verdict": "OUTPERFORMS"}
RAW.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
print("RESULT:" + json.dumps({"summary_only_rejected": True,
                              "same_author_rejected": True,
                              "artifact_citing_accepted": True,
                              "recomputed": artifact_citing["recomputed"]}))
print("SUCCESS:IMP-0202-probe1 summary-only rejected, raw-citing accepted")
