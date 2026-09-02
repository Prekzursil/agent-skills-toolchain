"""AUD-0095 freeze-inventory contract constants."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "AUD-0095"
OUT_REL = "command-center/audit/AUD-0095-freeze-inventory.json"
SCHEMA_REL = "command-center/schema/audit-inventory.schema.json"
SENTINEL = (
    "SUCCESS:AUD-0095 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
TITLE = "Launcher and schema freeze inventory with a versioned-migration requirement"
QUESTION = (
    "Which launchers, prompt templates, and schemas must be frozen the moment "
    "the first implementation wave starts, and what is the exact "
    "versioned-migration procedure for changing each one afterwards?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0095/probe1_freeze_anchors.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0095/probe2_change_detection.py"
)

SKIP_PARTS = frozenset(
    {
        "__pycache__",
        ".git",
        "node_modules",
        "probes",
        ".bin",
        "runtime",
        "scratch",
        "fixtures",
        "catalog-slices",
    }
)

NAMED_REQUIRED: tuple[tuple[str, str, str], ...] = (
    (
        "_USER-PROMPTS.md",
        "prompt-template",
        "spec :10660 source (freeze launchers and schemas at first implementation wave)",
    ),
    (
        "rules/common/fan-out-contract.md",
        "prompt-template",
        "A10: freeze the preamble once the first unit launches",
    ),
    (
        "hooks/_dispatch/manifest.json",
        "launcher-or-dispatcher",
        "hook dispatcher entry point",
    ),
    (
        "AGENTS.md",
        "prompt-template",
        "live agent preamble; mid-run edit left contradictory instructions",
    ),
)

CLI_LAUNCHERS: tuple[str, ...] = ("tools/command-center/seed.py",)
