#!/usr/bin/env python3
"""Invertible fusion encodings and decompose() for IMP-0180.

Eight strategies, matching IMP-0182..IMP-0189:
  stage-splice, common-core, union, best-of-breed,
  conditional-hybrid, ensemble, progressive, meta-workflow.

decompose(fuse(a, b)) recovers {a, b} under structural_fingerprint.
The fused object has no sidecar `sources` list: each strategy stores a
strategy-specific encoding, and decompose inverts that encoding.

A planted lossy encoding (make_lossy) drops the recovery material so the
inverse fails — the detector for the unit's second signal.
"""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Callable

STRATEGIES: tuple[str, ...] = (
    "stage-splice",
    "common-core",
    "union",
    "best-of-breed",
    "conditional-hybrid",
    "ensemble",
    "progressive",
    "meta-workflow",
)

AGGREGATION_RULES = frozenset(
    {"majority", "weighted", "evidence-gated", "execution-consensus"}
)


class FusionRefused(ValueError):
    """Contract mismatch or missing recovery material."""


class InverseBroken(ValueError):
    """decompose() cannot recover both source fingerprints."""


def canonical_stage(stage: dict) -> dict:
    return {
        "contract_in": stage["contract_in"],
        "contract_out": stage["contract_out"],
        "gate": stage["gate"],
        "kind": stage["kind"],
        "roles": sorted(stage["roles"]),
        "tools": sorted(stage["tools"]),
    }


def stage_key(stage: dict) -> str:
    return json.dumps(canonical_stage(stage), sort_keys=True, separators=(",", ":"))


def linear_topology(n: int) -> list[list[int]]:
    return [[i, i + 1] for i in range(n - 1)]


def _topo(wf: dict) -> list[list[int]]:
    topo = wf.get("topology")
    if topo:
        return [list(e) for e in topo]
    return linear_topology(len(wf["stages"]))


def structural_fingerprint(wf: dict) -> str:
    """Rename-invariant fingerprint over kinds, roles, gates, tool classes, topology.

    Identifier fields (`id`, `name`) and scores are excluded. Changing a gate
    predicate or dropping topology from the hash changes the digest.
    """
    stages = [canonical_stage(s) for s in wf["stages"]]
    edges = []
    for i, j in _topo(wf):
        edges.append([stages[i], stages[j]])
    blob = {
        "role_set": sorted({r for s in wf["stages"] for r in s["roles"]}),
        "stages": stages,
        "tool_classes": sorted({t for s in wf["stages"] for t in s["tools"]}),
        "topology": edges,
    }
    raw = json.dumps(blob, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def workflow(
    wid: str,
    stages: list[dict],
    *,
    topology: list[list[int]] | None = None,
    license_id: str = "Apache-2.0",
) -> dict:
    body = {
        "id": wid,
        "license": license_id,
        "stages": [copy.deepcopy(s) for s in stages],
        "topology": topology if topology is not None else linear_topology(len(stages)),
    }
    return body


def _stage(
    sid: str,
    kind: str,
    gate: str,
    tools: list[str],
    roles: list[str],
    cin: str,
    cout: str,
    score: float,
) -> dict:
    return {
        "id": sid,
        "kind": kind,
        "gate": gate,
        "tools": list(tools),
        "roles": list(roles),
        "contract_in": cin,
        "contract_out": cout,
        "score": score,
    }


def source_a() -> dict:
    """Cheap/host workflow: ingest -> analyze -> gate."""
    return workflow(
        "wf.scout-analyze",
        [
            _stage(
                "a-ingest",
                "ingest",
                "has_input",
                ["http"],
                ["scout"],
                "raw",
                "doc",
                0.60,
            ),
            _stage(
                "a-analyze",
                "analyze",
                "doc_ok",
                ["llm"],
                ["analyst"],
                "doc",
                "findings",
                0.55,
            ),
            _stage(
                "a-gate",
                "gate",
                "findings_complete",
                ["schema"],
                ["skeptic"],
                "findings",
                "ok",
                0.70,
            ),
        ],
        license_id="Apache-2.0",
    )


def source_b() -> dict:
    """Thorough/donor workflow: ingest -> deep-analyze -> repair -> verify."""
    return workflow(
        "wf.forge-verify",
        [
            _stage(
                "b-ingest",
                "ingest",
                "has_input",
                ["http"],
                ["scout"],
                "raw",
                "doc",
                0.80,
            ),
            _stage(
                "b-analyze",
                "analyze",
                "doc_deep",
                ["llm", "rag"],
                ["analyst"],
                "doc",
                "findings",
                0.92,
            ),
            _stage(
                "b-repair",
                "repair",
                "needs_fix",
                ["patch"],
                ["fixer"],
                "findings",
                "findings",
                0.66,
            ),
            _stage(
                "b-verify",
                "verify",
                "tests_green",
                ["pytest"],
                ["tester"],
                "findings",
                "ok",
                0.85,
            ),
        ],
        license_id="MIT",
    )


def _meta(wf: dict) -> dict:
    return {"id": wf["id"], "license": wf["license"]}


def _pack(wf: dict) -> dict:
    return {
        "meta": _meta(wf),
        "stages": copy.deepcopy(wf["stages"]),
        "topology": _topo(wf),
    }


def _unpack(pack: dict) -> dict:
    if not isinstance(pack, dict) or "stages" not in pack or "meta" not in pack:
        raise InverseBroken("missing packed workflow")
    return workflow(
        pack["meta"]["id"],
        pack["stages"],
        topology=pack.get("topology"),
        license_id=pack["meta"].get("license", "UNLICENSED"),
    )


def fused_plan_stages(fusion: dict) -> list[dict]:
    """Executable stage list of the fusion (not the recovered sources)."""
    enc = fusion["encoding"]
    st = fusion["strategy"]
    if st == "stage-splice":
        return list(enc["host_prefix"]) + [enc["inserted"]] + list(enc["host_suffix"])
    if st == "common-core":
        return list(enc["core"])
    if st == "union":
        return [row["stage"] for row in enc["collapsed"]]
    if st == "best-of-breed":
        return [row["winner_stage"] for row in enc["slots"] if row.get("winner_stage")]
    if st == "conditional-hybrid":
        return [
            {
                "id": "router",
                "kind": "router",
                "gate": enc["predicate"],
                "tools": ["dispatch"],
                "roles": ["router"],
                "contract_in": "raw",
                "contract_out": "ok",
                "score": 0.0,
            }
        ]
    if st == "ensemble":
        return [
            {
                "id": "aggregator",
                "kind": "aggregate",
                "gate": enc["aggregation"]["rule"],
                "tools": ["ensemble"],
                "roles": ["aggregator"],
                "contract_in": "ok",
                "contract_out": "ok",
                "score": 0.0,
            }
        ]
    if st == "progressive":
        return [
            {
                "id": "escalate",
                "kind": "escalate",
                "gate": enc["escalate_predicate"],
                "tools": ["budget"],
                "roles": ["dispatcher"],
                "contract_in": "raw",
                "contract_out": "ok",
                "score": 0.0,
            }
        ]
    if st == "meta-workflow":
        return [
            {
                "id": "sub-" + child["meta"]["id"],
                "kind": "subworkflow",
                "gate": "child_complete",
                "tools": ["compose"],
                "roles": ["parent"],
                "contract_in": "raw",
                "contract_out": "ok",
                "score": 0.0,
            }
            for child in enc["children"]
        ]
    raise FusionRefused(f"unknown strategy {st}")


def _fusion(strategy: str, encoding: dict) -> dict:
    return {"strategy": strategy, "encoding": encoding}


# --- stage-splice -----------------------------------------------------------


def _neighbour_contracts(host: dict, at: int, donor_stage: dict) -> None:
    stages = host["stages"]
    if at < 0 or at >= len(stages):
        raise FusionRefused(f"splice index {at} out of range")
    if at > 0 and stages[at - 1]["contract_out"] != donor_stage["contract_in"]:
        raise FusionRefused(
            "splice contract mismatch with predecessor: "
            f"{stages[at - 1]['contract_out']} != {donor_stage['contract_in']}"
        )
    if at + 1 < len(stages) and stages[at + 1]["contract_in"] != donor_stage["contract_out"]:
        raise FusionRefused(
            "splice contract mismatch with successor: "
            f"{donor_stage['contract_out']} != {stages[at + 1]['contract_in']}"
        )


def fuse_stage_splice(a: dict, b: dict, *, at: int = 1, donor_index: int = 1) -> dict:
    donor_stage = copy.deepcopy(b["stages"][donor_index])
    _neighbour_contracts(a, at, donor_stage)
    host_stages = a["stages"]
    return _fusion(
        "stage-splice",
        {
            "at": at,
            "donor_index": donor_index,
            "host_prefix": copy.deepcopy(host_stages[:at]),
            "removed": copy.deepcopy(host_stages[at]),
            "inserted": donor_stage,
            "host_suffix": copy.deepcopy(host_stages[at + 1 :]),
            "host_topology": _topo(a),
            "host_meta": _meta(a),
            "donor_prefix": copy.deepcopy(b["stages"][:donor_index]),
            "donor_suffix": copy.deepcopy(b["stages"][donor_index + 1 :]),
            "donor_topology": _topo(b),
            "donor_meta": _meta(b),
        },
    )


def decompose_stage_splice(enc: dict) -> list[dict]:
    for key in (
        "host_prefix",
        "removed",
        "inserted",
        "host_suffix",
        "donor_prefix",
        "donor_suffix",
        "host_meta",
        "donor_meta",
    ):
        if key not in enc:
            raise InverseBroken(f"stage-splice missing {key}")
    host = workflow(
        enc["host_meta"]["id"],
        list(enc["host_prefix"]) + [enc["removed"]] + list(enc["host_suffix"]),
        topology=enc.get("host_topology"),
        license_id=enc["host_meta"].get("license", "UNLICENSED"),
    )
    donor = workflow(
        enc["donor_meta"]["id"],
        list(enc["donor_prefix"]) + [enc["inserted"]] + list(enc["donor_suffix"]),
        topology=enc.get("donor_topology"),
        license_id=enc["donor_meta"].get("license", "UNLICENSED"),
    )
    return [host, donor]


# --- common-core ------------------------------------------------------------


def fuse_common_core(a: dict, b: dict) -> dict:
    keys_a = [stage_key(s) for s in a["stages"]]
    keys_b = [stage_key(s) for s in b["stages"]]
    shared = [k for k in keys_a if k in set(keys_b)]
    by_a = {stage_key(s): s for s in a["stages"]}
    core = [copy.deepcopy(by_a[k]) for k in shared]
    delta_a = {
        k: copy.deepcopy(s) for k, s in zip(keys_a, a["stages"]) if k not in set(shared)
    }
    delta_b = {
        k: copy.deepcopy(s) for k, s in zip(keys_b, b["stages"]) if k not in set(shared)
    }
    if not core:
        raise FusionRefused("common-core empty intersection")
    return _fusion(
        "common-core",
        {
            "core": core,
            "a": {
                "order": keys_a,
                "delta": delta_a,
                "topology": _topo(a),
                "meta": _meta(a),
            },
            "b": {
                "order": keys_b,
                "delta": delta_b,
                "topology": _topo(b),
                "meta": _meta(b),
            },
        },
    )


def _recompose_core(core: list[dict], side: dict) -> dict:
    if not isinstance(side, dict) or "order" not in side or "delta" not in side:
        raise InverseBroken("common-core side missing order/delta")
    core_map = {stage_key(s): s for s in core}
    stages = []
    for key in side["order"]:
        if key in core_map:
            stages.append(copy.deepcopy(core_map[key]))
        elif key in side["delta"]:
            stages.append(copy.deepcopy(side["delta"][key]))
        else:
            raise InverseBroken(f"common-core cannot recompose key {key[:48]}")
    return workflow(
        side["meta"]["id"],
        stages,
        topology=side.get("topology"),
        license_id=side["meta"].get("license", "UNLICENSED"),
    )


def decompose_common_core(enc: dict) -> list[dict]:
    if "core" not in enc or "a" not in enc or "b" not in enc:
        raise InverseBroken("common-core missing core or a/b delta")
    return [_recompose_core(enc["core"], enc["a"]), _recompose_core(enc["core"], enc["b"])]


# --- union ------------------------------------------------------------------


def fuse_union(a: dict, b: dict) -> dict:
    collapsed: list[dict] = []
    index: dict[str, int] = {}
    for origin, wf in (("a", a), ("b", b)):
        for stage in wf["stages"]:
            key = stage_key(stage)
            if key in index:
                collapsed[index[key]]["origins"].append(origin)
            else:
                index[key] = len(collapsed)
                collapsed.append(
                    {
                        "key": key,
                        "origins": [origin],
                        "stage": copy.deepcopy(stage),
                    }
                )
    return _fusion(
        "union",
        {
            "collapsed": collapsed,
            "sequence_a": [stage_key(s) for s in a["stages"]],
            "sequence_b": [stage_key(s) for s in b["stages"]],
            "topo_a": _topo(a),
            "topo_b": _topo(b),
            "meta_a": _meta(a),
            "meta_b": _meta(b),
        },
    )


def _replay_union(enc: dict, seq_key: str, topo_key: str, meta_key: str) -> dict:
    if seq_key not in enc or meta_key not in enc:
        raise InverseBroken(f"union missing {seq_key}")
    by_key = {row["key"]: row["stage"] for row in enc.get("collapsed") or []}
    stages = []
    for key in enc[seq_key]:
        if key not in by_key:
            raise InverseBroken(f"union sequence key absent from collapsed: {key[:48]}")
        stages.append(copy.deepcopy(by_key[key]))
    meta = enc[meta_key]
    return workflow(
        meta["id"],
        stages,
        topology=enc.get(topo_key),
        license_id=meta.get("license", "UNLICENSED"),
    )


def decompose_union(enc: dict) -> list[dict]:
    return [
        _replay_union(enc, "sequence_a", "topo_a", "meta_a"),
        _replay_union(enc, "sequence_b", "topo_b", "meta_b"),
    ]


# --- best-of-breed ----------------------------------------------------------


def _slot_id(stage: dict) -> str:
    return json.dumps(
        {
            "contract_in": stage["contract_in"],
            "contract_out": stage["contract_out"],
            "kind": stage["kind"],
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def fuse_best_of_breed(a: dict, b: dict) -> dict:
    slots: dict[str, dict] = {}
    order: list[str] = []

    def add(origin: str, stage: dict) -> None:
        sid = _slot_id(stage)
        if sid not in slots:
            order.append(sid)
            slots[sid] = {
                "slot": sid,
                "candidates": {},
                "winner": None,
                "winner_stage": None,
            }
        slots[sid]["candidates"][origin] = copy.deepcopy(stage)

    for s in a["stages"]:
        add("a", s)
    for s in b["stages"]:
        add("b", s)

    for sid in order:
        row = slots[sid]
        cands = row["candidates"]
        if "a" in cands and "b" in cands:
            winner = "b" if cands["b"]["score"] > cands["a"]["score"] else "a"
        else:
            winner = "a" if "a" in cands else "b"
        row["winner"] = winner
        row["winner_stage"] = copy.deepcopy(cands[winner])
        if "a" not in cands or "b" not in cands:
            if any(v is None for v in cands.values()):
                raise FusionRefused("best-of-breed no-evidence stage")

    return _fusion(
        "best-of-breed",
        {
            "slots": [slots[sid] for sid in order],
            "order_a": [_slot_id(s) for s in a["stages"]],
            "order_b": [_slot_id(s) for s in b["stages"]],
            "topo_a": _topo(a),
            "topo_b": _topo(b),
            "meta_a": _meta(a),
            "meta_b": _meta(b),
        },
    )


def _replay_breed(enc: dict, origin: str, order_key: str, topo_key: str, meta_key: str) -> dict:
    if order_key not in enc or meta_key not in enc:
        raise InverseBroken(f"best-of-breed missing {order_key}")
    by_slot = {row["slot"]: row for row in enc.get("slots") or []}
    stages = []
    for sid in enc[order_key]:
        row = by_slot.get(sid)
        if not row or origin not in (row.get("candidates") or {}):
            raise InverseBroken(f"best-of-breed missing {origin} candidate for {sid[:48]}")
        stages.append(copy.deepcopy(row["candidates"][origin]))
    meta = enc[meta_key]
    return workflow(
        meta["id"],
        stages,
        topology=enc.get(topo_key),
        license_id=meta.get("license", "UNLICENSED"),
    )


def decompose_best_of_breed(enc: dict) -> list[dict]:
    return [
        _replay_breed(enc, "a", "order_a", "topo_a", "meta_a"),
        _replay_breed(enc, "b", "order_b", "topo_b", "meta_b"),
    ]


# --- wrapping strategies ----------------------------------------------------


def fuse_conditional_hybrid(a: dict, b: dict) -> dict:
    return _fusion(
        "conditional-hybrid",
        {
            "predicate": "input.source_kind == git",
            "default_branch": "a",
            "reachable": ["a", "b"],
            "branch_a": _pack(a),
            "branch_b": _pack(b),
        },
    )


def decompose_conditional_hybrid(enc: dict) -> list[dict]:
    if "branch_a" not in enc or "branch_b" not in enc:
        raise InverseBroken("conditional-hybrid missing a branch")
    return [_unpack(enc["branch_a"]), _unpack(enc["branch_b"])]


def fuse_ensemble(a: dict, b: dict) -> dict:
    rule = "execution-consensus"
    if rule not in AGGREGATION_RULES:
        raise FusionRefused("aggregation rule not in closed set")
    return _fusion(
        "ensemble",
        {
            "aggregation": {"rule": rule, "typed": True},
            "member_a": _pack(a),
            "member_b": _pack(b),
            "independence": "distinct-tool-classes",
        },
    )


def decompose_ensemble(enc: dict) -> list[dict]:
    if "member_a" not in enc or "member_b" not in enc:
        raise InverseBroken("ensemble missing a member")
    return [_unpack(enc["member_a"]), _unpack(enc["member_b"])]


def fuse_progressive(a: dict, b: dict) -> dict:
    return _fusion(
        "progressive",
        {
            "cheap": _pack(a),
            "expensive": _pack(b),
            "escalate_predicate": "cheap.gate == fail",
        },
    )


def decompose_progressive(enc: dict) -> list[dict]:
    if "cheap" not in enc or "expensive" not in enc:
        raise InverseBroken("progressive missing a tier")
    return [_unpack(enc["cheap"]), _unpack(enc["expensive"])]


def fuse_meta_workflow(a: dict, b: dict) -> dict:
    ba, bb = 3, 4
    return _fusion(
        "meta-workflow",
        {
            "children": [_pack(a), _pack(b)],
            "budget_ledger": {
                "a": ba,
                "b": bb,
                "parent": ba + bb,
                "double_count": False,
            },
            "failure_policy": "continue",
        },
    )


def decompose_meta_workflow(enc: dict) -> list[dict]:
    children = enc.get("children")
    if not isinstance(children, list) or len(children) < 2:
        raise InverseBroken("meta-workflow missing children")
    return [_unpack(children[0]), _unpack(children[1])]


FUSE: dict[str, Callable[[dict, dict], dict]] = {
    "stage-splice": fuse_stage_splice,
    "common-core": fuse_common_core,
    "union": fuse_union,
    "best-of-breed": fuse_best_of_breed,
    "conditional-hybrid": fuse_conditional_hybrid,
    "ensemble": fuse_ensemble,
    "progressive": fuse_progressive,
    "meta-workflow": fuse_meta_workflow,
}

DECOMPOSE: dict[str, Callable[[dict], list[dict]]] = {
    "stage-splice": decompose_stage_splice,
    "common-core": decompose_common_core,
    "union": decompose_union,
    "best-of-breed": decompose_best_of_breed,
    "conditional-hybrid": decompose_conditional_hybrid,
    "ensemble": decompose_ensemble,
    "progressive": decompose_progressive,
    "meta-workflow": decompose_meta_workflow,
}


def fuse(strategy: str, a: dict, b: dict) -> dict:
    if strategy not in FUSE:
        raise FusionRefused(f"unknown strategy {strategy}")
    out = FUSE[strategy](a, b)
    if "sources" in out:
        raise FusionRefused("sidecar sources are not an inverse")
    return out


def decompose(fusion: dict) -> list[dict]:
    if not isinstance(fusion, dict) or "strategy" not in fusion:
        raise InverseBroken("not a fusion encoding")
    if "sources" in fusion:
        raise InverseBroken("sidecar sources are refused; invert the encoding")
    st = fusion["strategy"]
    if st not in DECOMPOSE:
        raise InverseBroken(f"unknown strategy {st}")
    enc = fusion.get("encoding")
    if not isinstance(enc, dict):
        raise InverseBroken("missing encoding")
    return DECOMPOSE[st](enc)


def wire_roundtrip(fusion: dict) -> dict:
    return json.loads(json.dumps(fusion))


def inverse_holds(strategy: str, a: dict, b: dict, fused: dict | None = None) -> dict:
    """True iff decompose(fuse(a,b)) recovers {fp(a), fp(b)} after JSON round-trip."""
    want = {structural_fingerprint(a), structural_fingerprint(b)}
    try:
        if fused is None:
            fused = fuse(strategy, a, b)
        recovered = decompose(wire_roundtrip(fused))
        got = {structural_fingerprint(w) for w in recovered}
        ok = got == want
        return {
            "ok": ok,
            "strategy": strategy,
            "want": sorted(want),
            "got": sorted(got),
            "recovered_n": len(recovered),
            "error": None,
        }
    except (FusionRefused, InverseBroken, KeyError, TypeError, IndexError) as exc:
        return {
            "ok": False,
            "strategy": strategy,
            "want": sorted(want),
            "got": [],
            "recovered_n": 0,
            "error": f"{type(exc).__name__}: {exc}",
        }


LOSSY_DROPS: dict[str, tuple[str, ...]] = {
    "stage-splice": ("removed", "donor_prefix", "donor_suffix"),
    "common-core": ("b",),
    "union": ("sequence_b",),
    "best-of-breed": ("order_b",),
    "conditional-hybrid": ("branch_b",),
    "ensemble": ("member_b",),
    "progressive": ("expensive",),
    "meta-workflow": ("children",),
}


def make_lossy(fusion: dict) -> dict:
    """Deliberately drop recovery material. Inverse must fail."""
    out = copy.deepcopy(fusion)
    drops = LOSSY_DROPS[fusion["strategy"]]
    for key in drops:
        out["encoding"].pop(key, None)
    if fusion["strategy"] == "meta-workflow":
        # leave a single child so the object still looks like a fusion
        kids = fusion["encoding"].get("children") or []
        out["encoding"]["children"] = kids[:1]
    if fusion["strategy"] == "best-of-breed":
        for row in out["encoding"].get("slots") or []:
            (row.get("candidates") or {}).pop("b", None)
    return out


def rename_workflow(wf: dict, prefix: str) -> dict:
    """Identifier rename; fingerprint must be invariant."""
    out = copy.deepcopy(wf)
    out["id"] = prefix + out["id"]
    for i, stage in enumerate(out["stages"]):
        stage["id"] = f"{prefix}{i}-{stage['id']}"
    return out


def mutate_gate(wf: dict, index: int = 1) -> dict:
    out = copy.deepcopy(wf)
    out["stages"][index]["gate"] = out["stages"][index]["gate"] + "|mutant"
    return out
