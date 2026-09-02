#!/usr/bin/env python3
"""Liquid delegation with fail-closed cycle detection and a concentration cap.

Tabulation is a separate function. process() must not call it when a cycle
exists or when one terminal seat would hold more than cap_share of total
base weight. That is the load-bearing claim of CNL-0067.
"""
from __future__ import annotations

from typing import Any, Callable

YES = "YES"
NO = "NO"
ABSTAIN = "ABSTAIN"

STATUS_OK = "TABULATED"
STATUS_CYCLE = "DELEGATION_CYCLE"
STATUS_CAP = "CONCENTRATION_CAP"
STATUS_UNKNOWN = "UNKNOWN_DELEGATE"
STATUS_DUP = "DUPLICATE_SEAT"
STATUS_WEIGHT = "INVALID_WEIGHT"

# Default: no resolved seat may silently hold a simple-majority share.
DEFAULT_CAP_SHARE = 0.5


def load_profile(path) -> dict[str, Any]:
    import json
    from pathlib import Path

    return json.loads(Path(path).read_text(encoding="utf-8"))


def seats_by_id(profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in profile["seats"]:
        sid = str(row["id"])
        if sid in out:
            raise ValueError(f"duplicate seat {sid!r}")
        out[sid] = row
    return out


def base_weights(profile: dict[str, Any]) -> dict[str, float]:
    w: dict[str, float] = {}
    for sid, row in seats_by_id(profile).items():
        wt = float(row.get("base_weight", 1))
        if wt < 0:
            raise ValueError(f"negative base_weight for {sid!r}")
        w[sid] = wt
    return w


def edges(profile: dict[str, Any]) -> dict[str, str]:
    """delegator -> delegate, omitting seats that vote themselves."""
    out: dict[str, str] = {}
    known = set(seats_by_id(profile))
    for sid, row in seats_by_id(profile).items():
        tgt = row.get("delegates_to")
        if tgt is None or tgt == "":
            continue
        tgt = str(tgt)
        if tgt not in known:
            out[sid] = tgt  # dangling; caller classifies UNKNOWN_DELEGATE
        else:
            out[sid] = tgt
    return out


def dangling_delegates(profile: dict[str, Any]) -> list[tuple[str, str]]:
    known = set(seats_by_id(profile))
    bad: list[tuple[str, str]] = []
    for src, tgt in edges(profile).items():
        if tgt not in known:
            bad.append((src, tgt))
    return bad


def find_cycles(profile: dict[str, Any]) -> list[list[str]]:
    """DFS back-edge cycles. Self-loops are 1-cycles. Order is detection order."""
    adj = {sid: [] for sid in seats_by_id(profile)}
    for src, tgt in edges(profile).items():
        if tgt in adj:
            adj[src].append(tgt)
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in adj}
    stack: list[str] = []
    cycles: list[list[str]] = []

    def emit_cycle(back_to: str) -> None:
        if back_to not in stack:
            return
        i = stack.index(back_to)
        cyc = stack[i:] + [back_to]
        # Canonicalize rotation so independent recounts can set-compare.
        body = cyc[:-1]
        k = body.index(min(body))
        canon = body[k:] + body[:k] + [body[k]]
        if canon not in cycles:
            cycles.append(canon)

    def dfs(n: str) -> None:
        color[n] = GRAY
        stack.append(n)
        for m in adj[n]:
            if color[m] == WHITE:
                dfs(m)
            elif color[m] == GRAY:
                emit_cycle(m)
        stack.pop()
        color[n] = BLACK

    for n in sorted(adj):
        if color[n] == WHITE:
            dfs(n)
    return cycles


def resolve_weights(profile: dict[str, Any]) -> dict[str, float]:
    """Push every base weight along the unique outgoing chain to a terminal.

    MUST be called only on an acyclic, dangling-free graph. Walks are bounded
    by |seats| so a missed cycle cannot loop forever; it raises instead.
    """
    known = seats_by_id(profile)
    ed = edges(profile)
    base = base_weights(profile)
    effective = {sid: 0.0 for sid in known}
    bound = len(known) + 1
    for sid, wt in base.items():
        cur = sid
        seen: set[str] = set()
        steps = 0
        while cur in ed:
            if cur in seen or steps >= bound:
                raise RuntimeError(f"resolve_weights saw a cycle at {cur!r}")
            seen.add(cur)
            cur = ed[cur]
            steps += 1
            if cur not in known:
                raise RuntimeError(f"resolve_weights dangling {cur!r}")
        effective[cur] += wt
    return effective


def concentration_offenders(
    effective: dict[str, float], cap_share: float
) -> list[dict[str, Any]]:
    total = sum(effective.values())
    if total <= 0:
        return []
    cap = cap_share * total
    out: list[dict[str, Any]] = []
    for sid, wt in sorted(effective.items()):
        if wt > cap:
            out.append(
                {
                    "seat": sid,
                    "effective_weight": wt,
                    "share": wt / total,
                    "cap_share": cap_share,
                    "cap_weight": cap,
                    "total": total,
                }
            )
    return out


def tabulate(
    profile: dict[str, Any], effective: dict[str, float]
) -> dict[str, Any]:
    """Sum YES/NO using resolved weights. Delegators do not cast a ballot."""
    ballots = dict(profile.get("ballots") or {})
    yes = no = abstain = 0.0
    unused = 0.0
    for sid, wt in effective.items():
        if wt == 0:
            continue
        choice = ballots.get(sid)
        if choice == YES:
            yes += wt
        elif choice == NO:
            no += wt
        elif choice == ABSTAIN:
            abstain += wt
        else:
            unused += wt
    if yes > no:
        winner = YES
    elif no > yes:
        winner = NO
    else:
        winner = "TIE"
    return {
        "yes": yes,
        "no": no,
        "abstain": abstain,
        "unused": unused,
        "winner": winner,
    }


def process(
    profile: dict[str, Any],
    *,
    tabulate_fn: Callable[..., dict[str, Any]] | None = None,
    skip_cycle_check: bool = False,
    skip_cap_check: bool = False,
) -> dict[str, Any]:
    """Fail-closed: cycle and concentration reject BEFORE tabulation.

    tabulate_fn is injectable so probes can prove it was not called.
    skip_* flags exist only as negative-control mutants: they must make a
    planted-bad fixture produce a winner the honest path refuses.
    """
    tally = tabulate_fn if tabulate_fn is not None else tabulate
    cap_share = float(profile.get("cap_share", DEFAULT_CAP_SHARE))
    if not 0 < cap_share <= 1:
        raise ValueError("cap_share must be in (0, 1]")

    ids = [str(r["id"]) for r in profile["seats"]]
    if len(ids) != len(set(ids)):
        return {
            "status": STATUS_DUP,
            "tabulated": False,
            "winner": None,
            "cycles": [],
            "offenders": [],
            "effective": {},
            "tally": None,
        }
    for sid, wt in base_weights(profile).items():
        if wt < 0:
            return {
                "status": STATUS_WEIGHT,
                "tabulated": False,
                "winner": None,
                "cycles": [],
                "offenders": [],
                "effective": {},
                "tally": None,
                "seat": sid,
            }

    dangling = dangling_delegates(profile)
    if dangling:
        return {
            "status": STATUS_UNKNOWN,
            "tabulated": False,
            "winner": None,
            "cycles": [],
            "offenders": [],
            "effective": {},
            "tally": None,
            "dangling": [{"from": a, "to": b} for a, b in dangling],
        }

    cycles = [] if skip_cycle_check else find_cycles(profile)
    # CYCLE-GATE: tabulate is not invoked when cycles is non-empty.
    if cycles:
        return {
            "status": STATUS_CYCLE,
            "tabulated": False,
            "winner": None,
            "cycles": cycles,
            "offenders": [],
            "effective": {},
            "tally": None,
        }

    effective = resolve_weights(profile)
    offenders = [] if skip_cap_check else concentration_offenders(
        effective, cap_share
    )
    # CAP-GATE: tabulate is not invoked when a seat exceeds cap_share.
    if offenders:
        return {
            "status": STATUS_CAP,
            "tabulated": False,
            "winner": None,
            "cycles": [],
            "offenders": offenders,
            "effective": effective,
            "tally": None,
        }

    tally_row = tally(profile, effective)
    return {
        "status": STATUS_OK,
        "tabulated": True,
        "winner": tally_row["winner"],
        "cycles": [],
        "offenders": [],
        "effective": effective,
        "tally": tally_row,
        "conservation_ok": abs(
            sum(effective.values()) - sum(base_weights(profile).values())
        )
        < 1e-9,
    }


def compact(row: dict[str, Any]) -> str:
    off = ",".join(o["seat"] for o in (row.get("offenders") or []))
    cyc = "|".join("->".join(c) for c in (row.get("cycles") or []))
    return (
        f"status={row['status']} tabulated={row['tabulated']} "
        f"winner={row['winner']} cycles={cyc or '-'} offenders={off or '-'}"
    )
