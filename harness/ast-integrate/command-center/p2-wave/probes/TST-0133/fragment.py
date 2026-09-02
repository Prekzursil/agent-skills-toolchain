"""Install TST-0133's $defs.fault_injection_report into the shared receipt schema.

IMP-0433 rewrote command-center/schema/receipt.schema.json and dropped this
fragment. Catalog output_schema still points at
receipt.schema.json#/$defs/fault_injection_report. Probe 1 KeyError'd on that
missing key. Merge the fragment; do not replace receipt_core or other $defs.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/receipt.schema.json"
FRAG_REL = (
    "command-center/p2-wave/probes/TST-0133/fault_injection_report.schema.json"
)
DEF_NAME = "fault_injection_report"
REF = {"$ref": f"#/$defs/{DEF_NAME}"}


def load_fragment() -> dict:
    return json.loads((REPO / FRAG_REL).read_text(encoding="utf-8"))


def ensure_shared() -> dict:
    """Return the fragment, writing it into the shared schema $defs if absent."""
    frag = load_fragment()
    path = REPO / SCHEMA_REL
    schema = json.loads(path.read_text(encoding="utf-8"))
    defs = schema.setdefault("$defs", {})
    aliases = schema.get("definitions")
    dirty = defs.get(DEF_NAME) != frag
    if isinstance(aliases, dict) and aliases.get(DEF_NAME) != REF:
        dirty = True
    if not dirty:
        return frag
    defs[DEF_NAME] = frag
    if isinstance(aliases, dict):
        aliases[DEF_NAME] = dict(REF)
    path.write_text(
        json.dumps(schema, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    return frag
