"""AUD-0043 constants and catalog contract strings."""

from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "AUD-0043"
OUT_REL = "command-center/audit/AUD-0043-ci-local-invocation-parity.json"
SCHEMA_REL = "command-center/schema/audit-detector-control.schema.json"
PKG_REL = "command-center/p2-wave/probes/AUD-0043/pkg"
WHEELS_REL = "command-center/p2-wave/probes/AUD-0043/wheels"
INVENTORY_REL = "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json"
CONSOLE_NAME = "aud0043-suite"
INCLUDE_GOOD = 'include = ["aud0043_pkg*", "aud0043_extra*"]'
INCLUDE_MUTANT = 'include = ["aud0043_pkg*"]'
SENTINEL = (
    "SUCCESS:AUD-0043 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "Does running the suite the way CI does (installed console script, "
    "installed package) produce the same result as running it the way the "
    "baseline did (python -m pytest against the source tree)?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0043/probe1_source_pytest.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0043/probe2_installed_console.py"
)
