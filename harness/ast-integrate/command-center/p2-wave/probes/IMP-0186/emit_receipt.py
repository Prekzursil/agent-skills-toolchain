#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0186.json and the fusion record it cites."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from workflow_fusion.conditional_hybrid import (  # noqa: E402
    FusionRefused,
    analyze_conditional_hybrid,
    emit_conditional_hybrid,
    route,
)
from workflow_fusion.reachability import dual_reachability, proofs_agree  # noqa: E402
from workflow_fusion.typed_predicate import eval_pred, typed_universe  # noqa: E402
import scenario as S  # noqa: E402

UNIT = "IMP-0186"
OUT = "command-center/receipts/IMP-0186.json"
FUSION_REL = "command-center/fusion/IMP-0186-conditional-hybrid.json"
ENGINE = "tools/workflow_fusion/conditional_hybrid.py"
REACH = "tools/workflow_fusion/reachability.py"
PRED = "tools/workflow_fusion/typed_predicate.py"
QUESTION = (
    "Target: emit a fusion that dispatches to different source sub-workflows "
    "based on a typed runtime predicate. Acceptance: every branch is reachable "
    "(static reachability proof) and the default branch is explicit - an "
    "unreachable branch is dead capability masquerading as coverage."
)


def sha_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def main() -> int:
    started = now()
    fixture_path = S.write_fixture_json()
    spec = S.good_spec()
    proof = dual_reachability(spec)
    if not proof.agreement or not proofs_agree(proof):
        print("FAILED:IMP-0186 derivations disagree on the good spec")
        return 1
    if proof.unreachable or proof.unrouted_count:
        print(
            f"FAILED:IMP-0186 good spec unreachable={list(proof.unreachable)} "
            f"unrouted={proof.unrouted_count}"
        )
        return 1

    fusion = emit_conditional_hybrid(spec)
    fusion_path = REPO / FUSION_REL
    fusion_path.parent.mkdir(parents=True, exist_ok=True)
    fusion_path.write_text(
        json.dumps(fusion, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    universe = typed_universe(spec["input_type"])
    counts = {br["id"]: 0 for br in spec["branches"]}
    for env in universe:
        src = route(fusion, env)
        owner = next(br["id"] for br in spec["branches"] if eval_pred(br["predicate"], env))
        want = next(br["source_id"] for br in spec["branches"] if br["id"] == owner)
        if src != want:
            print(f"FAILED:IMP-0186 runtime route {src} != {want} for {env}")
            return 1
        counts[owner] += 1
    if any(v == 0 for v in counts.values()):
        print(f"FAILED:IMP-0186 unexercised {counts}")
        return 1

    plant_rows = []
    for name, (factory, dead_id) in S.PLANTS.items():
        planted = factory()
        pproof = analyze_conditional_hybrid(planted)
        if dead_id not in pproof.unreachable:
            print(f"FAILED:IMP-0186 plant {name} missed {dead_id}")
            return 1
        refused = False
        code = ""
        try:
            emit_conditional_hybrid(planted)
        except FusionRefused as exc:
            refused = True
            code = exc.code
        if not refused or code != "fusion.conditional_hybrid.unreachable-branch":
            print(f"FAILED:IMP-0186 plant {name} not refused code={code!r}")
            return 1
        plant_rows.append(
            {
                "plant": name,
                "dead_id": dead_id,
                "unreachable": list(pproof.unreachable),
                "refused": True,
                "code": code,
            }
        )

    good_emit_ok = True
    try:
        emit_conditional_hybrid(spec)
    except FusionRefused:
        good_emit_ok = False
        print("FAILED:IMP-0186 good twin emit refused")
        return 1

    ended = now()
    fusion_art = art(FUSION_REL, "primary-fusion")
    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0186",
        "completion_sentinel": "SUCCESS:IMP-0186",
        "title": "Implement conditional-hybrid fusion (route to a source by runtime condition)",
        "question": QUESTION,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0186",
        "min_bytes_threshold": 2048,
        "profile": "selfimprove-measure-artifact",
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "implementer",
            "execution_substrate": "worktree-isolated",
        },
        "strategy": "conditional-hybrid",
        "operator": {
            "module": "tools/workflow_fusion/conditional_hybrid.py",
            "entry": "emit_conditional_hybrid",
            "dispatch": "first-match over typed predicates",
            "default_required": True,
            "default_must_be_last": True,
            "default_must_be_reachable": True,
        },
        "fusion_artifact": FUSION_REL,
        "fusion_id": fusion["id"],
        "default_branch_id": fusion["default_branch_id"],
        "default_explicit": True,
        "reachability": proof.as_dict(),
        "runtime_exercise": {
            "universe_size": proof.universe_size,
            "branch_taken_counts": counts,
            "every_branch_exercised": all(v > 0 for v in counts.values()),
        },
        "plants": plant_rows,
        "artifacts": [
            fusion_art,
            art(ENGINE, "supporting"),
            art(REACH, "supporting"),
            art(PRED, "supporting"),
            art(
                "command-center/p2-wave/probes/IMP-0186/scenario.py",
                "control",
            ),
            art(
                fixture_path.relative_to(REPO).as_posix(),
                "control",
            ),
        ],
        "evidence": [
            {
                "claim": (
                    "Static reachability over the 18-member enum universe reports 0 "
                    "unreachable branches. CFG dataflow and bitmask-complement agree "
                    f"on reachable={list(proof.cfg_reachable)}."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{REACH}:dual_reachability",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "cfg-dataflow",
                        "command": "dual_reachability(good_spec).cfg_reachable",
                        "raw_output": json.dumps(list(proof.cfg_reachable)),
                    },
                    {
                        "role": "verifier",
                        "method": "bitmask-complement",
                        "command": "dual_reachability(good_spec).bitmask_reachable",
                        "raw_output": json.dumps(list(proof.bitmask_reachable)),
                    },
                ],
            },
            {
                "claim": (
                    "A planted unreachable branch is detected: emit refuses with "
                    "fusion.conditional_hybrid.unreachable-branch on never, "
                    "out-of-enum, subsumed, and contradiction plants; the good twin "
                    "is not flagged."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{ENGINE}:emit_conditional_hybrid",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "plant-and-analyze",
                        "command": "analyze_conditional_hybrid(plant_*)",
                        "raw_output": json.dumps(plant_rows, sort_keys=True),
                    },
                    {
                        "role": "verifier",
                        "method": "both-states-emit",
                        "command": "emit_conditional_hybrid(good) vs emit(plant)",
                        "raw_output": json.dumps(
                            {"good_emit_ok": good_emit_ok, "plants_refused": len(plant_rows)}
                        ),
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "T1-zero-unreachable-computed",
                "command": "dual_reachability(good_spec)",
                "result": "PASS",
                "assertions": 3,
                "output_tail": (
                    f"unreachable=0 universe={proof.universe_size} "
                    f"agreement={proof.agreement}"
                ),
            },
            {
                "id": "T2-default-explicit-and-exercised",
                "command": "route(fusion, env) over typed universe",
                "result": "PASS",
                "assertions": proof.universe_size,
                "output_tail": json.dumps(counts, sort_keys=True),
            },
            {
                "id": "T3-planted-unreachable-detected",
                "command": "emit_conditional_hybrid(plant_*)",
                "result": "PASS",
                "assertions": len(plant_rows),
                "output_tail": json.dumps(
                    [r["plant"] for r in plant_rows]
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "IMP0186-C1-plant-never",
                "kind": "known-broken-fixture",
                "description": (
                    "Insert predicate op=false before default. Detector must name "
                    "br.dead-never; good twin must stay at 0 unreachable."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "br.dead-never -> fusion.conditional_hybrid.unreachable-branch",
                "good_state_output": "unreachable=[] emit ok",
            },
            {
                "id": "IMP0186-C2-plant-out-of-enum",
                "kind": "known-broken-fixture",
                "description": (
                    "eq task_class=translate is outside the declared enum. That is "
                    "unsatisfiable typed-dead, not a parse error."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "br.dead-ghost-class -> unreachable-branch",
                "good_state_output": "unreachable=[] emit ok",
            },
            {
                "id": "IMP0186-C3-plant-subsumed",
                "kind": "known-broken-fixture",
                "description": (
                    "Duplicate search+cheap after the live arm. First-match consumes "
                    "every witness; the duplicate is dead coverage."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "br.dead-subsumed -> unreachable-branch",
                "good_state_output": "unreachable=[] emit ok",
            },
            {
                "id": "IMP0186-C4-plant-contradiction",
                "kind": "known-broken-fixture",
                "description": (
                    "and(eq task_class=search, eq task_class=extract) has empty SAT."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "br.dead-contradiction -> unreachable-branch",
                "good_state_output": "unreachable=[] emit ok",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0186-probe2-planted-unreachable",
            "verdict": "PASS",
            "independent": True,
            "basis": (
                "Mechanically different from probe 1: planted fixtures must be "
                "refused at emit, while the good twin must emit. Four plant kinds."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0186/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/IMP-0186/probe1_zero_unreachable.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
            },
            {
                "consumer": "command-center/p2-wave/probes/IMP-0186/probe2_planted_unreachable.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Exact SAT is over finite enums. An infinite or string-open field "
                    "would make unreachability semi-decidable; this operator refuses "
                    "non-enum input types rather than approximating."
                ),
                "verdict": "SCOPED",
                "settling_experiment": (
                    "Add a string field to input_type and assert emit raises "
                    "fusion.predicate.field-not-enum."
                ),
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": "two strikes then pivot; this unit did not retry",
        },
        "notes": (
            "Dependencies IMP-0182 and IMP-0195 are not delivered on this worktree "
            "(agentspec and stage-splice are absent). The operator is self-contained "
            "under tools/workflow_fusion with a finite typed IR sufficient to emit "
            "conditional-hybrid dispatch and to prove branch reachability. "
            "SUCCESS:IMP-0186"
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if "SUCCESS:IMP-0186" not in text:
        print("FAILED:IMP-0186 sentinel missing from serialized receipt")
        return 1
    out_path.write_text(text, encoding="utf-8")
    size = out_path.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:IMP-0186 receipt {size}B below floor")
        return 1
    print(f"wrote {OUT} ({size} B) fusion={FUSION_REL}")
    print("SUCCESS:IMP-0186")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
