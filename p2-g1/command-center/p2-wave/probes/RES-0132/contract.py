"""RES-0132 catalog contract constants."""
from __future__ import annotations

UNIT_ID = "RES-0132"
OUTPUT_REL = (
    "command-center/research/supply-chain/"
    "RES-0132-advisory-green-decay-measurement.json"
)
SCHEMA_REL = "command-center/schema/measurement-run.schema.json"
SENTINEL = "SUCCESS:RES-0132"
QUESTION = (
    "How fast does a stored-green osv-scanner / pip-audit result decay, "
    "measured by re-running a frozen lockfile against the live advisory DB "
    "at T+0, T+7d and T+30d, and what is the verdict-flip rate and the "
    "median lag from advisory publication to scanner verdict flip?"
)
TITLE = "Measure decay of a stored-green vulnerability scan"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0132/probe1_cadence_flips.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0132/probe2_control_red.py"
)
FETCHED_AT = "2026-08-24T20:48:42Z"
OSV_QUERYBATCH = "https://api.osv.dev/v1/querybatch"
OSV_VULN = "https://api.osv.dev/v1/vulns/{id}"
GITHUB_ADV = "https://api.github.com/advisories/{id}"
