"""RES-0187 paths, sentinel, and named-probe commands."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "RES-0187"
OUT_REL = "command-center/research/evidence-quality/RES-0187-counterevidence-coverage-audit.json"
SCHEMA_REL = "command-center/schema/measurement-run.schema.json"
SENTINEL = (
    "SUCCESS:RES-0187 emitted only when the artifact at output_path exists, "
    "is non-empty, parses, is not self-declared BLOCKED, and both named "
    "probes re-run exit 0"
)
CATALOG_SNIPPET = (
    "a conclusion counts as challenged only if a recorded query, "
    "its result set and a verdict exist"
)
HEDGE_RULE = (
    "a hedging phrase in the prose does not count and the audit must state that rule"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0187/probe1_however_negative_control.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0187/probe2_recorded_triple_and_recount.py"
)
QUESTION = (
    "Audit the program's conclusions for whether a disconfirming search was "
    "actually RUN and RECORDED for each - not whether a caveat sentence exists "
    "- and report the coverage fraction plus the list of conclusions that have "
    "never been challenged. Distinct from RES-0022 (hunts doc-versus-behaviour "
    "contradictions in the client)."
)
ABSENT_INPUTS = (
    "_USER-PROMPTS.md",
    "command-center/sources/REGISTER.md",
    "command-center/CLAIM-REGISTRY.json",
    "rules/common/single-signal-verification.md",
)
RESEARCH_ROOT = "command-center/research"
SKIP_NAMES = frozenset({"RES-0187-counterevidence-coverage-audit.json"})
