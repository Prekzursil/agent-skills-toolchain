"""Shared constants for ADV-0047 post-uninstall residue audit."""
from __future__ import annotations

UNIT_ID = "ADV-0047"
OUTPUT_REL = "command-center/adversarial/ADV-0047-post-uninstall-residue-audit.json"
SCHEMA_REL = "command-center/schema/privacy-dataflow.schema.json"
COMPLETION_SENTINEL = (
    "SUCCESS:ADV-0047 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0047 <reason>."
)
QUESTION = (
    "After uninstall, what remains on disk or in the user profile - caches, "
    "logs, transcripts, credentials, registry keys, scheduled tasks, MCP "
    "registrations - and is any of it privacy-relevant or capable of "
    "re-activating the software?"
)
PROFILE_USER = "ADV0047Fresh"
PACKAGE_ID = "adv0047-keepalive"
SYNTHETIC_TOKEN = "ADV0047-SYNTHETIC-NOT-A-SECRET"
USER_NOTE = "owner-authored note that uninstall must retain"
UNRELATED_MCP = "unrelated-weather"
HOOK_ID = "hook.session-start"
TASK_ID = "adv0047-keepalive"
REGISTRY_KEY = r"HKCU\Software\Harness\ADV0047"
LEGAL_VERDICTS = frozenset(
    {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}
)
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0047/probe1_snapshot_diff.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0047/probe2_behavioral.py"
)
