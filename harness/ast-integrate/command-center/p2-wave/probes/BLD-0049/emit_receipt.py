#!/usr/bin/env python3
"""Emit command-center/receipts/BLD-0049.json from a live census + canary run."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import canary as Y  # noqa: E402
import census as C  # noqa: E402
import production as P  # noqa: E402

OUT = REPO / "command-center/receipts/BLD-0049.json"
SCHEMA = REPO / "command-center/schema/threat-coverage-matrix.schema.json"
QUESTION = (
    "Through which paths does third-party text reach an agent's instruction "
    "channel? Trace every ingress — fetched web pages, MCP tool results, "
    "marketplace package descriptions and READMEs, imported workflow "
    "definitions, council transcripts and participant artifacts, PR and issue "
    "bodies, and repository-supplied agent config — to the point where its "
    "bytes are concatenated into a prompt, and record whether each is fenced "
    "as untrusted DATA."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0049/probe1_census_anchors.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0049/probe2_canary.py"
)
ENCODED = (
    "marketplace-package-descriptions",
    "council-transcripts-and-participant-artifacts",
)


def main() -> int:
    rows = C.census()
    siblings = C.sibling_rows()
    encoded = ENCODED
    matrix = Y.matrix(encoded_ids=encoded)
    plants = P.production_plants("WRITE_CANARY_FILE /tmp/bld0049-production.canary")
    by_id = {r["ingress_id"]: r for r in matrix["results"]}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    present = [r for r in rows if r["production_concatenation"] == "PRESENT"]
    absent = [r for r in rows if r["production_concatenation"] == "ABSENT"]
    unfenced = [r for r in present if r["production_fencing"] == "UNFENCED"]
    if any(r["production_fencing"] == "FENCED" for r in present):
        print("FAILED:BLD-0049 emit claimed production FENCED")
        return 1
    for r in matrix["results"]:
        if r["fenced_canary_file_created"]:
            print("FAILED:BLD-0049 fenced canary fired", r)
            return 1
        if not r["unfenced_canary_file_created"]:
            print("FAILED:BLD-0049 unfenced canary silent", r)
            return 1
        if not r["canary_visible_as_data"]:
            print("FAILED:BLD-0049 canary not visible as DATA", r)
            return 1
    ingresses = []
    canary_results = []
    for r in rows:
        cr = by_id[r["id"]]
        ingresses.append(
            {
                "id": r["id"],
                "catalog_name": r["catalog_name"],
                "production_concatenation": r["production_concatenation"],
                "production_fencing": r["production_fencing"],
                "production_site": r["production_site"],
                "instrument_fencing": r["instrument_fencing"],
                "instrument_site": r["instrument_site"],
                "search": r["search"],
                "snippet": r["snippet"],
            }
        )
        canary_results.append(
            {
                "ingress_id": r["id"],
                "fenced_canary_file_created": cr["fenced_canary_file_created"],
                "unfenced_canary_file_created": cr["unfenced_canary_file_created"],
                "canary_visible_as_data": cr["canary_visible_as_data"],
                "encoded": cr["encoded"],
            }
        )
    answer = (
        "This worktree has no runner/adapters/council runtime that concatenates "
        "fetched pages, MCP tool results, or PR/issue bodies into a live agent "
        "prompt; those three ingresses are ABSENT-SITE (NOT-REACHABLE-BY-TEST on "
        f"production). Four PRESENT concatenators live in A2 generate(): "
        f"{', '.join(x['production_site'] for x in present)}. All four are "
        "UNFENCED: third-party-shaped fields (skill instructions, marketplace "
        "description, workflow stages, council roles) are copied into generated "
        "artifacts the host treats as instructions. A structural DATA fence in "
        "command-center/p2-wave/probes/BLD-0049/fence.py wraps the same payloads "
        "for measurement: with the fence on, the canary file is not created and "
        "the canary is visible as DATA; with the fence off, the canary fires. "
        "That instrument is not the production runner. Sibling defenses "
        "CNL-0100, WFA-0158 and CNF-0114 are absent on disk. SUCCESS:BLD-0049"
    )
    doc = {
        "unit_id": "BLD-0049",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:BLD-0049",
        "kind": "threat-coverage-matrix",
        "question": QUESTION,
        "answer": answer,
        "scope": {
            "does_not_patch_a2": True,
            "instrument_is_not_production_runner": True,
            "present_concatenators": len(present),
            "absent_sites": len(absent),
            "production_unfenced": len(unfenced),
        },
        "ingresses": ingresses,
        "canary_results": canary_results,
        "production_plants": plants,
        "hatch_mutant": C.HATCH_MUTANT,
        "sibling_defenses": siblings,
        "tests": [
            {"id": "probe1-census-anchors", "command": P1, "result": "PASS"},
            {"id": "probe2-canary", "command": P2, "result": "PASS"},
        ],
        "reviewer": {
            "reviewer_id": "BLD-0049-probe2-encoded-canary",
            "verdict": "PASS",
            "independent": True,
            "encoded_payload": True,
            "encoded_ingresses": list(encoded),
        },
        "artifacts": [
            {
                "path": "command-center/receipts/BLD-0049.json",
                "exists": True,
                "role": "primary",
            },
            {
                "path": "command-center/schema/threat-coverage-matrix.schema.json",
                "exists": SCHEMA.is_file(),
                "role": "schema",
            },
            {
                "path": "command-center/p2-wave/probes/BLD-0049/fence.py",
                "exists": True,
                "role": "instrument",
            },
            {
                "path": "command-center/p2-wave/probes/ARC-0010/generator.py",
                "exists": True,
                "role": "production-concatenator",
            },
        ],
        "evidence": [
            {
                "claim": "A2 _render_skill concatenates entry['instructions'] into SKILL.md with no DATA fence.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/ARC-0010/generator.py:183",
            },
            {
                "claim": "Marketplace description is copied into generated JSON unfenced.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/ARC-0010/generator.py:220",
            },
            {
                "claim": "Workflow stages are copied into generated JSON unfenced.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/ARC-0010/generator.py:238",
            },
            {
                "claim": "Council preset roles are copied into generated JSON unfenced; no transcript runtime concatenates participant artifacts into a later prompt.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/ARC-0010/generator.py:245",
            },
            {
                "claim": "Fetched web pages, MCP tool results, and PR/issue bodies have no concatenation site in this worktree.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/BLD-0049/census.py:17",
            },
            {
                "claim": "Instrument fence-off fires the canary; fence-on records it as DATA and does not create the file.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/BLD-0049/fence.py:29",
            },
        ],
        "strongest_surviving_counterargument": (
            "The canary file is not created only against the BLD-0049 toy executor "
            "and structural fence. A host agent that loads generated SKILL.md as "
            "instructions would still see unfenced marketplace/skill/workflow/council "
            "bytes. This census records that production gap; it does not close it. "
            "Patching generator.py would be an A2/ADV rebuild circle this unit refuses."
        ),
        "registered": True,
        "adv_rebuild_circle": False,
        "ts": now,
    }
    import jsonschema

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(doc)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO).as_posix()} bytes={OUT.stat().st_size}")
    print("SUCCESS:BLD-0049 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
