"""WFA-0152 constants. Catalog output_path is the foundry pack-contract artifact."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT_ID = "WFA-0152"
COMPLETION_SENTINEL = "SUCCESS:WFA-0152"
OUTPUT_REL = (
    "command-center/foundry/"
    "WFA-0152-workflow-pack-packaging-versioning-and-publication-c.json"
)
SCHEMA_REL = "command-center/p2-wave/probes/WFA-0152/pack-contract.schema.json"
DECLARED_SCHEMA = "command-center/schema/foundry-artifact.schema.json#/$defs/pack-contract"
CHANNELS = ("stable", "beta", "nightly")
SOURCE_POLICY_RANK = {"deny-all": 0, "allow-listed": 1, "unrestricted": 2}
BUMP_RANK = {"patch": 0, "minor": 1, "major": 2}
EXCLUDED_PACK_PATHS = (".git/", ".git", "__pycache__/", ".cache/", "transcripts/", ".env")
