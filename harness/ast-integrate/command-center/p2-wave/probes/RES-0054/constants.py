"""Shared constants for RES-0054."""

UNIT_ID = "RES-0054"
CATALOG_SENTINEL = (
    "SUCCESS:RES-0054 in the receipt AND a defense table with an "
    "automatable/moderation-dependent column and at least one of each"
)
OUTPUT_REL = "command-center/research/RES-0054.json"
SCHEMA_REL = "command-center/schema/threat-model.schema.json"
CAPTURE_REL = "command-center/p2-wave/probes/RES-0054/captures"
CLASS_KEY = "automatable/moderation-dependent"
AUTOMATABLE = "automatable"
MODERATION = "moderation-dependent"
NAMED_DEFENSES = (
    "scoped names",
    "verified publishers",
    "reserved prefixes",
    "typo-distance blocking",
)
