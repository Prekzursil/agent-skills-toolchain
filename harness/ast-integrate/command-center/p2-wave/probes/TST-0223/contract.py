"""TST-0223 catalog contract constants."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SPEC_ROOT = REPO / "tools" / "agentspec"
UNIT = "TST-0223"
OUT_REL = "command-center/receipts/TST-0223.json"
SCHEMA_REL = "command-center/p2-wave/probes/TST-0223/security_report.schema.json"
SENTINEL = "SUCCESS:TST-0223"
QUESTION = (
    "Can a subworkflow obtain a permission its parent lacks, via nesting, "
    "re-entry or a preset? PASS requires a monotone-narrowing property "
    "proven over randomized nesting trees."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0223/probe1_property_trees.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0223/probe2_mutation_widen.py"
)
NAMED_INPUTS = (
    "tools/lib/workspace.mjs",
    "tools/lib/net-allowlist.mjs",
    "tools/agentspec/agentspec/subworkflow_executor.py",
    "tools/agentspec/agentspec/permission_bound.py",
    "tools/agentspec/agentspec/dispatchpolicy.py",
)
