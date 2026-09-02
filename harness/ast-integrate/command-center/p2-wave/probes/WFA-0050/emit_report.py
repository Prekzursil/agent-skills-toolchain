#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0050-adapter-crew-autogen.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from adapter import (  # noqa: E402
    CONSTRUCTS,
    imported_forbidden,
    live_loop_must_be_non_transferable,
    translate_crew,
    translate_groupchat,
)
from battery import run_battery  # noqa: E402
from roles import CANONICAL  # noqa: E402
from sources import LICENCES, licences_recorded  # noqa: E402

UNIT = "WFA-0050"
OUT = "command-center/wfa/WFA-0050-adapter-crew-autogen.json"
QUESTION = (
    "Implementation target: express CrewAI crews/tasks/processes and AutoGen "
    "conversable-agent group chats as IR roles, turn policies and termination "
    "conditions - and identify which of their conversational-turn semantics "
    "have no barrier equivalent on the chosen control plane."
)


def sha_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    if not licences_recorded():
        print("FAILED:WFA-0050 licence not recorded before excerpts")
        return 1
    forbidden = imported_forbidden()
    if forbidden:
        print(f"FAILED:WFA-0050 imported {forbidden}")
        return 1
    live_bad = live_loop_must_be_non_transferable()
    if live_bad:
        print(f"FAILED:WFA-0050 live loop marked transferable {live_bad}")
        return 1
    crew = translate_crew()
    group = translate_groupchat()
    if imported_forbidden():
        print("FAILED:WFA-0050 adapter imported a runtime")
        return 1
    batt = run_battery()
    if batt["n"] != 20 or batt["disagree"]:
        print(f"FAILED:WFA-0050 battery n={batt['n']} disagree={batt['disagree']}")
        return 1
    if not batt["stop_ids"] or not batt["continue_ids"]:
        print("FAILED:WFA-0050 battery not mixed stop/continue")
        return 1
    if not batt["planted_and_hits"]:
        print("FAILED:WFA-0050 planted AND mutation was vacuous")
        return 1

    mapped = [c["id"] for c in CONSTRUCTS if c["status"] == "MAPPED"]
    non_t = [c["id"] for c in CONSTRUCTS if c["status"] == "NON-TRANSFERABLE"]
    crew_roles = [n["payload"]["mapping"] for n in crew["ir"]["roles"]]
    ag_roles = [n["payload"]["mapping"] for n in group["ir"]["roles"]]
    if any(m["status"] not in {"MAPPED", "EXTEND"} for m in crew_roles + ag_roles):
        print("FAILED:WFA-0050 role neither mapped nor extended")
        return 1

    schema_pack = REPO / "command-center/wfa/schema/wfa-schema-pack.json"
    ir_spec = REPO / "command-center/wfa/WFA-0044-workflow-ir-spec.json"
    teardown = REPO / "command-center/wfa/WFA-0027-teardown-adjacent-runtimes.json"
    council_spec = REPO / "11-COUNCIL-SPECIFICATION.md"

    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    doc = {
        "adapter_id": "crewai-autogen-to-ir",
        "answer": (
            "CrewAI sequential crews map to ordered IR stages with a Boolean "
            "stop tasks_completed >= task_count. AutoGen GroupChat termination "
            "maps to is_termination_msg OR round_index == last_round OR "
            "speaker_selection_none OR reply_is_none. Live conversational loops "
            "(hierarchical manager delegation, allow_delegation, auto/manual/"
            "random speaker selection, run_chat itself, human_input ALWAYS/"
            "TERMINATE) are NON-TRANSFERABLE. CrewAI Agent.role job titles "
            "extend the council vocabulary; Reviewer and Critic and "
            "GroupChatManager map onto reviewer/critic/chair."
        ),
        "artifacts": [
            {
                "exists": True,
                "path": OUT,
                "role": "primary",
            }
        ],
        "claims": [
            {
                "anchor": "command-center/p2-wave/probes/WFA-0050/adapter.py:translate_crew",
                "claim": "Worked sequential crew translates with every CrewAI construct mapped or NON-TRANSFERABLE.",
                "id": "C1",
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "command-center/p2-wave/probes/WFA-0050/adapter.py:translate_groupchat",
                "claim": "Worked round-robin group chat translates; auto/manual/random speaker policies stay NON-TRANSFERABLE.",
                "id": "C2",
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "command-center/p2-wave/probes/WFA-0050/battery.py:run_battery",
                "claim": "Boolean stopping grammar agrees with the documented oracles on 20 synthetic states; an AND-for-OR plant is detected.",
                "id": "C3",
                "verdict": "CONFIRMED",
            },
        ],
        "completion_sentinel": "SUCCESS:WFA-0050",
        "constructs": CONSTRUCTS,
        "constructs_mapped": mapped,
        "constructs_non_transferable": non_t,
        "control_plane": {
            "chosen": "prompt-native council / workflow IR (WFA-0044 absent; local subset used)",
            "no_second_runtime": True,
            "wfa_0027_teardown_present": teardown.is_file(),
        },
        "dependencies_on_disk": {
            "WFA-0001_schema_pack": schema_pack.is_file(),
            "WFA-0027_teardown": teardown.is_file(),
            "WFA-0044_ir_spec": ir_spec.is_file(),
            "council_specification_md": council_spec.is_file(),
        },
        "evidence_requirement": {
            "A": "worked crew and worked group chat each translated with per-construct mapped or NON-TRANSFERABLE",
            "B": "termination re-expressed in Boolean grammar and evaluated on 20 synthetic states vs documented behaviour",
        },
        "frameworks": ["CrewAI", "AutoGen/AG2"],
        "groupchat_translation": group,
        "ir_subset_note": (
            "WFA-0044 workflow IR spec is not on this worktree. This adapter "
            "emits a local IR subset (roles, stages, turn_policy, stopping, "
            "gates, edges, lineage, source_anchor on every node, no execution "
            "entrypoint). It is not a second runtime."
        ),
        "licences": LICENCES,
        "lossy_field_ledger": [
            {
                "source": "CrewAI Agent.role",
                "lost_if_forced_to_council_seat": True,
                "disposition": "EXTEND crew-job-title",
            },
            {
                "source": "CrewAI ConditionalTask predicate",
                "lost_if_forced_to_boolean_grammar": True,
                "disposition": "NON-TRANSFERABLE",
            },
            {
                "source": "AutoGen speaker_selection_method=auto nested LLM chat",
                "lost_if_approximated_as_round_robin": True,
                "disposition": "NON-TRANSFERABLE",
            },
        ],
        "output_schema": "command-center/wfa/schema/wfa-schema-pack.json#/$defs/AdapterConformanceReport",
        "output_schema_pack_present": schema_pack.is_file(),
        "output_schema_note": (
            (
                "WFA-0001 schema pack is present as a generated shim that $ref's "
                "platform/schema/artifact-class-profiles.schema.json#/$defs/"
                "AdapterConformanceReport. This document is AdapterConformanceReport-"
                "shaped (record_type, sentinel, construct map, 20-state battery). "
                "It is not a full receipt_core envelope and does not claim "
                "schema-valid against additionalProperties:false receipt_core."
            )
            if schema_pack.is_file()
            else (
                "WFA-0001 schema pack is absent on this worktree. This document is "
                "an AdapterConformanceReport-shaped record. It is not claimed valid "
                "against a missing $defs.AdapterConformanceReport."
            )
        ),
        "produced_at": started,
        "question": QUESTION,
        "record_type": "AdapterConformanceReport",
        "reviewer": {
            "independent": True,
            "reviewer_id": "WFA-0050-probe2-termination-battery",
            "verdict": "PASS",
            "basis": (
                "Probe 2 re-evaluates 20 states with documented.py control-flow "
                "versus stopping.py grammar and requires the planted AND mutation "
                "to disagree. Probe 1 is translation/role/import, a different mechanism."
            ),
        },
        "role_mappings": {
            "council_vocabulary": sorted(CANONICAL),
            "crew": crew_roles,
            "groupchat": ag_roles,
            "vocabulary_source": (
                "Reconstructed from on-disk CNL-0105, CNL-0114, CNL-0033 because "
                "11-COUNCIL-SPECIFICATION.md is absent."
            ),
        },
        "runtime_import": {
            "forbidden": ["crewai", "autogen", "ag2", "pyautogen"],
            "imported": forbidden,
            "ok": not forbidden,
        },
        "schema_version": 1,
        "sentinel": "SUCCESS:WFA-0050",
        "state": "SUCCESS",
        "termination_battery": {
            "n": batt["n"],
            "disagree": batt["disagree"],
            "stop_ids": batt["stop_ids"],
            "continue_ids": batt["continue_ids"],
            "expressions": batt["expressions"],
            "planted_and_hits": batt["planted_and_hits"],
            "rows": batt["rows"],
        },
        "tests": [
            {
                "id": "T1-live-loop-non-transferable",
                "result": "PASS",
                "detail": "every live conversational loop construct is NON-TRANSFERABLE",
            },
            {
                "id": "T2-roles-map-or-extend",
                "result": "PASS",
                "detail": "no force-fit; job titles extend; Reviewer/Critic/Manager map",
            },
            {
                "id": "T3-no-runtime-import",
                "result": "PASS",
                "detail": "adapter does not import crewai/autogen/ag2",
            },
            {
                "id": "T4-20-state-agreement",
                "result": "PASS",
                "detail": f"n=20 disagree=0 stop={len(batt['stop_ids'])} continue={len(batt['continue_ids'])}",
            },
        ],
        "title": "Adapter: role-crew frameworks (CrewAI, AutoGen) to IR",
        "translations": {
            "crew": crew,
            "groupchat": group,
        },
        "unit_id": UNIT,
        "worked_examples": {
            "crew_id": crew["native"]["id"],
            "groupchat_id": group["native"]["id"],
        },
    }
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if "SUCCESS:WFA-0050" not in text:
        print("FAILED:WFA-0050 sentinel missing")
        return 1
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    digest, size = sha_file(out)
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:WFA-0050")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
