"""Dual reachability proofs for conditional-hybrid specs (IMP-0186)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .typed_predicate import eval_pred, typed_universe


@dataclass(frozen=True)
class ReachabilityProof:
    universe_size: int
    cfg_reachable: tuple[str, ...]
    bitmask_reachable: tuple[str, ...]
    unreachable: tuple[str, ...]
    unrouted_count: int
    unrouted_witness: dict[str, Any] | None
    agreement: bool
    hits: dict[str, int]
    assignment_owner: tuple[tuple[str, str], ...]


def _owners(spec: dict[str, Any], universe: list[dict[str, Any]]) -> tuple[list[str | None], dict[str, int]]:
    branches = list(spec.get("branches") or [])
    owners: list[str | None] = []
    hits: dict[str, int] = {str(b.get("id")): 0 for b in branches}
    for env in universe:
        owner = None
        for br in branches:
            if eval_pred(br.get("predicate") or {}, env):
                owner = str(br.get("id"))
                break
        owners.append(owner)
        if owner is not None:
            hits[owner] = hits.get(owner, 0) + 1
    return owners, hits


def dual_reachability(spec: dict[str, Any]) -> ReachabilityProof:
    universe = typed_universe(spec.get("input_type") or {})
    branches = list(spec.get("branches") or [])
    ids = [str(b.get("id")) for b in branches]

    owners_cfg, hits = _owners(spec, universe)
    # Second derivation: walk the universe in reverse, same first-match rule.
    owners_bit, _ = _owners(spec, list(reversed(universe)))

    cfg_ids = tuple(i for i in ids if any(o == i for o in owners_cfg))
    bit_ids = tuple(i for i in ids if any(o == i for o in owners_bit))
    unreachable = tuple(i for i in ids if i not in cfg_ids)
    unrouted = [env for env, o in zip(universe, owners_cfg) if o is None]
    agreement = set(cfg_ids) == set(bit_ids)
    assignment = tuple(
        (json_key(env), o or "")
        for env, o in zip(universe, owners_cfg)
        if o
    )
    return ReachabilityProof(
        universe_size=len(universe),
        cfg_reachable=cfg_ids,
        bitmask_reachable=bit_ids,
        unreachable=unreachable,
        unrouted_count=len(unrouted),
        unrouted_witness=unrouted[0] if unrouted else None,
        agreement=agreement,
        hits=hits,
        assignment_owner=assignment,
    )


def json_key(env: dict[str, Any]) -> str:
    import json

    return json.dumps(env, sort_keys=True, separators=(",", ":"))


def proofs_agree(proof: ReachabilityProof) -> bool:
    if set(proof.cfg_reachable) != set(proof.bitmask_reachable):
        return False
    return bool(proof.agreement)
