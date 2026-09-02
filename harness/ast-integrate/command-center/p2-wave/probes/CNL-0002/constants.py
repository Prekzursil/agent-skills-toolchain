"""Catalog-grounded names for the reconstructed v1 charter schema.

Originals 11-COUNCIL-SPECIFICATION.schema.json and
12-COUNCIL-PROTOCOLS-AND-PRESETS.json are absent on this worktree.
Required-key names are reconstructed from sibling catalog questions
(CNL-0003 charter fields, ADV-0104 harvested required list), not read
from the missing schema file. The criterion depends on KEY-SET
structure (12 required, 0 intersection), not on the specific spellings.
"""
from __future__ import annotations

REQUIRED_12 = (
    "council_id",
    "objective",
    "risk_tier",
    "desired_output",
    "success_criteria",
    "consensus_intent",
    "participants",
    "protocol",
    "voting",
    "stopping",
    "topology",
    "schema_version",
)

# Optional properties that a typical charter instance also carries (13th field).
CHARTER_OPTIONAL = ("meta",)

# Four protocol-record keys that collide with v1 schema.properties so C-M01
# can show "4 of 20 keys recognised" without filling any of the 12 required.
OVERLAP_OPTIONAL = ("id", "title", "description", "status")

CATALOGUE_ROOT_KEYS = ("schema_relationship", "protocols", "presets")

CM01_UNRECOGNISED = (
    "name",
    "protocol_class",
    "roles",
    "anti_failure",
    "audit",
    "consensus",
    "discovery_only",
    "version",
    "seats",
    "budgets",
    "evidence",
    "outcomes",
    "integrity",
    "artifacts",
    "execution",
    "bound_preset_ids",
)

PROTOCOL_COUNT = 58
PRESET_COUNT = 72

DISCOVERY_STATUS = "DISCOVERY - no protocol here has been executed"

SCHEMA_RELATIONSHIP_PROSE = (
    "CLAIM-UNDER-TEST: this catalogue is said to produce 13 errors against "
    "the v1 charter schema with 0 of 12 required keys present. Probes must "
    "NOT use this string as the measurement."
)

CHARTER_SCHEMA_ID = (
    "https://ast-integrate.local/command-center/p2-wave/probes/"
    "CNL-0002/fixtures/v1-charter.schema.json"
)
CATALOGUE_SCHEMA_ID = (
    "https://ast-integrate.local/command-center/p2-wave/probes/"
    "CNL-0002/fixtures/catalogue.schema.json"
)
UNION_SCHEMA_ID = (
    "https://ast-integrate.local/command-center/p2-wave/probes/"
    "CNL-0002/fixtures/tagged-union.schema.json"
)

# Catalog-named originals only. platform/schema/councilspec.schema.json is a
# later CouncilSpec, not 11-COUNCIL-SPECIFICATION.schema.json; listing it here
# made any_present true on this worktree and blocked a reconstructed fixture.
ORIGIN_CANDIDATES = (
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
    "11-COUNCIL-SPECIFICATION.schema.json",
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "11-COUNCIL-SPECIFICATION.schema.json",
    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "command-center/sources/11-COUNCIL-SPECIFICATION.schema.json",
    "command-center/sources/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
)
RELATED_NOT_ORIGIN = (
    "platform/schema/councilspec.schema.json",
    "tools/council/schema/councilspec.schema.json",
)
