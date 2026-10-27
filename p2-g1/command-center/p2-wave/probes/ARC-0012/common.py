"""ARC-0012 shared constants."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT_ID = "ARC-0012"
OUT_REL = "command-center/phase3/A2/FAILURE-MODES.json"
SENTINEL = "SUCCESS:ARC-0012"

REGISTRY = REPO / "command-center/p2-wave/probes/ARC-0010/registry.json"
GENERATED_ROOT = REPO / "command-center/control-plane/A2/generated"

# A2 design mapping (as recorded in the artifact's direction-A orphan rows).
MAPPING = {
    "plugin_manifest": "plugin/{id}.json",
    "marketplace_entry": "marketplace/{id}.json",
    "skill": "skills/{id}.json",
    "hook": "hooks/{id}.json",
    "rule": "rules/{id}.json",
    "doc": "docs/{id}.md",
    "workflow_blueprint": "workflows/{id}.json",
    "workflow_catalog": "workflows/{id}.json",
    "council_preset": "council/{id}.json",
    "council_catalog": "catalogs/{id}.json",
}


def expected_rel(entry: dict) -> str:
    kind = str(entry.get("kind") or "")
    tpl = MAPPING.get(kind)
    if tpl is None:
        raise ValueError(f"unmapped kind {kind!r}")
    return tpl.format(id=entry.get("id"))


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT_ID} {msg}")
    return 1
