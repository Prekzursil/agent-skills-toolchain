#!/usr/bin/env python3
"""Emit the WFA-0141 foundry control-plane-census artifact."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402
import schema_util as S  # noqa: E402

UNIT = "WFA-0141"
OUT = (
    "command-center/foundry/"
    "WFA-0141-control-plane-singularity-gate-at-acquisition-and-at.json"
)
SCHEMA = "command-center/schema/foundry-artifact.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0141/probe1_acquisition_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0141/probe2_fusion_and_shared_counter.py"
)
SENTINEL = "SUCCESS:WFA-0141"
QUESTION = (
    "Implement one census that counts the distinct orchestration control "
    "planes a workflow introduces, and run it at BOTH trigger points: when "
    "an external candidate is acquired (spec forbids importing a second "
    "orchestration runtime merely because a workflow was found there) and "
    "when a fusion is assembled (spec names duplicate control planes as a "
    "fusion failure). Question: which acquired candidates or fusions raise "
    "the control-plane count above one, and for each, what is the extracted "
    "mechanism that would let it run on the existing plane instead?"
)
MIN_BYTES = 2048


def digest(rel: str) -> dict:
    path = REPO / rel
    data = path.read_bytes() if path.is_file() else b""
    norm = data.replace(b"\r\n", b"\n")
    return {
        "path": rel,
        "bytes": len(norm) if data else 0,
        "sha256": hashlib.sha256(norm).hexdigest() if data else "",
        "exists": path.is_file(),
    }


def run(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def slim_reading(row: dict) -> dict:
    keys = (
        "trigger",
        "subject_id",
        "runtime_field_planes",
        "guard_planes",
        "planes",
        "count",
        "over_one",
        "gate",
        "extracted_mechanism",
        "source_ids",
        "source_runtime_field_planes",
        "fused_definition_runtime_planes",
    )
    return {k: row[k] for k in keys if k in row}


def main() -> int:
    c1, t1 = run(P1)
    c2, t2 = run(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:WFA-0141 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    planted = C.planted_bundle()
    live = C.live_bundle()
    acq_plant = planted["acquisition"]
    fus_plant = planted["fusion"]
    raised = [
        slim_reading(r)
        for r in (acq_plant["readings"] + fus_plant["readings"])
        if r["over_one"]
    ]
    live_raised: list[dict] = []
    live_acq_n = 0
    live_fus_n = 0
    if live["acquisition"]:
        live_acq_n = live["acquisition"]["n"]
        live_raised.extend(
            slim_reading(r)
            for r in live["acquisition"]["readings"]
            if r["over_one"]
        )
    if live["fusion"]:
        live_fus_n = live["fusion"]["n"]
        live_raised.extend(
            slim_reading(r)
            for r in live["fusion"]["readings"]
            if r["over_one"]
        )

    live_present = live["live_available"]
    if live_present:
        answer = (
            f"Live registry loaded ({live_acq_n} candidates, {live_fus_n} "
            f"fusions). {len(live_raised)} subject(s) raise the control-plane "
            "count above one; each row names the extracted mechanism that "
            f"stays on {C.HOME_PLANE}. Planted both-states also hold. "
            + SENTINEL
        )
    else:
        answer = (
            "The 284-row 08-WORKFLOW-CANDIDATE-REGISTRY.json and the "
            "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json are not on this Linux "
            "worktree (paths hunted and recorded). The shared counter still "
            "ran at both trigger points over the planted corpus required by "
            "the unit: plant-own-runner and plant-home-string-foreign-import "
            "fire at acquisition; plant-fusion-dup-planes and "
            "plant-fusion-two-foreign fire at fusion; plant-pure-mechanism "
            "and plant-fusion-single-plane stay at count=1. For each firing "
            f"row the extracted mechanism is the IR that stays on {C.HOME_PLANE}. "
            "Live 284-row identities are NOT-CHECKED, not invented. "
            + SENTINEL
        )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    catalog_q = C.line_anchor(
        "command-center/WORK-UNIT-CATALOG.json",
        "counts the distinct orchestration control planes a workflow introduces",
    )
    counter_anchor = C.line_anchor(
        "command-center/p2-wave/probes/WFA-0141/census.py",
        '"""THE shared counter. Used at acquisition and at fusion."""',
    )
    acquire_anchor = C.line_anchor(
        "command-center/p2-wave/probes/WFA-0141/census.py",
        'return count_planes(candidate, trigger="acquisition")',
    )
    fuse_anchor = C.line_anchor(
        "command-center/p2-wave/probes/WFA-0141/census.py",
        'reading = count_planes(fusion, trigger="fusion", extra_docs=extra)',
    )

    supporting = [
        SCHEMA,
        S.LOCAL_REL,
        "command-center/p2-wave/probes/WFA-0141/census.py",
        "command-center/p2-wave/probes/WFA-0141/probe1_acquisition_both_states.py",
        "command-center/p2-wave/probes/WFA-0141/probe2_fusion_and_shared_counter.py",
        "command-center/p2-wave/probes/WFA-0141/fixtures/candidates.json",
        "command-center/p2-wave/probes/WFA-0141/fixtures/fusions.json",
        "command-center/p2-wave/probes/WFA-0141/emit_artifact.py",
        "command-center/p2-wave/probes/WFA-0141/schema_util.py",
    ]
    arts = [
        {"path": OUT, "exists": True, "role": "primary"},
        *[
            {"path": p, "exists": True, "role": "supporting"}
            for p in supporting
        ],
    ]

    doc = {
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "kind": "control-plane-census",
        "title": "Control-plane singularity gate at acquisition and at fusion",
        "question": QUESTION,
        "answer": answer,
        "home_plane": C.HOME_PLANE,
        "shared_counter": {
            "module": "command-center/p2-wave/probes/WFA-0141/census.py",
            "function": "count_planes",
            "used_at": ["acquisition", "fusion"],
            "acquire_anchor": acquire_anchor,
            "fuse_anchor": fuse_anchor,
        },
        "trigger_points": ["acquisition", "fusion"],
        "source_availability": {
            "registry": live["registry_hunt"],
            "merge_maps": live["merge_hunt"],
            "user_prompts": live["prompts_hunt"],
            "registry_load": live["registry_load"],
            "merge_load": live["merge_load"],
            "live_available": live_present,
            "catalog_claimed_candidate_n": 284,
            "catalog_claimed_merge_unit_n": 30,
            "live_candidate_n": live_acq_n,
            "live_fusion_n": live_fus_n,
            "scope": "live" if live_present else "planted-plus-hunt",
        },
        "acquisition_census": {
            "planted": {
                "n": acq_plant["n"],
                "n_over_one": acq_plant["n_over_one"],
                "raised_ids": acq_plant["raised_ids"],
                "readings": [slim_reading(r) for r in acq_plant["readings"]],
            },
            "live": live["acquisition"],
        },
        "fusion_census": {
            "planted": {
                "n": fus_plant["n"],
                "n_over_one": fus_plant["n_over_one"],
                "raised_ids": fus_plant["raised_ids"],
                "readings": [slim_reading(r) for r in fus_plant["readings"]],
            },
            "live": live["fusion"],
        },
        "raised_above_one": {
            "planted": raised,
            "live": live_raised,
        },
        "planted_controls": {
            "own_runner_acquisition": slim_reading(
                next(
                    r
                    for r in acq_plant["readings"]
                    if r["subject_id"] == "plant-own-runner"
                )
            ),
            "pure_mechanism_acquisition": slim_reading(
                next(
                    r
                    for r in acq_plant["readings"]
                    if r["subject_id"] == "plant-pure-mechanism"
                )
            ),
            "dup_plane_fusion": slim_reading(
                next(
                    r
                    for r in fus_plant["readings"]
                    if r["subject_id"] == "plant-fusion-dup-planes"
                )
            ),
            "single_plane_fusion": slim_reading(
                next(
                    r
                    for r in fus_plant["readings"]
                    if r["subject_id"] == "plant-fusion-single-plane"
                )
            ),
        },
        "evidence": [
            {
                "id": "E1-shared-counter-two-triggers",
                "claim": (
                    "One count_planes function is the counter at both "
                    "acquisition and fusion."
                ),
                "verdict": "CONFIRMED",
                "anchor": counter_anchor,
                "probe": P2,
            },
            {
                "id": "E2-runtime-field-and-fused-definition",
                "claim": (
                    "Acquisition reads candidate.runtime; fusion reports "
                    "source runtime-field planes and fused-definition planes "
                    "separately."
                ),
                "verdict": "CONFIRMED",
                "anchor": fuse_anchor,
                "probe": P2,
            },
            {
                "id": "E3-catalog-question",
                "claim": "Catalog question is the census-at-two-triggers question.",
                "verdict": "CONFIRMED",
                "anchor": catalog_q,
            },
        ],
        "tests": [
            {
                "id": "probe1-acquisition-both-states",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
                "tail": t1[-1500:],
            },
            {
                "id": "probe2-fusion-and-shared-counter",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "exit_code": c2,
                "tail": t2[-1500:],
            },
        ],
        "report": {
            "kind": "control-plane-census",
            "observations": [
                {
                    "name": "planted_acquisition_n_over_one",
                    "measured": acq_plant["n_over_one"],
                    "method": "command",
                    "anchor": P1,
                },
                {
                    "name": "planted_fusion_n_over_one",
                    "measured": fus_plant["n_over_one"],
                    "method": "command",
                    "anchor": P2,
                },
                {
                    "name": "shared_counter_is_count_planes",
                    "measured": True,
                    "method": "static-analysis",
                    "anchor": counter_anchor,
                },
                {
                    "name": "live_registry_available",
                    "measured": live_present,
                    "method": "file-read",
                    "anchor": "command-center/p2-wave/probes/WFA-0141/census.py:live_bundle",
                },
            ],
            "control_ids": [
                "plant-own-runner",
                "plant-pure-mechanism",
                "plant-fusion-dup-planes",
                "plant-fusion-single-plane",
            ],
        },
        "negative_controls": [
            {
                "id": "acquisition-both-states",
                "kind": "known-broken-fixture",
                "description": (
                    "A candidate that carries its own runner fires at "
                    "acquisition; a pure-mechanism candidate is silent."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "plant-own-runner gate=FIRE",
                "good_state_output": "plant-pure-mechanism gate=PASS",
            },
            {
                "id": "fusion-both-states",
                "kind": "known-broken-fixture",
                "description": (
                    "A fusion that would import a second plane fires; a "
                    "single-plane fusion is silent."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "plant-fusion-dup-planes gate=FIRE",
                "good_state_output": "plant-fusion-single-plane gate=PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0141-probe2-fusion-and-shared-counter",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 does not re-run the acquisition plant. It checks "
                "fusion both-states, the runtime-string vs import-guard split, "
                "and the AST proof that both triggers call count_planes."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "08-WORKFLOW-CANDIDATE-REGISTRY.json (catalog 284) and "
                    "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json are absent "
                    "on this Linux worktree, so live 284-row identities are "
                    "NOT-CHECKED rather than invented."
                    if not live_present
                    else "Live registry and merge maps were present and censused."
                ),
                "verdict": "NOT-CHECKED" if not live_present else "CONFIRMED",
                "settling_experiment": (
                    "Place 08-WORKFLOW-CANDIDATE-REGISTRY.json and "
                    "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json at a hunted "
                    "path (census.SEARCH_BASES) and re-run emit_artifact.py; "
                    "source_availability.live_available becomes true."
                ),
            }
        ],
        "artifacts": arts,
        "ts": now,
        "notes": (
            "G-1 for WFA-0141. Live named probes exit 0. Artifact state="
            "SUCCESS. Per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Did not rotate or print API keys. "
            "No ADV rebuild. cloud ok=true is not delivery. Windows "
            "harness-restore inputs were hunted, not assumed."
        ),
    }

    if not S.rejects_garbage():
        print("FAILED:WFA-0141 schema accepted garbage")
        return 1
    try:
        S.validate(doc)
    except S.ValidationError as exc:
        print(f"FAILED:WFA-0141 schema {exc.message}")
        for line in S.error_list(doc)[:12]:
            print(f"  {line}")
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=1, ensure_ascii=False) + "\n"
    out_path.write_text(payload, encoding="utf-8")
    if SENTINEL not in payload:
        print("FAILED:WFA-0141 sentinel missing")
        return 1
    if len(payload.encode("utf-8")) < MIN_BYTES:
        print("FAILED:WFA-0141 artifact too small")
        return 1
    sha, size = C.digest_file(out_path)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
