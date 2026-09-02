"""CNF-0010 shared contract constants."""

from __future__ import annotations

UNIT_ID = "CNF-0010"
OUT_REL = "command-center/confirmation/CNF-0010-environment-manifest.json"
SCHEMA_REL = "command-center/schema/environment-manifest.schema.json"
INVENTORY_REL = "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json"
SENTINEL = "SUCCESS:CNF-0010"
COMPLETION_SENTINEL = (
    "SUCCESS:CNF-0010 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and manifests from two "
    "different operating systems are attached and the forced-mismatch control "
    "was attributed to environment. Any other terminal state is "
    "FAILED:CNF-0010 <classification> with the diagnostic tail attached."
)
QUESTION = (
    "When a confirmer and an implementer disagree, was it the code or the "
    "environment? Capture a pinned manifest per confirmation run and count "
    "how many disagreements in the corpus are explained by a manifest delta alone."
)
NAMED_TOOLS = (
    "python3",
    "python",
    "node",
    "git",
    "ruff",
    "basedpyright",
    "pwsh",
    "bash",
)
FORMATTER_LINTER_NAMES = ("ruff", "basedpyright")
CI_RUFF_PIN = "0.15.17"
FORCED_RUFF = "0.15.22"
WINDOWS_RECORDED_RUFF = "0.15.22"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0010/probe1_resolver_and_pin_parity.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0010/probe2_forced_mismatch.py"
)
