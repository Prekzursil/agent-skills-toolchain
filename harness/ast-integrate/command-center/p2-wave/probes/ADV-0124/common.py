"""ADV-0124 shared constants. Catalog completion_sentinel is copied verbatim."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT_ID = "ADV-0124"
OUT_REL = "command-center/adversarial/ADV-0124-monitor-liveness-four-state-matrix.json"
SCHEMA_DECLARED = "command-center/schema/fault-injection-run.schema.json"
LOCAL_SCHEMA = HERE / "fault-injection-run.schema.json"

SENTINEL = (
    "SUCCESS:ADV-0124 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0124 <reason>."
)

QUESTION = (
    "Does the monitor correctly distinguish these four states - work running "
    "with monitor alive, work running with monitor dead, work finished, and "
    "work genuinely stalled - or does it conflate any pair?"
)

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0124/probe1_four_state_matrix.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0124/probe2_signal_source_audit.py"
)

TRUTH_S1 = "RUNNING_MONITOR_ALIVE"
TRUTH_S2 = "RUNNING_MONITOR_DEAD"
TRUTH_S3 = "FINISHED"
TRUTH_S4 = "STALLED"
FOUR_TRUTHS = (TRUTH_S1, TRUTH_S2, TRUTH_S3, TRUTH_S4)

COMPLETE = b"\nADV-0124-COMPLETE\n"
ELEVEN_H = 11 * 3600

PRODUCTION_ABSENT = (
    "platform/coordination/session.py",
    "platform/coordination/oslock.py",
    "tools/monitorcore",
    "tools/monitorcore/__init__.py",
)
