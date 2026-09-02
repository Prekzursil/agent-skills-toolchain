"""Fusion operators over Workflow IR."""
from __future__ import annotations

from dataclasses import replace

from .workflow_ir import Stage, Workflow


class FusionRefused(Exception):
    pass


def _strictest(licences: tuple[str, ...]) -> tuple[str, ...]:
    rank = {
        "AGPL-3.0-only": 6,
        "GPL-3.0-only": 5,
        "GPL-2.0-only": 4,
        "LGPL-3.0-only": 3,
        "MPL-2.0": 2,
        "Apache-2.0": 1,
        "BSD-3-Clause": 1,
        "MIT": 0,
    }
    ordered = sorted(set(licences), key=lambda x: (-rank.get(x, 0), x))
    return tuple(ordered[:1]) if ordered else ()


def _merge(host: Workflow, donor: Workflow, op: str) -> Workflow:
    seen = {s.id: s for s in host.stages}
    stages = list(host.stages)
    for st in donor.stages:
        if st.id not in seen:
            stages.append(st)
            seen[st.id] = st
    return Workflow(
        id=f"{op}:{host.id}+{donor.id}",
        stages=stages,
        edges=list(host.edges) + list(donor.edges),
        licences=_strictest(tuple(host.licences) + tuple(donor.licences)),
        credits=tuple(dict.fromkeys(host.credits + donor.credits)),
    )


def splice(host: Workflow, donor: Workflow) -> Workflow:
    host_contracts = {(s.in_contract, s.out_contract) for s in host.stages}
    for st in donor.stages:
        if st.kind in {s.kind for s in host.stages}:
            continue
        if (st.in_contract, st.out_contract) not in host_contracts and st.in_contract != "bundle":
            raise FusionRefused("splice-contract-mismatch")
    return _merge(host, donor, "splice")


def common_core(family: list[Workflow]) -> Workflow:
    if not family:
        raise FusionRefused("empty-family")
    shared_ids = set(family[0].stages[i].id for i in range(len(family[0].stages)))
    for wf in family[1:]:
        shared_ids &= {s.id for s in wf.stages}
    stages = [s for s in family[0].stages if s.id in shared_ids]
    licences: tuple[str, ...] = ()
    credits: tuple[str, ...] = ()
    for wf in family:
        licences = _strictest(licences + wf.licences)
        credits = tuple(dict.fromkeys(credits + wf.credits))
    return Workflow(id="common-core", stages=stages, licences=licences, credits=credits)


def union(left: Workflow, right: Workflow) -> Workflow:
    return _merge(left, right, "union")


def best_of_breed(left: Workflow, right: Workflow, scores: dict) -> Workflow:
    picked: list[Stage] = []
    index = {s.id: s for s in list(left.stages) + list(right.stages)}
    kinds = []
    for wf in (left, right):
        for s in wf.stages:
            if s.kind not in kinds:
                kinds.append(s.kind)
    for kind in kinds:
        candidates = []
        for wf in (left, right):
            for s in wf.stages:
                if s.kind == kind:
                    sc = float((scores.get(wf.id) or {}).get(s.kind) or 0)
                    candidates.append((sc, s))
        candidates.sort(key=lambda x: -x[0])
        if candidates:
            picked.append(candidates[0][1])
    return Workflow(
        id=f"bob:{left.id}+{right.id}",
        stages=picked,
        licences=_strictest(left.licences + right.licences),
        credits=tuple(dict.fromkeys(left.credits + right.credits)),
    )


def hybrid(left: Workflow, right: Workflow) -> Workflow:
    return _merge(left, right, "hybrid")


def ensemble(left: Workflow, right: Workflow) -> Workflow:
    fused = _merge(left, right, "ensemble")
    return replace(fused, stages=fused.stages + [Stage(id="vote", kind="vote")])


def progressive(cheap: Workflow, expensive: Workflow) -> Workflow:
    return Workflow(
        id=f"progressive:{cheap.id}+{expensive.id}",
        stages=list(cheap.stages) + [Stage(id="escalate", kind="escalate")] + list(expensive.stages[1:]),
        licences=_strictest(cheap.licences + expensive.licences),
        credits=tuple(dict.fromkeys(cheap.credits + expensive.credits)),
    )
