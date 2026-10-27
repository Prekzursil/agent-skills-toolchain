"""IMP-0071 probe 2 (verifier): a channel-pinned client resolves only within
its channel across the 10-case pin matrix; cross-channel resolution refuses.

Re-run: python command-center/p2-wave/probes/IMP-0071/probe2_channel_pin_matrix.py
Exit 0 iff 10/10 matrix cases behave as declared.
"""
import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools"))
sys.path.insert(0, str(W / "tools" / "marketplace"))
from channels import CONDITION_13_STATUS, run_pin_matrix  # noqa: E402

matrix = run_pin_matrix()
result = {
    "cases": matrix["cases"],
    "passed": matrix["passed"],
    "failed": matrix["failed"],
    "condition_13_status": CONDITION_13_STATUS,
    "results": matrix["results"],
    "unit_id": "IMP-0071",
}
result["pass"] = matrix["pass"] and matrix["cases"] == 10 and matrix["passed"] == 10
print(json.dumps(result, indent=1))
if result["pass"]:
    print("SUCCESS:IMP-0071-probe2 channel pin matrix 10/10 with cross-channel refusal")
else:
    print("FAILED:IMP-0071-probe2")
sys.exit(0 if result["pass"] else 1)
