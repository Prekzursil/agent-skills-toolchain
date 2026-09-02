"""RES-0024 shared contract constants."""

UNIT = "RES-0024"
OUT_REL = "command-center/research/RES-0024.json"
SENTINEL = (
    "SUCCESS:RES-0024 in the receipt AND a two-shell availability verdict "
    "plus, if present, a version string from an actual invocation"
)
QUESTION = (
    "What is the Gemini CLI extension manifest and context-file surface, "
    "and is the Gemini rail actually available on this box (installed, "
    "authenticated) such that this program may assign work units to it - "
    "or must every Gemini-assigned unit fall back?"
)
SCHEMA_REL = "command-center/schema/research-claim-record.schema.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
