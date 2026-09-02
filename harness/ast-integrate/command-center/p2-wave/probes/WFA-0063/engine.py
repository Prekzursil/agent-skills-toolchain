#!/usr/bin/env python3
"""Fusion operators, inverse decompose, certification, smoke runtime.

A fused WorkflowIR is decomposable only when lineage carries reconstructable
source components and re-running the recorded operator reproduces the fusion
body. Recovering ids without runnable sources is not certification.
"""
from __future__ import annotations

import copy
import json
from typing import Any

OPERATORS: tuple[str, ...] = (
    "stage-splice",
    "common-core",
    "union",
    "best-of-breed",
    "conditional-hybrid",
    "ensemble",
    "progressive",
)

OPS = {
    "inc": lambda x, p: int(x) + 1,
    "double": lambda x, p: int(x) * 2,
    "square": lambda x, p: int(x) * int(x),
    "add_k": lambda x, p: int(x) + int(p.get("k", 0)),
    "ident": lambda x, p: x,
    "neg": lambda x, p: -int(x),
}


class FusionError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code if not detail else f"{code}:{detail}")
        self.code = code
        self.detail = detail


class DecomposeError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code if not detail else f"{code}:{detail}")
        self.code = code
        self.detail = detail


def dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def deep(obj: Any) -> Any:
    return copy.deepcopy(obj)


def canonical(uid: str, mmap: dict[str, str] | None) -> str:
    cur = uid
    seen: set[str] = set()
    table = mmap or {}
    while cur in table and cur not in seen:
        seen.add(cur)
        cur = table[cur]
    return cur


def component_key(
    sid: str, components: dict[str, Any], mmap: dict[str, str] | None
) -> str | None:
    if sid in components:
        return sid
    target = canonical(sid, mmap)
    if target in components:
        return target
    for key in components:
        if canonical(key, mmap) == target:
            return key
    return None


def stage_fp(stage: dict[str, Any]) -> tuple[Any, ...]:
    return (
        stage.get("kind"),
        stage.get("mechanism"),
        stage.get("op"),
        dumps(stage.get("params") or {}),
        stage.get("in_type"),
        stage.get("out_type"),
        stage.get("slot"),
    )


def workflow_fp(wf: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(stage_fp(s) for s in wf.get("stages") or [])


def tag_stage(stage: dict[str, Any], source_id: str) -> dict[str, Any]:
    out = deep(stage)
    out["origin"] = {"source_id": source_id, "stage_id": stage["id"]}
    return out


def strip_to_source(wf: dict[str, Any]) -> dict[str, Any]:
    out = deep(wf)
    out["kind"] = "source"
    out.pop("lineage", None)
    return out


def run_pipeline(stages: list[dict[str, Any]], value: Any) -> Any:
    cur = value
    for stage in stages:
        op = stage.get("op")
        if op not in OPS:
            raise FusionError("unknown-op", str(op))
        cur = OPS[op](cur, stage.get("params") or {})
    return cur


def run_smoke(wf: dict[str, Any]) -> dict[str, Any]:
    smoke = wf.get("smoke") or {}
    if "input" not in smoke or "expected" not in smoke:
        return {
            "ok": False,
            "reason": "smoke-missing",
            "observed": None,
            "expected": None,
        }
    observed = run_pipeline(wf.get("stages") or [], smoke["input"])
    expected = smoke["expected"]
    return {
        "ok": observed == expected,
        "observed": observed,
        "expected": expected,
        "reason": None if observed == expected else "smoke-mismatch",
    }


def _by_id(sources: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out = {s["id"]: s for s in sources}
    if len(out) != len(sources):
        raise FusionError("duplicate-source-id")
    return out


def _fuse_stage_splice(
    sources: list[dict[str, Any]], params: dict[str, Any]
) -> list[dict[str, Any]]:
    if len(sources) != 2:
        raise FusionError("splice-arity")
    host, donor = sources[0], sources[1]
    idx = int(params["index"])
    donor_stage_id = params["donor_stage_id"]
    found = next((s for s in donor["stages"] if s["id"] == donor_stage_id), None)
    if found is None:
        raise FusionError("donor-stage-missing", donor_stage_id)
    if idx < 0 or idx > len(host["stages"]):
        raise FusionError("splice-index")
    inserted = tag_stage(found, donor["id"])
    host_stages = [tag_stage(s, host["id"]) for s in host["stages"]]
    return host_stages[:idx] + [inserted] + host_stages[idx:]


def _fuse_common_core(
    sources: list[dict[str, Any]], params: dict[str, Any]
) -> list[dict[str, Any]]:
    if len(sources) < 2:
        raise FusionError("core-arity")
    core_len = int(params["core_len"])
    if core_len < 1:
        raise FusionError("empty-core")
    fps = [tuple(stage_fp(s) for s in src["stages"][:core_len]) for src in sources]
    if any(len(src["stages"]) < core_len for src in sources):
        raise FusionError("core-truncated")
    if len(set(fps)) != 1:
        raise FusionError("core-mismatch")
    head = sources[0]
    return [tag_stage(s, head["id"]) for s in head["stages"][:core_len]]


def _fuse_union(
    sources: list[dict[str, Any]], params: dict[str, Any]
) -> list[dict[str, Any]]:
    del params
    if len(sources) < 2:
        raise FusionError("union-arity")
    out: list[dict[str, Any]] = []
    for src in sources:
        for stage in src["stages"]:
            tagged = tag_stage(stage, src["id"])
            tagged["id"] = f"{src['id']}::{stage['id']}"
            out.append(tagged)
    return out


def _fuse_best_of_breed(
    sources: list[dict[str, Any]], params: dict[str, Any]
) -> list[dict[str, Any]]:
    table = _by_id(sources)
    scores: dict[str, dict[str, float]] = params["scores"]
    picked: list[dict[str, Any]] = []
    for slot, ranked in scores.items():
        if not ranked:
            raise FusionError("empty-slot", slot)
        best = max(ranked.values())
        winners = sorted(sid for sid, val in ranked.items() if val == best)
        winner = winners[0]
        if winner not in table:
            raise FusionError("bob-source-missing", winner)
        match = next(
            (s for s in table[winner]["stages"] if s.get("slot") == slot), None
        )
        if match is None:
            raise FusionError("bob-slot-missing", f"{winner}:{slot}")
        tagged = tag_stage(match, winner)
        tagged["id"] = f"bob::{slot}::{winner}"
        picked.append(tagged)
    return picked


def _concat_all(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for src in sources:
        for stage in src["stages"]:
            tagged = tag_stage(stage, src["id"])
            tagged["id"] = f"{src['id']}::{stage['id']}"
            out.append(tagged)
    return out


def _fuse_conditional_hybrid(
    sources: list[dict[str, Any]], params: dict[str, Any]
) -> list[dict[str, Any]]:
    if "predicate" not in params or "default" not in params:
        raise FusionError("hybrid-params")
    return _concat_all(sources)


def _fuse_ensemble(
    sources: list[dict[str, Any]], params: dict[str, Any]
) -> list[dict[str, Any]]:
    if "aggregator" not in params:
        raise FusionError("ensemble-params")
    return _concat_all(sources)


def _fuse_progressive(
    sources: list[dict[str, Any]], params: dict[str, Any]
) -> list[dict[str, Any]]:
    if "adequacy" not in params:
        raise FusionError("progressive-params")
    return _concat_all(sources)


_BUILDERS = {
    "stage-splice": _fuse_stage_splice,
    "common-core": _fuse_common_core,
    "union": _fuse_union,
    "best-of-breed": _fuse_best_of_breed,
    "conditional-hybrid": _fuse_conditional_hybrid,
    "ensemble": _fuse_ensemble,
    "progressive": _fuse_progressive,
}


def fuse(
    operator: str,
    sources: list[dict[str, Any]],
    params: dict[str, Any] | None = None,
    fusion_id: str | None = None,
) -> dict[str, Any]:
    if operator not in _BUILDERS:
        raise FusionError("unknown-operator", operator)
    if len(sources) < 2:
        raise FusionError("need-two-sources")
    for src in sources:
        if not src.get("id") or not src.get("stages"):
            raise FusionError("empty-source")
        if not (src.get("anchor") or ""):
            raise FusionError("anchor-missing", src.get("id"))
        if src.get("anchor") == "":
            raise FusionError("anchor-empty", src.get("id"))
    params = deep(params or {})
    stages = _BUILDERS[operator](sources, params)
    source_ids = [s["id"] for s in sources]
    fid = fusion_id or f"fusion.{operator}.{'.'.join(source_ids)}"
    licenses = sorted({s.get("license") or "UNKNOWN" for s in sources})
    credits = [s.get("credit") or s["id"] for s in sources]
    mechanisms: list[str] = []
    for src in sources:
        for mid in src.get("mechanisms") or []:
            if mid not in mechanisms:
                mechanisms.append(mid)
    return {
        "id": fid,
        "kind": "fusion",
        "stages": stages,
        "mechanisms": mechanisms,
        "roles": ["fusion-runtime"],
        "license": licenses[-1] if licenses else "UNKNOWN",
        "license_obligations": licenses,
        "credit": ";".join(credits),
        "anchor": f"fusion:{fid}",
        "smoke": None,
        "lineage": {
            "operator": operator,
            "source_ids": list(source_ids),
            "components": {s["id"]: strip_to_source(s) for s in sources},
            "params": params,
            "id_migration_map": {},
        },
    }


def apply_rename(fusion: dict[str, Any], old: str, new: str) -> dict[str, Any]:
    """Rewrite a source id through the migration map (old -> new)."""
    out = deep(fusion)
    lin = out["lineage"]
    mmap = dict(lin.get("id_migration_map") or {})
    mmap[old] = new
    lin["id_migration_map"] = mmap
    comps = lin["components"]
    if old in comps:
        wf = comps.pop(old)
        wf["id"] = new
        comps[new] = wf
    lin["source_ids"] = [new if sid == old else sid for sid in lin["source_ids"]]
    return out


def recover_sources(fusion: dict[str, Any]) -> list[dict[str, Any]]:
    if fusion.get("kind") != "fusion":
        raise DecomposeError("not-a-fusion")
    lin = fusion.get("lineage")
    if not isinstance(lin, dict):
        raise DecomposeError("sources-not-reconstructable", "lineage-missing")
    source_ids = lin.get("source_ids")
    components = lin.get("components")
    if not source_ids or not isinstance(components, dict) or not components:
        raise DecomposeError("sources-not-reconstructable", "components-missing")
    mmap = lin.get("id_migration_map") or {}
    recovered: list[dict[str, Any]] = []
    for sid in source_ids:
        key = component_key(sid, components, mmap)
        if key is None:
            raise DecomposeError("sources-not-reconstructable", sid)
        wf = strip_to_source(components[key])
        wf["id"] = canonical(sid, mmap)
        if not wf.get("stages"):
            raise DecomposeError("sources-not-reconstructable", f"empty:{sid}")
        recovered.append(wf)
    return recovered


def decompose(fusion: dict[str, Any]) -> list[dict[str, Any]]:
    """Return runnable source workflows; verify they re-fuse to this body."""
    recovered = recover_sources(fusion)
    lin = fusion["lineage"]
    mmap = lin.get("id_migration_map") or {}
    recovered_ids = {canonical(s["id"], mmap) for s in recovered}
    lineage_ids = {canonical(i, mmap) for i in lin["source_ids"]}
    if recovered_ids != lineage_ids:
        raise DecomposeError("id-set-mismatch", dumps([sorted(recovered_ids), sorted(lineage_ids)]))
    refusion = fuse(lin["operator"], recovered, lin.get("params") or {})
    if workflow_fp(refusion) != workflow_fp(fusion):
        raise DecomposeError("refusion-mismatch", lin["operator"])
    return recovered


def certify(fusion: dict[str, Any]) -> dict[str, Any]:
    """Reject at certification when sources cannot be reconstructed and rehearsed.

    A note that the fusion is undecomposable is not a shipping state.
    """
    note = fusion.get("notes") or fusion.get("certification_note")
    try:
        recovered = decompose(fusion)
    except DecomposeError as exc:
        return {
            "verdict": "REJECTED",
            "reason": exc.code,
            "detail": exc.detail,
            "note_ignored": bool(note),
            "recovered_ids": [],
            "lineage_ids": list(((fusion.get("lineage") or {}).get("source_ids")) or []),
            "rehearsal": {},
        }
    rehearsal: dict[str, Any] = {}
    failed = False
    for src in recovered:
        result = run_smoke(src)
        rehearsal[src["id"]] = result
        if not result["ok"]:
            failed = True
    if failed:
        return {
            "verdict": "REJECTED",
            "reason": "rehearsal-failed",
            "detail": "",
            "note_ignored": bool(note),
            "recovered_ids": [s["id"] for s in recovered],
            "lineage_ids": list(fusion["lineage"]["source_ids"]),
            "rehearsal": rehearsal,
        }
    return {
        "verdict": "CERTIFIED",
        "reason": None,
        "detail": "",
        "note_ignored": bool(note),
        "recovered_ids": [s["id"] for s in recovered],
        "lineage_ids": list(fusion["lineage"]["source_ids"]),
        "rehearsal": rehearsal,
    }


def plant_lossy(fusion: dict[str, Any], mode: str = "strip-components") -> dict[str, Any]:
    """Deliberately undecomposable fusion used as the negative certification control."""
    out = deep(fusion)
    out["notes"] = "sources cannot be reconstructed; ship with a note"
    out["certification_note"] = "undecomposable-but-useful"
    lin = out.setdefault("lineage", {})
    if mode == "strip-components":
        lin["components"] = {}
    elif mode == "drop-lineage":
        out["lineage"] = None
    elif mode == "drop-one-component":
        comps = dict(lin.get("components") or {})
        if comps:
            comps.pop(next(iter(comps)))
        lin["components"] = comps
    else:
        raise FusionError("unknown-lossy-mode", mode)
    return out
