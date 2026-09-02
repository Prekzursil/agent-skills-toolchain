"""Pinned H-executed-corpus fixture: 72 family members plus named decoys.

Live Prompt One 08/09/transcripts are joined when present. Fixture IDs are
NOT claimed to be the Windows registry ids. Stages live on blueprints and
recorded runs, not on 08 candidates (matching WFA-0042: registry stages=0).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "corpus"
H_FAMILY = "H-executed-corpus"
H_N = 72
CATALOG_H_N = 72

# 0-59 MATCH, 60-61 STAGE, 62-63 GATE, 64-65 STOP,
# 66-67 missing transcript, 68-69 missing blueprint, 70 STAGE, 71 MATCH
STAGE_MUTANTS = {60, 61, 70}
GATE_MUTANTS = {62, 63}
STOP_MUTANTS = {64, 65}
MISSING_TRANSCRIPT = {66, 67}
MISSING_BLUEPRINT = {68, 69}


def _stages(i: int) -> list[str]:
    if i % 2 == 0:
        return ["ingest", "plan", "gate:review", "execute", "stop:commit"]
    return ["scout", "select", "gate:budget", "act", "stop:halt"]


def _gates(i: int) -> list[dict[str, Any]]:
    if i % 2 == 0:
        return [{"id": "review", "after_stage": 1, "predicate": "human-ok"}]
    return [{"id": "budget", "after_stage": 1, "predicate": "tokens<cap"}]


def _stop(i: int) -> dict[str, Any]:
    rule = "stop:commit" if i % 2 == 0 else "stop:halt"
    return {"kind": "named-terminal", "stage_index": 4, "rule": rule}


def cid(i: int) -> str:
    return f"h-exec-{i:02d}"


def tid(i: int) -> str:
    return f"tr-h-exec-{i:02d}"


def bid(i: int) -> str:
    return f"bp-h-exec-{i:02d}"


def decoys() -> list[dict[str, Any]]:
    return [
        {
            "id": "wf-kept-stage-gate",
            "family": "A-saved-workflow",
            "name": "kept-stage-gate",
            "does": "finite stage sequence with max_stages halt",
            "classification": "ADOPT-AS-IS",
            "mechanisms": ["kept.stage-gate"],
            "provenance": {"prov": "kept.stage-gate", "src": "07-OPTION-UNIVERSE.md:4"},
            "origin": "saved-file",
            "runtime": {"kind": "saved"},
            "evidence": {},
            "license": "unknown",
            "maintenance": "unmaintained",
            "notes": "decoy: must not enter H-executed-corpus recount",
        },
        {
            "id": "wf-repo-ci",
            "family": "B-repo-workflow",
            "name": "repo-ci",
            "does": "yaml jobs in the repository",
            "classification": "ADOPT-AS-IS",
            "mechanisms": ["repo.ci"],
            "provenance": {"prov": "repo.ci", "src": "08-WORKFLOW-ARCHAEOLOGY-AND-SOURCE-CATALOG.md:1"},
            "origin": "repo",
            "runtime": {"kind": "ci"},
            "evidence": {},
            "license": "unknown",
            "maintenance": "unmaintained",
            "notes": "decoy: family is not H-executed-corpus",
        },
        {
            "id": "cmd-start-task",
            "family": "I-command",
            "name": "start-task",
            "does": "slash command; mentions H-executed-corpus in notes only",
            "classification": "UNKNOWN-NEEDS-PROBE",
            "mechanisms": ["cmd.start"],
            "provenance": {"prov": "cmd.start", "src": "00-CURRENT-STATE-INVENTORY.md:1"},
            "origin": "command",
            "runtime": {"kind": "command"},
            "evidence": {},
            "license": "unknown",
            "maintenance": "unmaintained",
            "notes": (
                "USE-VS-MENTION decoy: the string H-executed-corpus appears here "
                "but family is I-command. A raw-text hit would count 73; JSON "
                "family recount must stay at 72."
            ),
        },
    ]


def h_candidates() -> list[dict[str, Any]]:
    rows = []
    for i in range(H_N):
        ev: dict[str, Any] = {}
        if i not in MISSING_TRANSCRIPT:
            ev["transcript_record_id"] = tid(i)
        rows.append(
            {
                "id": cid(i),
                "family": H_FAMILY,
                "name": f"executed-{i:02d}",
                "does": "workflow reconstructed from a recorded run that actually happened",
                "classification": "RECONSTRUCT-FROM-RUN",
                "mechanisms": ["replay.stage-sequence"],
                "provenance": {
                    "prov": "executed-corpus",
                    "src": "08-WORKFLOW-ARCHAEOLOGY-AND-SOURCE-CATALOG.md:3",
                },
                "origin": "recorded-run",
                "runtime": {"kind": "reconstructed"},
                "evidence": ev,
                "license": "unknown",
                "maintenance": "unmaintained",
                "notes": "fixture; not a Prompt One live registry id",
            }
        )
    return rows


def recorded_run(i: int) -> dict[str, Any]:
    return {
        "transcript_record_id": tid(i),
        "candidate_id": cid(i),
        "stages": _stages(i),
        "gates": _gates(i),
        "stopping_point": _stop(i),
        "source_anchor": f"recorded-runs.json:{cid(i)}",
    }


def blueprint_for(i: int) -> dict[str, Any]:
    stages = list(_stages(i))
    gates = [dict(g) for g in _gates(i)]
    stop = dict(_stop(i))
    if i in STAGE_MUTANTS:
        stages[1] = f"MUTANT-STAGE-{i:02d}"
    if i in GATE_MUTANTS:
        gates[0] = dict(gates[0])
        gates[0]["predicate"] = f"always-true-{i:02d}"
    if i in STOP_MUTANTS:
        stop = dict(stop)
        stop["stage_index"] = 3
        stop["rule"] = "stop:early"
    return {
        "id": bid(i),
        "candidate_id": cid(i),
        "stages": stages,
        "gates": gates,
        "stopping_point": stop,
        "provenance": {
            "prov": "reconstructed-blueprint",
            "src": "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
        },
    }


def registry_doc() -> dict[str, Any]:
    cands = h_candidates() + decoys()
    return {
        "artifact": "08-WORKFLOW-CANDIDATE-REGISTRY",
        "origin": "fixture-for-WFA-0154",
        "not_live_prompt_one": True,
        "candidates": cands,
        "counts": {
            "n": len(cands),
            H_FAMILY: H_N,
            "decoys": len(decoys()),
        },
    }


def blueprint_doc() -> dict[str, Any]:
    bps = [blueprint_for(i) for i in range(H_N) if i not in MISSING_BLUEPRINT]
    return {
        "artifact": "09-WORKFLOW-BLUEPRINT-LIBRARY",
        "origin": "fixture-for-WFA-0154",
        "not_live_prompt_one": True,
        "blueprints": bps,
    }


def runs_doc() -> dict[str, Any]:
    runs = [recorded_run(i) for i in range(H_N) if i not in MISSING_TRANSCRIPT]
    return {
        "artifact": "recorded-runs",
        "origin": "fixture-for-WFA-0154",
        "not_live_prompt_one": True,
        "runs": runs,
    }


def archaeology_md() -> str:
    return (
        "# 08 Workflow archaeology and source catalog\n"
        "\n"
        "H-executed-corpus candidates are reconstructed from recorded runs, "
        "not from saved workflow files.\n"
        "\n"
        "DEFINE `replay.stage-sequence`\n"
        "A reconstructed blueprint is replayed against its transcript by comparing "
        "stage sequence, gates, and stopping point. A mismatch cites the transcript "
        "record id and the stage index of first divergence.\n"
    )


def materialize() -> dict[str, Path]:
    FIXTURE.mkdir(parents=True, exist_ok=True)
    paths = {
        "registry": FIXTURE / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
        "blueprints": FIXTURE / "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
        "runs": FIXTURE / "recorded-runs.json",
        "archaeology": FIXTURE / "08-WORKFLOW-ARCHAEOLOGY-AND-SOURCE-CATALOG.md",
    }
    paths["registry"].write_text(
        json.dumps(registry_doc(), indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    paths["blueprints"].write_text(
        json.dumps(blueprint_doc(), indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    paths["runs"].write_text(
        json.dumps(runs_doc(), indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    paths["archaeology"].write_text(archaeology_md(), encoding="utf-8")
    return paths


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_registry(path: Path | None = None) -> list[dict[str, Any]]:
    p = path or (FIXTURE / "08-WORKFLOW-CANDIDATE-REGISTRY.json")
    doc = load_json(p)
    recs = doc.get("candidates") if isinstance(doc, dict) else doc
    if not isinstance(recs, list):
        return []
    return [r for r in recs if isinstance(r, dict) and r.get("id")]


def h_family(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [c for c in candidates if str(c.get("family") or "") == H_FAMILY]
    rows.sort(key=lambda r: str(r.get("id")))
    return rows


def load_blueprints(path: Path | None = None) -> dict[str, dict[str, Any]]:
    p = path or (FIXTURE / "09-WORKFLOW-BLUEPRINT-LIBRARY.json")
    doc = load_json(p)
    recs = doc.get("blueprints") if isinstance(doc, dict) else []
    out: dict[str, dict[str, Any]] = {}
    for b in recs or []:
        if isinstance(b, dict) and b.get("candidate_id"):
            out[str(b["candidate_id"])] = b
    return out


def load_runs(path: Path | None = None) -> dict[str, dict[str, Any]]:
    p = path or (FIXTURE / "recorded-runs.json")
    doc = load_json(p)
    recs = doc.get("runs") if isinstance(doc, dict) else []
    out: dict[str, dict[str, Any]] = {}
    for r in recs or []:
        if isinstance(r, dict) and r.get("candidate_id"):
            out[str(r["candidate_id"])] = r
    return out
