"""Normative telemetry/privacy clauses for ARC-0096.

The contract JSON Schema embeds these strings so a later consumer can grep
them, and so probes can prove the artifact is not a vacuous $schema wrapper.
"""

from __future__ import annotations

UNIT_ID = "ARC-0096"
SENTINEL = "SUCCESS:ARC-0096"
SCHEMA_VERSION = "arc-0096.telemetry.v1"
CONTRACT_ID = "ARC-0096"
CONTRACT_REL = "command-center/phase4/contracts/ARC-0096.json"
SCHEMA_URI = "https://ast-integrate.invalid/command-center/phase4/contracts/ARC-0096.json"

EGRESS_RULE = (
    "No telemetry payload may leave the machine without an explicit owner "
    "opt-in recorded in the decision log."
)
DISABLED_RULE = (
    "When telemetry is disabled the system emits literally nothing: no outbound "
    "socket, no queued flush, and no new local telemetry record."
)
LOCAL_VS_EGRESS = (
    "Local-only sink may persist allow-listed events without opt-in when "
    "enabled=true and local_recording=true. Egress (any payload leaving the "
    "machine, including localhost observers used as a sandbox stand-in for a "
    "remote collector) requires enabled=true AND a durable OPT-IN record whose "
    "scope is telemetry-egress. Configuration flags are not evidence of egress."
)
REDACTION_RULE = (
    "Every value is redacted before local persist or egress. Secrets, absolute "
    "paths, and personal data are scrubbed or the event is rejected. A write "
    "that drops the whole event is not redaction; a write that still contains "
    "the planted canary or home path is a leak."
)
RETENTION_RULE = (
    "Local telemetry records are retained at most 14 days then deleted. Egress "
    "copies are not retained on this machine after a successful POST. Disable "
    "does not flush a backlog: there is no backlog."
)
OPT_IN_RULE = (
    "Owner opt-in is an append-only decision-log record with id, ts, owner, "
    "decision=OPT-IN, scope=telemetry-egress, and destination_class. Last "
    "record for that scope wins. OPT-OUT or REVOKED cancels prior OPT-IN. "
    "Absent record defaults to no egress. A test fixture labeled sandbox-only "
    "is not a production owner ruling."
)
RECORDABLE_RULE = (
    "Only allow-listed coded fields may be recorded: schema_version, event_id, "
    "ts, unit_id, contract_id, event_kind, outcome, phase, duration_ms, "
    "probe_id, host_os_family, error_class. Prompts, file contents, env values, "
    "hostnames, usernames, IP addresses, command lines, and free-text payloads "
    "are forbidden."
)
OBSERVATION_RULE = (
    "Egress is verified by an actual network observation (an observer that "
    "accepted a TCP connection), not by reading configuration. A probe silent "
    "in both enabled and disabled states measures nothing."
)

CLAUSE_STRINGS = (
    EGRESS_RULE,
    DISABLED_RULE,
    LOCAL_VS_EGRESS,
    REDACTION_RULE,
    RETENTION_RULE,
    OPT_IN_RULE,
    RECORDABLE_RULE,
    OBSERVATION_RULE,
    SENTINEL,
)
