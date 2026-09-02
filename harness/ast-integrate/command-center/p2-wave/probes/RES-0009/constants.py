"""Shared constants for RES-0009 hook-contract mapping."""

UNIT_ID = "RES-0009"
OUTPUT_REL = "command-center/research/RES-0009.json"
SCHEMA_REL = "command-center/schema/research-claim-record.schema.json"
SENTINEL = (
    "SUCCESS:RES-0009 in the receipt AND one captured raw payload per "
    "supported event plus an observed block/inject/timeout transcript"
)
SHORT_SENTINEL = "SUCCESS:RES-0009"
BLOCK_STDERR = "RES-0009-BLOCK-STDERR"
INJECT_MARKER = "RES-0009-INJECT-MARKER"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0009/probe1_raw_payloads.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0009/probe2_block_inject_timeout.py"
)
