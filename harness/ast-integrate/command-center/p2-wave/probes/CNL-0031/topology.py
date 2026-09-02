"""Partition-grain topology family: flat-peer, committee, caucus.

Unifying parameter: partition grain k (cell cardinality of a roster
partition). Companion: fan-in capacity c (facts a cell may emit to
plenary). Flat is identity fan-in: g==1 implies the plenary IS the cell.
"""
from __future__ import annotations

from typing import Any

N_DEFAULT = 12
C_DEFAULT = 2
PLANTED_FACT_ID = "F00"
SWEEP_K = (1, 2, 3, 4, 6, 12)


def member_id(i: int) -> str:
    return f"M{i:02d}"


def fact_id(i: int) -> str:
    return f"F{i:02d}"


def family_label(k: int, n: int) -> str:
    """Labels on ranges of k; not distinct topology kinds."""
    if k == n:
        return "flat-peer"
    if k == 1:
        return "singleton-fanin"
    g = n // k
    if g <= 3:
        return "committee"
    return "caucus"


def expected_lost(n: int, k: int, c: int) -> int:
    """Closed form for one unique fact per member, disjoint cells.

    Overflow rule k > c: each cell of size k emits min(k, c) facts.
    Flat identity: g == 1 uses identity fan-in, so lost == 0.
    """
    if k < 1 or n % k != 0:
        raise ValueError(f"k={k} must divide n={n}")
    g = n // k
    if g == 1:
        return 0  # MARKER_FLAT_IDENTITY
    return n - g * min(k, c)  # MARKER_OVERFLOW k > c


def partition_groups(n: int, k: int) -> list[list[str]]:
    if k < 1 or n % k != 0:
        raise ValueError(f"k={k} must divide n={n}")
    groups: list[list[str]] = []
    for start in range(0, n, k):
        groups.append([member_id(i) for i in range(start, start + k)])
    return groups


def member_fact(i: int, n: int) -> dict[str, Any]:
    """Priority equals index: F00 is lowest, so a cell of size k>c drops it."""
    return {
        "id": fact_id(i),
        "priority": i,
        "holder": member_id(i),
        "n": n,
    }


def fan_in(facts: list[dict[str, Any]], c: int, identity: bool) -> list[dict[str, Any]]:
    """Rapporteur capacity c, or identity fan-in when the cell is the plenary."""
    if identity:
        return sorted(facts, key=lambda f: f["id"])
    ranked = sorted(facts, key=lambda f: (-int(f["priority"]), f["id"]))
    return ranked[:c]  # MARKER_FANIN rapporteur capacity c


def simulate(n: int = N_DEFAULT, k: int = N_DEFAULT, c: int = C_DEFAULT) -> dict[str, Any]:
    """Run one topology. Returns transcripts, plenary payloads, and lost ids."""
    groups = partition_groups(n, k)
    g = len(groups)
    identity = g == 1
    transcripts: list[dict[str, Any]] = []
    payloads: list[dict[str, Any]] = []
    for gi, group in enumerate(groups):
        facts = [member_fact(int(mid[1:]), n) for mid in group]
        fact_ids = [f["id"] for f in facts]
        emitted = fan_in(facts, c, identity)
        emit_ids = [f["id"] for f in emitted]
        transcripts.append(
            {
                "group_index": gi,
                "members": list(group),
                "fact_ids": fact_ids,
                "facts": facts,
            }
        )
        payloads.append(
            {
                "group_index": gi,
                "fact_ids": emit_ids,
                "facts": emitted,
            }
        )
    caucus_ids = [fid for t in transcripts for fid in t["fact_ids"]]
    plenary_ids = [fid for p in payloads for fid in p["fact_ids"]]
    caucus_set = set(caucus_ids)
    plenary_set = set(plenary_ids)
    lost_ids = sorted(caucus_set - plenary_set)
    planted_in_caucus = PLANTED_FACT_ID in caucus_set
    planted_in_group0 = PLANTED_FACT_ID in transcripts[0]["fact_ids"]
    planted_in_plenary = PLANTED_FACT_ID in plenary_set
    fires = bool(planted_in_group0 and not planted_in_plenary)
    return {
        "n": n,
        "k": k,
        "c": c,
        "g": g,
        "family": family_label(k, n),
        "identity_fan_in": identity,
        "group_transcripts": transcripts,
        "plenary_payloads": payloads,
        "caucus_count": len(caucus_set),
        "plenary_count": len(plenary_set),
        "lost_ids": lost_ids,
        "lost_count": len(lost_ids),
        "retention": (len(plenary_set) / len(caucus_set)) if caucus_set else 0.0,
        "planted_fact": PLANTED_FACT_ID,
        "planted_in_caucus": planted_in_caucus,
        "planted_in_group0": planted_in_group0,
        "planted_in_plenary": planted_in_plenary,
        "fragmentation_fires": fires,
        "expected_lost": expected_lost(n, k, c),
        "parallelism_g": g,
        "net_score": ((len(plenary_set) / len(caucus_set)) * g) if caucus_set else 0.0,
    }


def sweep(n: int = N_DEFAULT, c: int = C_DEFAULT, ks: tuple[int, ...] = SWEEP_K) -> list[dict[str, Any]]:
    rows = []
    for k in ks:
        if n % k != 0:
            continue
        rows.append(simulate(n=n, k=k, c=c))
    return rows


def crossover_k(n: int = N_DEFAULT, c: int = C_DEFAULT, ks: tuple[int, ...] = SWEEP_K) -> int:
    """Smallest k in the sweep with lost_count > 0. For c=2, n=12 this is 3."""
    for row in sweep(n=n, c=c, ks=ks):
        if row["k"] != n and row["lost_count"] > 0:
            return int(row["k"])
    raise ValueError("no lossy k in sweep")


def first_subdivision_from_flat(n: int = N_DEFAULT, ks: tuple[int, ...] = SWEEP_K) -> int:
    """Largest proper divisor of n in the sweep (first cut away from k=n)."""
    proper = [k for k in ks if k < n and n % k == 0]
    if not proper:
        raise ValueError("no proper partition")
    return max(proper)


def negative_control_verbatim(n: int = N_DEFAULT, c: int = C_DEFAULT) -> dict[str, str]:
    """Both-states control: FIRES on lossy committee, SILENT on flat identity."""
    bad = simulate(n=n, k=first_subdivision_from_flat(n), c=c)
    good = simulate(n=n, k=n, c=c)
    bad_line = (
        f"FIRES planted={bad['planted_fact']} in_caucus={bad['planted_in_group0']} "
        f"in_plenary={bad['planted_in_plenary']} lost_count={bad['lost_count']} "
        f"k={bad['k']} family={bad['family']}"
    )
    good_line = (
        f"SILENT planted={good['planted_fact']} in_caucus={good['planted_in_group0']} "
        f"in_plenary={good['planted_in_plenary']} lost_count={good['lost_count']} "
        f"k={good['k']} family={good['family']}"
    )
    return {
        "bad_state_output": bad_line,
        "good_state_output": good_line,
        "fires_on": f"k={bad['k']} c={c} committee overflow",
        "silent_on": f"k={good['k']} flat identity fan-in",
    }


def lossless_counterexample(n: int = N_DEFAULT, c: int = C_DEFAULT) -> dict[str, Any]:
    """k == c pair-caucus: subgrouping with measured loss 0.

    Counterexample to 'any k < n fragments'.
    """
    k = c
    if n % k != 0:
        raise ValueError(f"k=c={c} must divide n={n}")
    row = simulate(n=n, k=k, c=c)
    return {
        "k": k,
        "c": c,
        "n": n,
        "g": row["g"],
        "family": row["family"],
        "lost_count": row["lost_count"],
        "lost_ids": row["lost_ids"],
        "planted_in_plenary": row["planted_in_plenary"],
        "what_it_refutes": "any k<n subgrouping fragments cross-group information",
    }
