"""Near-zero expectation, frozen BEFORE any extraction.

Catalog evidence_requirement A: citable-benchmark count is expected near
zero because 09-WORKFLOW-BLUEPRINT-LIBRARY.json is discovery_only:true.
A near-zero live result is the honest outcome, not a lane failure. This
module is imported first so the ceiling cannot be rewritten after seeing
counts.
"""
from __future__ import annotations

NEAR_ZERO_EXPECTED = True
NEAR_ZERO_CEILING = 5
CATALOG_EXPECTED_N = 284
NEAR_ZERO_RATIONALE = (
    "09-WORKFLOW-BLUEPRINT-LIBRARY.json is catalog-cited with discovery_only:"
    "true and the honesty block that zero workflows have been executed, "
    "merged, or benchmarked. The unit's evidence_requirement states a "
    "near-zero citable-benchmark count is the honest outcome, not a lane "
    "failure. Recorded here before any candidate row is read so a near-zero "
    "result cannot be reinterpreted after the fact."
)

if not NEAR_ZERO_EXPECTED:
    raise SystemExit("FAILED:WFA-0041 expectation must be stated in advance")
if NEAR_ZERO_CEILING < 0:
    raise SystemExit("FAILED:WFA-0041 near-zero ceiling is not a count")
