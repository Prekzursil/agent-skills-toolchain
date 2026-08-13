"""Is the shipped in-suite control VACUOUS?

The parent's question: "would it look identical under both hypotheses?"
So build H2 explicitly -- a detector that merely NOTICES digits without comparing
them -- and require the shipped control to REJECT it. A control that passes under
H2 as well as H1 is inert.
"""
import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path("C:/Users/Prekzursil/source/ast-integrate")
GATE = ROOT / "ci" / "tests" / "test_docs_executable_claims.py"
spec = importlib.util.spec_from_file_location("gate", GATE)
gate = importlib.util.module_from_spec(spec)
sys.modules["gate"] = gate
spec.loader.exec_module(gate)

div = gate.measured_skill_root_divergence()
CLAIM = gate._PROJECTION_CLAIM


def h1_shipped(roadmap, divergence):
    return gate.roadmap_violations(roadmap, divergence)


def h2_notices_digits(roadmap, divergence):
    """H2: fires only when the claim is ABSENT; never compares the numbers."""
    return [] if CLAIM.search(roadmap) else ["projection-claim-missing: (h2)"]


def h3_always_silent(roadmap, divergence):
    return []


def run_shipped_control(impl):
    """Re-run the body of test_control_roadmap_arm_distinguishes_parity_from_divergence."""
    claims_parity = ("- `skills/` - 0 skill names live only in `skills/` and 0 only in "
                     "`.agents/skills/`, so it is a true generated projection.\n")
    truthful = (f"- `skills/` - {div['only_projection']} skill names live only in "
                f"`skills/` and {div['only_canonical']} only in "
                "`.agents/skills/`, so the projection is not complete.\n")
    try:
        assert impl(claims_parity, div), "parity-doc did not fire"
        assert impl(truthful, div) == [], "truthful-doc fired"
        return "PASS"
    except AssertionError as e:
        return f"FAIL ({e})"


def run_deleted_control(impl):
    deleted = CLAIM.sub("the roots are in sync", (ROOT / "docs/roadmap.md").read_text(encoding="utf-8"))
    return "PASS" if any("projection-claim-missing" in v for v in impl(deleted, div)) else "FAIL"


print(f"measured divergence: only_proj={div['only_projection']} only_canon={div['only_canonical']}")
print()
print("control: distinguishes_parity_from_divergence")
for name, impl in (("H1 shipped (compares)", h1_shipped),
                   ("H2 merely-notices-digits", h2_notices_digits),
                   ("H3 always-silent", h3_always_silent)):
    print(f"   {name:28s} -> {run_shipped_control(impl)}")
print()
print("control: fires_when_claim_deleted_or_unparseable")
for name, impl in (("H1 shipped (compares)", h1_shipped),
                   ("H2 merely-notices-digits", h2_notices_digits),
                   ("H3 always-silent", h3_always_silent)):
    print(f"   {name:28s} -> {run_deleted_control(impl)}")

h1 = run_shipped_control(h1_shipped)
h2 = run_shipped_control(h2_notices_digits)
h3 = run_shipped_control(h3_always_silent)
discriminating = h1 == "PASS" and h2.startswith("FAIL") and h3.startswith("FAIL")
print()
print(("SUCCESS:advver-vacuity control DISCRIMINATES (H1 pass, H2/H3 fail)"
       if discriminating else
       "FAILED:advver-vacuity control is INERT -- looks the same under both hypotheses"))
sys.exit(0 if discriminating else 1)
