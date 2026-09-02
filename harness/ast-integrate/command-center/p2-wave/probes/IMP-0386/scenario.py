"""IMP-0386 fixture map and live-normalize helper."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.router import normalize as N  # noqa: E402

SENTINEL = "SENTINEL:IMP-0386:CAPABILITY-RECORD-NORMALIZED"
ART_REL = "command-center/receipts/IMP-0386.json"
SCHEMA_REL = "command-center/schema/capability-record.schema.json"
SCHEMA_ROOT_REL = "schema/capability-record.schema.json"
NORMALIZER_REL = "tools/router/normalize.py"

FIXTURE_RELS = {
    N.FORMAT_SKILL_MD: "command-center/p2-wave/probes/IMP-0386/fixtures/skill/SKILL.md",
    N.FORMAT_PLUGIN_JSON: "command-center/p2-wave/probes/IMP-0386/fixtures/plugin/plugin.json",
    N.FORMAT_WORKFLOW_HEADER: "command-center/p2-wave/probes/IMP-0386/fixtures/workflow/catalog_discovery.py",
    N.FORMAT_MCP_TOOL: "command-center/p2-wave/probes/IMP-0386/fixtures/mcp/get_weather.json",
}

HEADLINE_DROP = {
    "source_format": N.FORMAT_MCP_TOOL,
    "source_key": "inputSchema",
    "why": (
        "MCP tool JSON-Schema carries the entire argument contract in inputSchema; "
        "CapabilityRecord has no destination for a JSON Schema, so the field is "
        "registered rather than copied."
    ),
}


def capability_record_schema() -> dict:
    """Load the CapabilityRecord definition (repo schema, not the generated shim)."""
    for rel in (SCHEMA_ROOT_REL, SCHEMA_REL):
        path = REPO / rel
        if not path.is_file():
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(doc, dict):
            continue
        defs = doc.get("definitions") or doc.get("$defs") or {}
        if "CapabilityRecord" in defs:
            if "definitions" not in doc:
                doc = dict(doc)
                doc["definitions"] = defs
            return doc
    raise FileNotFoundError(
        "CapabilityRecord schema missing from "
        f"{SCHEMA_ROOT_REL} and {SCHEMA_REL}"
    )


def fixture_paths() -> dict[str, Path]:
    return {fmt: REPO / rel for fmt, rel in FIXTURE_RELS.items()}


def live_results() -> list[N.NormalizationResult]:
    return [N.normalize_file(path, repo=REPO) for path in fixture_paths().values()]


def locator_points_at_key(locator: str, source_key: str) -> tuple[bool, str]:
    if ":" not in locator:
        return False, "locator-missing-colon"
    rel, _, line_s = locator.rpartition(":")
    try:
        line_no = int(line_s)
    except ValueError:
        return False, "locator-line-not-int"
    path = REPO / rel
    if not path.is_file():
        return False, f"locator-file-missing:{rel}"
    lines = path.read_text(encoding="utf-8").splitlines()
    if line_no < 1 or line_no > len(lines):
        return False, f"locator-line-oob:{line_no}"
    line = lines[line_no - 1]
    if source_key not in line:
        return False, f"key-absent-on-cited-line:{line!r}"
    return True, line.strip()
