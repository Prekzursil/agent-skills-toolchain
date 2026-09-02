#!/usr/bin/env python3
"""Source workflows and one fusion per operator for WFA-0063."""
from __future__ import annotations

from typing import Any

from engine import OPERATORS, apply_rename, certify, decompose, fuse, plant_lossy, workflow_fp

SENTINEL = "SUCCESS:WFA-0063"


def _stage(
    sid: str,
    mechanism: str,
    op: str,
    *,
    slot: str | None = None,
    params: dict[str, Any] | None = None,
    license: str = "Apache-2.0",
    source: str = "",
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "id": sid,
        "kind": "transform",
        "mechanism": mechanism,
        "op": op,
        "params": params or {},
        "in_type": "int",
        "out_type": "int",
        "anchor": f"fixture:{source}/stages/{sid}" if source else f"fixture:stage/{sid}",
        "license": license,
    }
    if slot is not None:
        body["slot"] = slot
    return body


def _wf(
    wid: str,
    stages: list[dict[str, Any]],
    smoke_in: int,
    smoke_out: int,
    *,
    license: str = "Apache-2.0",
    credit: str | None = None,
) -> dict[str, Any]:
    tagged = []
    for st in stages:
        item = dict(st)
        if not item.get("anchor") or item["anchor"].startswith("fixture:stage/"):
            item["anchor"] = f"fixture:{wid}/stages/{item['id']}"
        item["license"] = license
        tagged.append(item)
    mechs: list[str] = []
    for st in tagged:
        m = st["mechanism"]
        if m not in mechs:
            mechs.append(m)
    return {
        "id": wid,
        "kind": "source",
        "stages": tagged,
        "mechanisms": mechs,
        "roles": ["worker"],
        "license": license,
        "credit": credit or f"{wid}-authors",
        "anchor": f"fixture:{wid}",
        "smoke": {"input": smoke_in, "expected": smoke_out, "mode": "pipeline"},
    }


def make_sources() -> dict[str, dict[str, Any]]:
    # 3 -> inc=4 -> double=8
    alpha = _wf(
        "wf.alpha",
        [
            _stage("inc", "mech.increment", "inc", source="wf.alpha"),
            _stage("dbl", "mech.double", "double", source="wf.alpha"),
        ],
        3,
        8,
        credit="alpha-authors",
    )
    # 3 -> add_k(5)=8
    beta = _wf(
        "wf.beta",
        [_stage("add", "mech.shift", "add_k", params={"k": 5}, source="wf.beta")],
        3,
        8,
        license="MIT",
        credit="beta-authors",
    )
    # 3 -> square=9
    gamma = _wf(
        "wf.gamma",
        [_stage("sq", "mech.square", "square", source="wf.gamma")],
        3,
        9,
        credit="gamma-authors",
    )
    # shared prefix inc,double then add_k vs square
    core_a = _wf(
        "wf.core.a",
        [
            _stage("inc", "mech.increment", "inc", source="wf.core.a"),
            _stage("dbl", "mech.double", "double", source="wf.core.a"),
            _stage("k", "mech.shift", "add_k", params={"k": 1}, source="wf.core.a"),
        ],
        3,
        9,
    )
    core_b = _wf(
        "wf.core.b",
        [
            _stage("inc", "mech.increment", "inc", source="wf.core.b"),
            _stage("dbl", "mech.double", "double", source="wf.core.b"),
            _stage("sq", "mech.square", "square", source="wf.core.b"),
        ],
        3,
        64,
    )
    bob_a = _wf(
        "wf.bob.a",
        [
            _stage("s0", "mech.increment", "inc", slot="s0", source="wf.bob.a"),
            _stage("s1", "mech.double", "double", slot="s1", source="wf.bob.a"),
        ],
        3,
        8,
    )
    bob_b = _wf(
        "wf.bob.b",
        [
            _stage("s0", "mech.shift", "add_k", slot="s0", params={"k": 2}, source="wf.bob.b"),
            _stage("s1", "mech.square", "square", slot="s1", source="wf.bob.b"),
        ],
        3,
        25,
    )
    cheap = _wf(
        "wf.cheap",
        [_stage("id", "mech.ident", "ident", source="wf.cheap")],
        3,
        3,
    )
    expensive = _wf(
        "wf.expensive",
        [
            _stage("sq", "mech.square", "square", source="wf.expensive"),
            _stage("inc", "mech.increment", "inc", source="wf.expensive"),
        ],
        3,
        10,
    )
    return {
        "wf.alpha": alpha,
        "wf.beta": beta,
        "wf.gamma": gamma,
        "wf.core.a": core_a,
        "wf.core.b": core_b,
        "wf.bob.a": bob_a,
        "wf.bob.b": bob_b,
        "wf.cheap": cheap,
        "wf.expensive": expensive,
    }


def operator_plan(sources: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        "stage-splice": {
            "sources": [sources["wf.alpha"], sources["wf.gamma"]],
            "params": {"index": 1, "donor_stage_id": "sq"},
        },
        "common-core": {
            "sources": [sources["wf.core.a"], sources["wf.core.b"]],
            "params": {"core_len": 2},
        },
        "union": {
            "sources": [sources["wf.alpha"], sources["wf.beta"]],
            "params": {},
        },
        "best-of-breed": {
            "sources": [sources["wf.bob.a"], sources["wf.bob.b"]],
            "params": {
                "scores": {
                    "s0": {"wf.bob.a": 9.0, "wf.bob.b": 2.0},
                    "s1": {"wf.bob.a": 3.0, "wf.bob.b": 8.0},
                },
                "tie_break": "lexicographic-min-source-id",
            },
        },
        "conditional-hybrid": {
            "sources": [sources["wf.alpha"], sources["wf.beta"]],
            "params": {"predicate": "gt0", "default": "wf.beta"},
        },
        "ensemble": {
            "sources": [sources["wf.alpha"], sources["wf.beta"]],
            "params": {"aggregator": "sum"},
        },
        "progressive": {
            "sources": [sources["wf.cheap"], sources["wf.expensive"]],
            "params": {"adequacy": "gte5"},
        },
    }


def live_results() -> dict[str, Any]:
    sources = make_sources()
    plan = operator_plan(sources)
    if set(plan) != set(OPERATORS):
        raise RuntimeError(f"plan/operators mismatch {sorted(plan)} vs {list(OPERATORS)}")

    per_operator: list[dict[str, Any]] = []
    for operator in OPERATORS:
        spec = plan[operator]
        fusion = fuse(operator, spec["sources"], spec["params"])
        cert = certify(fusion)
        recovered = decompose(fusion) if cert["verdict"] == "CERTIFIED" else []
        expected_ids = sorted(s["id"] for s in spec["sources"])
        recovered_ids = sorted(s["id"] for s in recovered)
        fp_hits = []
        for rec in recovered:
            matches = [
                sid
                for sid, orig in sources.items()
                if workflow_fp(orig) == workflow_fp(rec)
            ]
            fp_hits.append({"recovered_id": rec["id"], "matched_source_ids": matches})
        per_operator.append(
            {
                "operator": operator,
                "fusion_id": fusion["id"],
                "expected_ids": expected_ids,
                "recovered_ids": recovered_ids,
                "id_set_equal": expected_ids == recovered_ids,
                "certification": cert["verdict"],
                "rehearsal": cert["rehearsal"],
                "fingerprint_matches": fp_hits,
                "stage_count": len(fusion["stages"]),
            }
        )

    certified_ok = all(
        row["certification"] == "CERTIFIED" and row["id_set_equal"]
        for row in per_operator
    )

    union_fusion = fuse(
        "union", plan["union"]["sources"], plan["union"]["params"]
    )
    lossy_rows = []
    for mode in ("strip-components", "drop-lineage", "drop-one-component"):
        planted = plant_lossy(union_fusion, mode)
        verdict = certify(planted)
        lossy_rows.append(
            {
                "mode": mode,
                "verdict": verdict["verdict"],
                "reason": verdict["reason"],
                "note_ignored": verdict["note_ignored"],
                "shipped_with_note": False,
            }
        )
    lossy_all_rejected = all(r["verdict"] == "REJECTED" for r in lossy_rows)

    old_id = union_fusion["lineage"]["source_ids"][0]
    new_id = f"{old_id}.renamed"
    renamed = apply_rename(union_fusion, old_id, new_id)
    renamed_cert = certify(renamed)
    renamed_recovered = (
        decompose(renamed) if renamed_cert["verdict"] == "CERTIFIED" else []
    )
    mmap = renamed["lineage"]["id_migration_map"]
    rename_ok = (
        renamed_cert["verdict"] == "CERTIFIED"
        and new_id in {s["id"] for s in renamed_recovered}
        and mmap.get(old_id) == new_id
        and all(r["ok"] for r in renamed_cert["rehearsal"].values())
    )

    rehearsal_ops = [
        row["operator"]
        for row in per_operator
        if row["certification"] == "CERTIFIED"
        and row["rehearsal"]
        and all(v.get("ok") for v in row["rehearsal"].values())
    ]

    return {
        "sentinel": SENTINEL,
        "operators": list(OPERATORS),
        "per_operator": per_operator,
        "certified_ok": certified_ok,
        "lossy": lossy_rows,
        "lossy_all_rejected": lossy_all_rejected,
        "rename": {
            "old_id": old_id,
            "new_id": new_id,
            "map": mmap,
            "certification": renamed_cert["verdict"],
            "recovered_ids": sorted(s["id"] for s in renamed_recovered),
            "ok": rename_ok,
        },
        "rehearsal_operators": rehearsal_ops,
        "rehearsal_covers_all_operators": set(rehearsal_ops) == set(OPERATORS),
        "pass": (
            certified_ok
            and lossy_all_rejected
            and rename_ok
            and set(rehearsal_ops) == set(OPERATORS)
        ),
    }
