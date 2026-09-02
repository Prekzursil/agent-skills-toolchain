"""Drive canaries through production A2 concatenators without patching them."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARC10 = HERE.parent / "ARC-0010"
sys.path.insert(0, str(ARC10))
import generator as G  # noqa: E402


def _registry() -> dict:
    return copy.deepcopy(json.loads((ARC10 / "registry.json").read_text(encoding="utf-8")))


def plant_skill_instructions(canary: str) -> dict:
    reg = _registry()
    skill = next(e for e in reg["entries"] if e["kind"] == "skill")
    skill["instructions"] = canary + "\n" + skill["instructions"]
    rendered = G._render_skill(skill).decode("utf-8")
    return {
        "ingress_id": "repository-supplied-agent-config",
        "site": "command-center/p2-wave/probes/ARC-0010/generator.py:183",
        "canary_in_output": canary in rendered,
        "output_preview": rendered[-400:],
        "fenced": "<<<UNTRUSTED_DATA" in rendered,
    }


def plant_marketplace_description(canary: str) -> dict:
    reg = _registry()
    entry = next(e for e in reg["entries"] if e["kind"] == "marketplace_entry")
    entry["description"] = canary + " " + entry["description"]
    payload = {
        "category": entry["category"],
        "description": entry["description"],
        "name": entry["name"],
        "plugin_id": entry["plugin_id"],
        "version": entry["version"],
    }
    rendered = G.json_with_prov(entry, payload).decode("utf-8")
    return {
        "ingress_id": "marketplace-package-descriptions",
        "site": "command-center/p2-wave/probes/ARC-0010/generator.py:220",
        "canary_in_output": canary in rendered,
        "output_preview": rendered[:500],
        "fenced": "<<<UNTRUSTED_DATA" in rendered,
    }


def plant_workflow_stage(canary: str) -> dict:
    reg = _registry()
    entry = next(e for e in reg["entries"] if e["kind"] == "workflow_blueprint")
    entry["stages"] = list(entry["stages"]) + [
        {"id": "canary", "kind": canary, "inputs": [], "outputs": []}
    ]
    payload = {
        "discovery_only": entry["discovery_only"],
        "id": entry["id"],
        "stages": entry["stages"],
        "stopping": entry["stopping"],
    }
    rendered = G.json_with_prov(entry, payload).decode("utf-8")
    return {
        "ingress_id": "imported-workflow-definitions",
        "site": "command-center/p2-wave/probes/ARC-0010/generator.py:238",
        "canary_in_output": canary in rendered,
        "output_preview": rendered[-500:],
        "fenced": "<<<UNTRUSTED_DATA" in rendered,
    }


def plant_council_role(canary: str) -> dict:
    reg = _registry()
    entry = next(e for e in reg["entries"] if e["kind"] == "council_preset")
    entry["roles"] = list(entry["roles"]) + [canary]
    payload = {
        "id": entry["id"],
        "roles": entry["roles"],
        "stopping": entry["stopping"],
        "voting": entry["voting"],
    }
    rendered = G.json_with_prov(entry, payload).decode("utf-8")
    return {
        "ingress_id": "council-transcripts-and-participant-artifacts",
        "site": "command-center/p2-wave/probes/ARC-0010/generator.py:245",
        "canary_in_output": canary in rendered,
        "output_preview": rendered[-500:],
        "fenced": "<<<UNTRUSTED_DATA" in rendered,
    }


def production_plants(canary: str) -> list[dict]:
    rows = [
        plant_skill_instructions(canary),
        plant_marketplace_description(canary),
        plant_workflow_stage(canary),
        plant_council_role(canary),
    ]
    for row in rows:
        if not row["canary_in_output"]:
            raise RuntimeError(f"production concatenator dropped canary {row}")
        if row["fenced"]:
            raise RuntimeError(f"unexpected fence in production output {row}")
    return rows
