"""RES-0105 catalog contract constants."""
from __future__ import annotations

UNIT_ID = "RES-0105"
OUTPUT_REL = "command-center/research/RES-0105.json"
SCHEMA_REL = "command-center/schema/measurement-run.schema.json"
SENTINEL = (
    "SUCCESS:RES-0105 in the receipt AND a per-strategy wrong-selection "
    "count on one shared task set, including a random baseline"
)
QUESTION = (
    "When two skills claim the same trigger, what resolution strategies "
    "exist (specificity, scope depth, explicit priority, ask the user), "
    "and which produces the fewest wrong selections on the fixed routing "
    "task set?"
)
TITLE = "Define conflict resolution when two capabilities both match a request"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0105/probe1_shared_task_set.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0105/probe2_detector_control.py"
)
ASK = "ASK_USER"
NAMED_STRATEGIES = (
    "specificity",
    "scope_depth",
    "explicit_priority",
    "ask_the_user",
)
ALL_STRATEGIES = NAMED_STRATEGIES + ("random",)

UNIT_ID = UNIT_ID
OUTPUT_REL = OUTPUT_REL
SCHEMA_REL = SCHEMA_REL
