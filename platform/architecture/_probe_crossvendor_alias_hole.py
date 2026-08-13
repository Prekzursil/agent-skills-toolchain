"""Does the EXISTING cross-vendor gate survive a vendor ALIAS?

`completion_predicate.py:_c9_reviewer` enforces cross-vendor review by STRING EQUALITY:
    if rev_vendor == exec_vendor: -> FAIL "same-vendor reviewer inherits blind spots"
and `receipt.schema.json` types both `produced_by.vendor` and `reviewer.vendor` as a free
`{"type":"string","maxLength":64}` with NO enum and NO normalization.

Hypothesis under test: two spellings of the SAME vendor compare unequal, so a same-vendor
review is accepted as cross-vendor. If true this is a live soundness hole in the strongest
gate Wave 1 shipped, and it is the concrete defect the cross-vendor adapter's identity
plane exists to close.

DETECTOR CONTROL (both states):
  known-BROKEN : identical spellings MUST be rejected (proves the gate is wired at all).
  known-GOOD   : a genuinely different vendor MUST be accepted (proves it is not just always-fail).
A probe that returns the same verdict for all three inputs measures nothing.

Run:  python platform/architecture/_probe_crossvendor_alias_hole.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "platform", "lib"))

import completion_predicate as cp  # noqa: E402

# Aliases that any human would agree name the SAME vendor / the same model family.
ALIAS_PAIRS = [
    ("anthropic", "Anthropic"),        # case
    ("anthropic", "anthropic "),       # trailing space
    ("anthropic", "claude"),           # vendor vs its product line
    ("anthropic", "ANTHROPIC"),
    ("openai", "OpenAI"),
    ("openai", "codex"),               # vendor vs its CLI/product
    ("openai", "gpt"),
    ("anthropic", "anthropic.com"),
    ("google", "Google"),
    ("google", "gemini"),
]
CONTROL_SAME = ("anthropic", "anthropic")
CONTROL_DIFF = ("anthropic", "openai")


def gate(exec_vendor, rev_vendor):
    """Run ONLY condition 9 with cross-vendor required. Returns (ok, reason)."""
    receipt = {
        "produced_by": {"vendor": exec_vendor, "model": "m", "role": "implementer"},
        "reviewer": {
            "reviewer_id": "reviewer-1",
            "verdict": "PASS",
            "independent": True,
            "vendor": rev_vendor,
            "fresh_context": True,
        },
    }
    opts = cp.PredicateOptions(
        repo_root=Path(REPO), require_cross_vendor_review=True
    )
    outcome, reason, _detail = cp._c9_reviewer(receipt, opts)
    # "accepted as cross-vendor" == condition 9 SATISFIED.
    return outcome is cp.Outcome.SATISFIED, "%s: %s" % (outcome.value, reason)


out = {"gate": "completion_predicate._c9_reviewer with require_cross_vendor_review=True"}

# ---- controls first (rule 3: validate the detector before trusting a result)
same_ok, same_reason = gate(*CONTROL_SAME)
diff_ok, diff_reason = gate(*CONTROL_DIFF)
out["control_known_broken_identical_vendor"] = {
    "input": CONTROL_SAME, "accepted": same_ok, "reason": same_reason[:160],
    "expected": "rejected", "control_passes": same_ok is False,
}
out["control_known_good_distinct_vendor"] = {
    "input": CONTROL_DIFF, "accepted": diff_ok, "reason": diff_reason[:160],
    "expected": "accepted", "control_passes": diff_ok is True,
}
out["detector_validated_both_states"] = bool(same_ok is False and diff_ok is True)

# ---- the actual question
leaks = []
held = []
for a, b in ALIAS_PAIRS:
    ok, reason = gate(a, b)
    rec = {"executor_vendor": a, "reviewer_vendor": b, "accepted_as_cross_vendor": ok}
    if ok:
        leaks.append(rec)
    else:
        held.append(rec)

out["alias_pairs_tested"] = len(ALIAS_PAIRS)
out["alias_pairs_that_DEFEAT_the_gate"] = len(leaks)
out["alias_leaks"] = leaks
out["alias_pairs_gate_held"] = held

if not out["detector_validated_both_states"]:
    out["VERDICT"] = "DETECTOR INVALID - do not cite"
elif leaks:
    out["VERDICT"] = (
        "CONFIRMED HOLE: %d/%d same-vendor alias pairs are accepted as cross-vendor. "
        "The gate is string-equality over an unvalidated free-text field."
        % (len(leaks), len(ALIAS_PAIRS))
    )
else:
    out["VERDICT"] = "REFUTED: the gate normalizes vendor identity already"

print(json.dumps(out, indent=2, default=str))
marker = "SUCCESS" if out["detector_validated_both_states"] else "FAILED"
sys.stdout.write("\n%s:crossvendor-alias-hole\n" % marker)
