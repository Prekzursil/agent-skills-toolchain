"""Echo-chamber detector: independence loss, not vote agreement.

FIRE when first-pass PRIVATE source overlap AND first-pass warrant overlap
both exceed threshold (shared retrieval / mutual anchoring), OR when
post-exposure new-warrant residue collapses while final conclusions agree
(sequential peer copy).

SILENT when conclusions agree via disjoint private sources and disjoint
warrants (genuine convergence), including easy questions with distinct
derivations and councils that only share the public question packet.

INSUFFICIENT (fired=False, absence_claimed=False) when fewer than two
first-pass briefs exist: a missing first pass is not a clean council.

NOT the signal: generated_independently bits, unanimous votes, lexical
paraphrase distance, declared role diversity.
"""
from __future__ import annotations

import json
import sys
from typing import Any

T_SRC = 0.50
T_WARRANT = 0.50
T_RESIDUE = 0.25
T_AGREE = 0.80


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def mean_pairwise_jaccard(sets: list[set[str]]) -> float:
    if len(sets) < 2:
        return 0.0
    vals: list[float] = []
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            vals.append(jaccard(sets[i], sets[j]))
    return sum(vals) / len(vals)


def pairwise_agreement(values: list[str]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    same = 0
    tot = 0
    for i in range(n):
        for j in range(i + 1, n):
            tot += 1
            if values[i] == values[j]:
                same += 1
    return same / tot


def first_passes(run: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    out: list[tuple[str, dict[str, Any]]] = []
    for p in run.get("participants") or []:
        fp = p.get("first_pass")
        if isinstance(fp, dict):
            out.append((str(p.get("id")), fp))
    return out


def private_sources(fp: dict[str, Any], public: set[str]) -> set[str]:
    return {str(s) for s in (fp.get("sources") or []) if str(s)} - public


def warrants_of(fp: dict[str, Any]) -> set[str]:
    return {str(w) for w in (fp.get("warrants") or []) if str(w)}


def final_conclusion(p: dict[str, Any]) -> str:
    turns = list(p.get("later_turns") or [])
    if turns:
        return str(turns[-1].get("conclusion") or "")
    fp = p.get("first_pass") or {}
    return str(fp.get("conclusion") or "")


def later_events(run: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for p in run.get("participants") or []:
        pid = str(p.get("id"))
        for t in p.get("later_turns") or []:
            events.append(
                {
                    "participant": pid,
                    "round": int(t.get("round") or 0),
                    "warrants": [str(w) for w in (t.get("warrants") or []) if str(w)],
                    "conclusion": str(t.get("conclusion") or ""),
                }
            )
    events.sort(key=lambda e: (e["round"], e["participant"]))
    return events


def residue_report(run: dict[str, Any]) -> dict[str, Any]:
    fps = first_passes(run)
    first_w = {pid: warrants_of(fp) for pid, fp in fps}
    events = later_events(run)
    if not events:
        return {
            "applicable": False,
            "mean_new_warrant_rate": None,
            "per_participant": {},
            "reason": "no post-exposure turns",
        }
    seen: set[str] = set()
    for wset in first_w.values():
        seen |= wset
    new_by: dict[str, set[str]] = {pid: set() for pid, _ in fps}
    for ev in events:
        incoming = set(ev["warrants"])
        fresh = incoming - seen
        new_by.setdefault(ev["participant"], set()).update(fresh)
        seen |= incoming
    rates: list[float] = []
    per: dict[str, Any] = {}
    participants_with_later = {e["participant"] for e in events}
    for pid in participants_with_later:
        n_first = max(1, len(first_w.get(pid) or []))
        n_new = len(new_by.get(pid) or set())
        rate = n_new / n_first
        rates.append(rate)
        per[pid] = {
            "new_warrants": sorted(new_by.get(pid) or set()),
            "first_pass_warrant_count": len(first_w.get(pid) or []),
            "new_warrant_rate": rate,
        }
    mean_rate = sum(rates) / len(rates) if rates else 0.0
    return {
        "applicable": True,
        "mean_new_warrant_rate": mean_rate,
        "per_participant": per,
    }


def snapshot(run: dict[str, Any]) -> dict[str, Any]:
    public = {str(x) for x in (run.get("public_premises") or []) if str(x)}
    fps = first_passes(run)
    priv = [private_sources(fp, public) for _, fp in fps]
    wsets = [warrants_of(fp) for _, fp in fps]
    conclusions = [final_conclusion(p) for p in (run.get("participants") or [])]
    gen_flags = [
        bool((fp.get("generated_independently") is True)) for _, fp in fps
    ]
    res = residue_report(run)
    return {
        "n_first_pass": len(fps),
        "mean_private_source_jaccard": mean_pairwise_jaccard(priv),
        "mean_first_pass_warrant_jaccard": mean_pairwise_jaccard(wsets),
        "final_conclusion_agreement": pairwise_agreement(conclusions),
        "all_generated_independently": bool(gen_flags) and all(gen_flags),
        "private_source_sets": {pid: sorted(s) for (pid, _), s in zip(fps, priv)},
        "warrant_sets": {pid: sorted(s) for (pid, _), s in zip(fps, wsets)},
        "residue": res,
        "thresholds": {
            "T_SRC": T_SRC,
            "T_WARRANT": T_WARRANT,
            "T_RESIDUE": T_RESIDUE,
            "T_AGREE": T_AGREE,
        },
    }


def detect(run: dict[str, Any]) -> dict[str, Any]:
    snap = snapshot(run)
    if snap["n_first_pass"] < 2:
        return {
            "status": "INSUFFICIENT",
            "fired": False,
            "absence_claimed": False,
            "reason": "fewer than two first-pass briefs; not reported as clean silence",
            "snapshot": snap,
            "s1_shared_retrieval": False,
            "s2_sequential_copy": False,
        }
    s1 = (
        snap["mean_private_source_jaccard"] >= T_SRC
        and snap["mean_first_pass_warrant_jaccard"] >= T_WARRANT
    )
    res = snap["residue"]
    s2 = False
    if res.get("applicable"):
        mean_r = float(res["mean_new_warrant_rate"])
        s2 = mean_r < T_RESIDUE and snap["final_conclusion_agreement"] >= T_AGREE
    if s1 or s2:
        why = []
        if s1:
            why.append(
                f"S1 shared-retrieval: private-source Jaccard "
                f"{snap['mean_private_source_jaccard']:.3f}>={T_SRC} and "
                f"warrant Jaccard {snap['mean_first_pass_warrant_jaccard']:.3f}"
                f">={T_WARRANT}"
            )
        if s2:
            why.append(
                f"S2 sequential-copy: mean new-warrant rate "
                f"{res['mean_new_warrant_rate']:.3f}<{T_RESIDUE} and "
                f"conclusion agreement {snap['final_conclusion_agreement']:.3f}"
                f">={T_AGREE}"
            )
        return {
            "status": "FIRE",
            "fired": True,
            "absence_claimed": False,
            "reason": "; ".join(why),
            "snapshot": snap,
            "s1_shared_retrieval": s1,
            "s2_sequential_copy": s2,
        }
    return {
        "status": "SILENT",
        "fired": False,
        "absence_claimed": True,
        "reason": (
            f"no echo: source Jaccard {snap['mean_private_source_jaccard']:.3f}"
            f"<{T_SRC} or warrant Jaccard "
            f"{snap['mean_first_pass_warrant_jaccard']:.3f}<{T_WARRANT}; "
            f"residue applicable={res.get('applicable')} "
            f"rate={res.get('mean_new_warrant_rate')} "
            f"agreement={snap['final_conclusion_agreement']:.3f}"
        ),
        "snapshot": snap,
        "s1_shared_retrieval": False,
        "s2_sequential_copy": False,
    }


def decoy_generation_independence(run: dict[str, Any]) -> dict[str, Any]:
    """Gameable decoy: FIRE only when some first pass was not independently generated.

    Silent on ADV-0135 shared-source briefs that are independently GENERATED.
    """
    fps = first_passes(run)
    if len(fps) < 2:
        return {
            "status": "INSUFFICIENT",
            "fired": False,
            "decoy": "generation-independence",
        }
    copied = [not bool(fp.get("generated_independently")) for _, fp in fps]
    fired = any(copied)
    return {
        "status": "FIRE" if fired else "SILENT",
        "fired": fired,
        "decoy": "generation-independence",
        "copied_flags": copied,
    }


def decoy_vote_agreement(run: dict[str, Any]) -> dict[str, Any]:
    """Gameable decoy: FIRE when final conclusions agree.

    False-positives genuine independent convergence.
    """
    people = list(run.get("participants") or [])
    if len(people) < 2:
        return {"status": "INSUFFICIENT", "fired": False, "decoy": "vote-agreement"}
    conc = [final_conclusion(p) for p in people]
    agr = pairwise_agreement(conc)
    fired = agr >= T_AGREE
    return {
        "status": "FIRE" if fired else "SILENT",
        "fired": fired,
        "decoy": "vote-agreement",
        "agreement": agr,
        "conclusions": conc,
    }


def format_line(run: dict[str, Any], det: dict[str, Any]) -> str:
    snap = det.get("snapshot") or {}
    res = snap.get("residue") or {}
    return (
        f"fixture={run.get('id')} status={det.get('status')} fired={det.get('fired')} "
        f"absence_claimed={det.get('absence_claimed')} "
        f"src_j={snap.get('mean_private_source_jaccard')} "
        f"w_j={snap.get('mean_first_pass_warrant_jaccard')} "
        f"agree={snap.get('final_conclusion_agreement')} "
        f"s1={det.get('s1_shared_retrieval')} s2={det.get('s2_sequential_copy')} "
        f"residue_applicable={res.get('applicable')} "
        f"residue_rate={res.get('mean_new_warrant_rate')} "
        f"reason={det.get('reason')}"
    )


def dumps(obj: dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=True)


def main(argv: list[str] | None = None) -> int:
    import fixtures as F

    args = list(sys.argv[1:] if argv is None else argv)
    decoy = None
    fixture_id = None
    i = 0
    while i < len(args):
        if args[i] == "--decoy" and i + 1 < len(args):
            decoy = args[i + 1]
            i += 2
            continue
        if args[i] == "--fixture" and i + 1 < len(args):
            fixture_id = args[i + 1]
            i += 2
            continue
        i += 1
    named = F.all_named()
    if not fixture_id or fixture_id not in named:
        print(
            "FAILED:CNL-0086-detector usage --fixture <id> [--decoy generation|vote]",
            file=sys.stderr,
        )
        return 2
    run = named[fixture_id]
    if decoy == "generation":
        out = decoy_generation_independence(run)
    elif decoy == "vote":
        out = decoy_vote_agreement(run)
    else:
        out = detect(run)
    out["fixture"] = fixture_id
    print(dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
