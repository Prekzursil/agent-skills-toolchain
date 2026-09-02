"""Recorded 44-row UNKNOWN-NEEDS-PROBE corpus for WFA-0147.

Live 08-WORKFLOW-CANDIDATE-REGISTRY.json is not mounted on this Linux
worktree (CC-0019 present=false; WFA-0007 inspect recorded sha256
4791c7a628e5bf1f5492c56a7b06bdb636f5a66829c0145ecb27d3f0b0f0885a on
Windows). This corpus matches the catalog contract n=44 recounted from
candidates[] (the counts block is a planted lie). Identities are local
wfa0147-unk-NN, not claimed to be the Windows wf-* ids.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

UNKNOWN = "UNKNOWN-NEEDS-PROBE"
VOCABULARY = [
    "ADOPT-AS-IS",
    "UNKNOWN-NEEDS-PROBE",
    "DISTILL",
    "RETIRE",
    "ADOPT-WITH-WRAPPER",
    "REPAIR",
    "EXTEND",
    "MERGE",
    "SPECIALIZE",
    "CLEAN-ROOM-REIMPLEMENT",
    "COMPOSE",
    "GENERALIZE",
    "REBUILD-FROM-SPEC",
    "REJECT",
    "TRANSLATE",
]

FIX = "command-center/p2-wave/probes/WFA-0147/fixtures"

# id, name, family, kind, target, extra
UNKNOWN_ROWS: list[tuple[str, str, str, str, str, dict[str, Any]]] = [
    ("wfa0147-unk-01", "anti-rebuild guard", "C-repo-tool", "exists", "tools/workflow_foundry/anti_rebuild_guard.py", {}),
    ("wfa0147-unk-02", "generator gate", "C-repo-tool", "exists", "tools/workflow_foundry/generator_gate.py", {}),
    ("wfa0147-unk-03", "baseline scorer", "C-repo-tool", "exists", "tools/workflow_foundry/baseline.py", {}),
    ("wfa0147-unk-04", "capability vector", "C-repo-tool", "exists", "tools/workflow_foundry/capability.py", {}),
    ("wfa0147-unk-05", "foundry package init", "C-repo-tool", "exists", "tools/workflow_foundry/__init__.py", {}),
    ("wfa0147-unk-06", "catalog loader", "C-repo-tool", "exists", "tools/command-center/catalog.py", {}),
    ("wfa0147-unk-07", "marketplace tag gate", "C-repo-tool", "exists", "tools/marketplace/tag_gate.py", {}),
    ("wfa0147-unk-08", "plugin secret gate", "C-repo-tool", "exists", "tools/plugin/secret_gate.py", {}),
    ("wfa0147-unk-09", "council deadlock detector", "D-harness-runtime", "exists", "tools/council/stopping/deadlock.py", {}),
    ("wfa0147-unk-10", "per-unit delivery measure", "D-harness-runtime", "exists", "command-center/p2-wave/_measure_one_delivered.py", {}),
    ("wfa0147-unk-11", "claim-record schema", "C-repo-tool", "exists", "command-center/schema/claim-record.schema.json", {}),
    ("wfa0147-unk-12", "IMP-0211 receipt", "H-executed-corpus", "exists", "command-center/receipts/IMP-0211.json", {}),
    ("wfa0147-unk-13", "retired once-only scanner", "C-repo-tool", "missing", "tools/retired/once-only-scanner.mjs", {}),
    ("wfa0147-unk-14", "WFA-0070 settlement artifact", "H-executed-corpus", "missing", "command-center/wfa/WFA-0070-unknown-needs-probe-settlement.json", {}),
    ("wfa0147-unk-15", "foundry artifact schema", "C-repo-tool", "missing", "command-center/schema/foundry-artifact.schema.json", {}),
    ("wfa0147-unk-16", "open-unknowns ledger", "H-executed-corpus", "missing", "18-OPEN-UNKNOWNS-AND-PROBES.md", {}),
    ("wfa0147-unk-17", "blueprint library", "B-repo-workflow", "missing", "09-WORKFLOW-BLUEPRINT-LIBRARY.json", {}),
    ("wfa0147-unk-18", "harness-restore registry copy", "H-executed-corpus", "missing", "harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json", {}),
    ("wfa0147-unk-19", "claim schema parse", "C-repo-tool", "json", "command-center/schema/claim-record.schema.json", {}),
    ("wfa0147-unk-20", "IMP-0211 registry parse", "H-executed-corpus", "json", "command-center/p2-wave/probes/IMP-0211/fixtures/registry.json", {}),
    ("wfa0147-unk-21", "detector-control schema parse", "C-repo-tool", "json", "command-center/schema/detector-control.schema.json", {}),
    ("wfa0147-unk-22", "IMP-0211 receipt parse", "H-executed-corpus", "json", "command-center/receipts/IMP-0211.json", {}),
    ("wfa0147-unk-23", "compile anti-rebuild guard", "C-repo-tool", "py-compile", "tools/workflow_foundry/anti_rebuild_guard.py", {}),
    ("wfa0147-unk-24", "compile catalog loader", "C-repo-tool", "py-compile", "tools/command-center/catalog.py", {}),
    ("wfa0147-unk-25", "compile tag gate", "C-repo-tool", "py-compile", "tools/marketplace/tag_gate.py", {}),
    ("wfa0147-unk-26", "compile deadlock detector", "D-harness-runtime", "py-compile", "tools/council/stopping/deadlock.py", {}),
    ("wfa0147-unk-27", "node wrapper shim", "C-repo-tool", "wrapper", f"{FIX}/wrapper.mjs", {}),
    ("wfa0147-unk-28", "cjs wrapper shim", "C-repo-tool", "wrapper", f"{FIX}/wrapper2.js", {}),
    ("wfa0147-unk-29", "distill unit catalog", "H-executed-corpus", "distill", "command-center/WORK-UNIT-CATALOG.json", {}),
    ("wfa0147-unk-30", "distill deadlock module", "D-harness-runtime", "distill", "tools/council/stopping/deadlock.py", {}),
    ("wfa0147-unk-31", "merge foundry init+capability", "C-repo-tool", "merge", "tools/workflow_foundry/__init__.py", {"second": "tools/workflow_foundry/capability.py"}),
    ("wfa0147-unk-32", "specialize IMP-0211 probe1", "H-executed-corpus", "specialize", "command-center/p2-wave/probes/IMP-0211/probe1_both_states.py", {}),
    ("wfa0147-unk-33", "reject planted unsafe token", "C-repo-tool", "reject", f"{FIX}/unsafe.py", {}),
    ("wfa0147-unk-34", "compose catalog+validate", "C-repo-tool", "compose", "tools/command-center/catalog.py", {"second": "tools/command-center/validate.py"}),
    ("wfa0147-unk-35", "generalize delivery measure", "D-harness-runtime", "generalize", "command-center/p2-wave/_measure_one_delivered.py", {}),
    ("wfa0147-unk-36", "translate powershell helper", "C-repo-tool", "translate", f"{FIX}/translate.ps1", {}),
    ("wfa0147-unk-37", "clean-room spec body", "C-repo-tool", "clean-room", f"{FIX}/spec-only.json", {}),
    ("wfa0147-unk-38", "rebuild from spec-only", "C-repo-tool", "rebuild", f"{FIX}/spec-only.json", {"second": f"{FIX}/missing-impl.py"}),
    ("wfa0147-unk-39", "extend claim schema", "C-repo-tool", "extend", "command-center/schema/claim-record.schema.json", {"required_key": "probe_dispatch"}),
    ("wfa0147-unk-40", "repair broken json fixture", "C-repo-tool", "repair", f"{FIX}/broken.json", {}),
    ("wfa0147-unk-41", "remote registry fetch", "H-executed-corpus", "refuse-network", "https://example.invalid/08-WORKFLOW-CANDIDATE-REGISTRY.json", {}),
    ("wfa0147-unk-42", "unnamed settling probe", "H-executed-corpus", "no-probe", "", {}),
    (
        "wfa0147-unk-43",
        "windows live registry",
        "H-executed-corpus",
        "windows-path",
        "C:/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json",
        {},
    ),
    (
        "wfa0147-unk-44",
        "windows open-unknowns ledger",
        "H-executed-corpus",
        "windows-path",
        "C:/Users/Prekzursil/.claude/harness-restore-20260806/18-OPEN-UNKNOWNS-AND-PROBES.md",
        {},
    ),
]

DECOYS = [
    ("wfa0147-decoy-adopt", "ADOPT-AS-IS", "already adopted decoy"),
    ("wfa0147-decoy-retire", "RETIRE", "already retired decoy"),
    ("wfa0147-decoy-distill", "DISTILL", "already distilled decoy"),
    ("wfa0147-decoy-repair", "REPAIR", "already repair-classed decoy"),
    ("wfa0147-decoy-extend", "EXTEND", "already extend-classed decoy"),
    ("wfa0147-decoy-merge", "MERGE", "already merge-classed decoy"),
]


def _candidate(
    cid: str,
    name: str,
    family: str,
    classification: str,
    does: str,
    probe: dict[str, Any] | None,
    origin: str = "recorded-corpus:WFA-0147",
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": cid,
        "name": name,
        "family": family,
        "classification": classification,
        "does": does,
        "mechanisms": ["named-settling-probe"] if probe else [],
        "provenance": "command-center/p2-wave/probes/WFA-0147/corpus.py",
        "license": "UNKNOWN",
        "maintenance": "worktree-local",
        "notes": (
            "UNKNOWN-NEEDS-PROBE until the named settling probe runs"
            if classification == UNKNOWN
            else "decoy already classified; must not enter the 44-row dispatch"
        ),
        "origin": origin,
        "evidence": ["catalog-histogram-n=44", "WFA-0007-inspect-schema"],
    }
    if probe is not None:
        row["settling_probe"] = probe
    return row


def build_registry() -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for cid, name, family, kind, target, extra in UNKNOWN_ROWS:
        probe = {"kind": kind, "target": target, **extra}
        candidates.append(
            _candidate(
                cid,
                name,
                family,
                UNKNOWN,
                f"settle {name} via {kind}",
                probe,
                origin="" if cid == "wfa0147-unk-37" else "recorded-corpus:WFA-0147",
            )
        )
    for cid, cls, name in DECOYS:
        candidates.append(
            _candidate(cid, name, "H-executed-corpus", cls, name, None)
        )
    if len([c for c in candidates if c["classification"] == UNKNOWN]) != 44:
        raise RuntimeError("corpus must contain exactly 44 UNKNOWN-NEEDS-PROBE rows")
    return {
        "artifact": "08-WORKFLOW-CANDIDATE-REGISTRY.recorded-for-WFA-0147",
        "classification_vocabulary": list(VOCABULARY),
        "generated_by": "command-center/p2-wave/probes/WFA-0147/corpus.py",
        "mirror": "catalog-contract n=44 UNKNOWN-NEEDS-PROBE; live Windows registry not mounted",
        "source_of_truth_ref": {
            "windows_path": "C:/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json",
            "windows_sha256_if_present": "4791c7a628e5bf1f5492c56a7b06bdb636f5a66829c0145ecb27d3f0b0f0885a",
            "windows_bytes_if_present": 261589,
            "this_corpus": "recorded-44-unknown-needs-probe",
        },
        "counts": {
            UNKNOWN: 40,
            "ADOPT-AS-IS": 99,
            "note": "planted lie — recount MUST use candidates[] not this block",
        },
        "candidates": candidates,
    }


def write_registry(path: Path) -> dict[str, Any]:
    doc = build_registry()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return doc


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    out = here / "fixtures" / "registry.json"
    write_registry(out)
    print(f"wrote {out}")
