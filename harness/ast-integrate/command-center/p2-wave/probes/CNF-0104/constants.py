"""Shared fixture bytes and catalog strings for CNF-0104."""
from __future__ import annotations

UNIT_ID = "CNF-0104"
OUT_REL = "command-center/confirmation/CNF-0104-case-collision.json"
SCHEMA_REL = "command-center/schema/platform-report.schema.json"

COMPLETION_SENTINEL = (
    "SUCCESS:CNF-0104 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both filesystem classes "
    "were exercised and the non-colliding control survived on each. Any other "
    "terminal state is FAILED:CNF-0104 <classification> with the diagnostic "
    "tail attached."
)

QUESTION = (
    "What happens when two names differ only in case? Create case-distinct "
    "file names and case-distinct JSON keys and answer: does the installer "
    "overwrite one with the other, does the parser silently keep only one key, "
    "and does the behaviour differ between the case-insensitive and "
    "case-sensitive filesystems in the support matrix?"
)

COLLIDE_UPPER_NAME = "Config.json"
COLLIDE_LOWER_NAME = "config.json"
CONTROL_ALPHA_NAME = "alpha.json"
CONTROL_BETA_NAME = "beta.json"

COLLIDE_UPPER = b"CNF-0104-UPPER-CONFIG\n"
COLLIDE_LOWER = b"CNF-0104-LOWER-config\n"
CONTROL_ALPHA = b"CNF-0104-CONTROL-alpha\n"
CONTROL_BETA = b"CNF-0104-CONTROL-beta\n"

INSTALLER_ID = "freeze_hook.deploy_write"
PARSER_ID = "json.loads"
