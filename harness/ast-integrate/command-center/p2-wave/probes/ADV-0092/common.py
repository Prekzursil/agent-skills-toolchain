"""Constants for ADV-0092 role-collapse differentiation."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "ADV-0092"
OUTPUT_REL = "command-center/adversarial/ADV-0092-role-collapse-differentiation.json"
DECLARED_SCHEMA = "command-center/schema/council-pathology-sim.schema.json"
LOCAL_SCHEMA = "command-center/p2-wave/probes/ADV-0092/artifact.schema.json"
TARGET_ID = "five-role-first-round-behavioural-differentiation"
ROLES = ("advocate", "skeptic", "domain_expert", "user_proxy", "judge")
STANCE_AXES = ("recommendation", "burden", "certainty", "frame")
CHANCE_ACCURACY = 1.0 / len(ROLES)
MAX_COLLAPSED_DIVERGENCE = 0.35
MIN_DIVERSE_DIVERGENCE = 0.55
MIN_MARGIN = 0.25
BINOMIAL_ALPHA = 0.05
COMPLETION_SENTINEL = (
    "SUCCESS:ADV-0092 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0092 <reason>."
)
QUESTION = (
    "Do participants assigned different roles produce measurably different "
    "content, or do they converge on one voice with different labels?"
)
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0092/probe1_divergence.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0092/probe2_attribution.py"
)
LEGAL_VERDICTS = frozenset(
    {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}
)
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
INVENTORY_RULE = (
    "exactly five produced briefs with text and one distinct assigned role "
    "from advocate,skeptic,domain_expert,user_proxy,judge"
)
