"""Liquid-democracy weights: conserve power; void cyclic edges; keep inbound."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

POLICY = "void-cyclic-edges-keep-inbound"


@dataclass
class Graph:
    authority: dict[str, int]
    delegations: dict[str, str]

    def as_maps(self) -> tuple[dict[str, int], dict[str, str]]:
        return dict(self.authority), dict(self.delegations)


@dataclass
class CycleReport:
    found: bool
    cycles: list[tuple[str, ...]]
    cyclic_seats: set[str]
    voided_edges: set[tuple[str, str]]
    sccs_cyclic: list[tuple[str, ...]]


@dataclass
class ResolveResult:
    conserved: bool
    total_power_before: int
    total_power_after: int
    effective: dict[str, int]
    cycle_report: CycleReport
    remaining_delegations: dict[str, str]
    sink_of: dict[str, str]
    policy: str = POLICY
    silent_disenfranchisement: bool = False


def total_power(authority: Mapping[str, int]) -> int:
    return int(sum(int(v) for v in authority.values()))


def _normalize_cycle(path: list[str]) -> tuple[str, ...]:
    body = path[:-1] if path and path[0] == path[-1] else list(path)
    if not body:
        return tuple()
    k = body.index(min(body))
    return tuple(body[k:] + body[:k])


def detect_cycles(graph: Graph) -> CycleReport:
    _, delegations = graph.as_maps()
    nodes = set(graph.authority) | set(delegations) | set(delegations.values())
    succ = {n: [] for n in nodes}
    for a, b in delegations.items():
        succ.setdefault(a, []).append(b)
        succ.setdefault(b, [])
    cycles: list[tuple[str, ...]] = []
    for start in sorted(nodes):
        stack = [start]
        blocked = {start}

        def circuit(path: list[str]) -> None:
            node = path[-1]
            for nxt in succ.get(node, []):
                if nxt < start:
                    continue
                if nxt == start:
                    cycles.append(_normalize_cycle(path + [start]))
                elif nxt not in path and nxt not in blocked:
                    blocked.add(nxt)
                    circuit(path + [nxt])
                    blocked.discard(nxt)

        circuit(stack)
    uniq = sorted(set(c for c in cycles if c))
    cyclic_seats: set[str] = set()
    voided: set[tuple[str, str]] = set()
    for cyc in uniq:
        seats = list(cyc)
        cyclic_seats.update(seats)
        for i, a in enumerate(seats):
            b = seats[(i + 1) % len(seats)]
            if delegations.get(a) == b:
                voided.add((a, b))
        if len(seats) == 1 and delegations.get(seats[0]) == seats[0]:
            voided.add((seats[0], seats[0]))
    sccs = [tuple(sorted(c)) for c in uniq]
    return CycleReport(
        found=bool(uniq),
        cycles=uniq,
        cyclic_seats=cyclic_seats,
        voided_edges=voided,
        sccs_cyclic=sccs,
    )


def reverse_sink_map(
    seats: Iterable[str], remaining: Mapping[str, str]
) -> dict[str, str]:
    seats = list(seats)
    sink = {s: s for s in seats}
    for _ in range(len(seats) + 2):
        changed = False
        for s in seats:
            nxt = remaining.get(s)
            if nxt is not None and nxt in sink:
                if sink[s] != sink[nxt]:
                    sink[s] = sink[nxt]
                    changed = True
        if not changed:
            break
    return sink


def resolve_weights(graph: Graph) -> ResolveResult:
    authority, delegations = graph.as_maps()
    report = detect_cycles(graph)
    remaining = {
        a: b
        for a, b in delegations.items()
        if (a, b) not in report.voided_edges
    }
    seats = list(authority.keys())
    sink = reverse_sink_map(seats, remaining)
    effective = {s: 0 for s in seats}
    for origin, weight in authority.items():
        effective[sink[origin]] += int(weight)
    before = total_power(authority)
    after = total_power(effective)
    return ResolveResult(
        conserved=before == after,
        total_power_before=before,
        total_power_after=after,
        effective=effective,
        cycle_report=report,
        remaining_delegations=remaining,
        sink_of=sink,
        policy=POLICY,
        silent_disenfranchisement=False,
    )


def resolve_drop_cyclic_bloc(graph: Graph) -> ResolveResult:
    """Mutant: drop every seat in a cyclic bloc (and inbound that lands there)."""
    good = resolve_weights(graph)
    report = good.cycle_report
    if not report.found:
        return good
    cyclic = set(report.cyclic_seats)
    effective = dict(good.effective)
    for s in list(effective):
        if s in cyclic or good.sink_of.get(s) in cyclic:
            effective[s] = 0
    after = total_power(effective)
    return ResolveResult(
        conserved=good.total_power_before == after,
        total_power_before=good.total_power_before,
        total_power_after=after,
        effective=effective,
        cycle_report=report,
        remaining_delegations=good.remaining_delegations,
        sink_of=good.sink_of,
        policy="drop-cyclic-bloc",
        silent_disenfranchisement=True,
    )


def constructed_fixtures() -> dict[str, Graph]:
    return {
        "three_cycle": Graph(
            authority={"A": 2, "B": 2, "C": 2},
            delegations={"A": "B", "B": "C", "C": "A"},
        ),
        "two_cycle": Graph(
            authority={"A": 3, "B": 3},
            delegations={"A": "B", "B": "A"},
        ),
        "self_loop": Graph(
            authority={"A": 5},
            delegations={"A": "A"},
        ),
        "inbound_to_cycle": Graph(
            authority={"A": 1, "B": 1, "C": 1, "D": 4},
            delegations={"A": "B", "B": "C", "C": "A", "D": "A"},
        ),
        "dag_chain": Graph(
            authority={"A": 1, "B": 1, "C": 1},
            delegations={"A": "B", "B": "C"},
        ),
        "two_disjoint_cycles": Graph(
            authority={"A": 1, "B": 1, "C": 1, "D": 1},
            delegations={"A": "B", "B": "A", "C": "D", "D": "C"},
        ),
        "chain_into_cycle": Graph(
            authority={"A": 1, "B": 1, "C": 1},
            delegations={"C": "A", "A": "B", "B": "A"},
        ),
        "authority_roles": Graph(
            authority={"chair": 3, "member": 1},
            delegations={},
        ),
    }


def expected_effective_fixtures() -> dict[str, dict[str, int]]:
    return {name: resolve_weights(g).effective for name, g in constructed_fixtures().items()}


def random_delegation_graph(rng: Any, n: int, p: float) -> Graph:
    seats = [chr(ord("A") + i) if n <= 26 else f"S{i}" for i in range(n)]
    authority = {s: int(rng.randint(1, 5)) for s in seats}
    delegations: dict[str, str] = {}
    for s in seats:
        if rng.random() < p:
            others = [t for t in seats]
            delegations[s] = others[int(rng.randrange(len(others)))]
    return Graph(authority=authority, delegations=delegations)


def property_conservation(*, n_trials: int, seed: int) -> dict[str, Any]:
    import random

    rng = random.Random(seed)
    rows = []
    n_fail = 0
    n_cyclic = 0
    for i in range(n_trials):
        g = random_delegation_graph(rng, rng.randint(3, 8), 0.55)
        res = resolve_weights(g)
        n_cycles = len(res.cycle_report.cycles)
        if n_cycles:
            n_cyclic += 1
        conserved = res.conserved
        if not conserved:
            n_fail += 1
        rows.append(
            {
                "i": i,
                "conserved": conserved,
                "n_cycles": n_cycles,
                "before": res.total_power_before,
                "after": res.total_power_after,
            }
        )
    return {
        "n_trials": n_trials,
        "n_fail": n_fail,
        "n_cyclic_graphs": n_cyclic,
        "pass": n_fail == 0,
        "seed": seed,
        "rows": rows,
    }
