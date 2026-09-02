"""Premature-convergence detector: quota attainment at first stop, not round count.

FIRE when the first converge happens and unique idea clusters or unique
objection clusters are below the declared divergence quotas.

SILENT when the first converge happens and both quotas are met (including
genuinely easy questions whose quotas are small and attained in round 1).

NO-CONVERGE is not silence: a hanging council is not reported as clean.
"""
from __future__ import annotations

from typing import Any

from transcript import (
    cluster_count,
    events_until,
    first_converge_index,
    idea_quota,
    items_of_kind,
    objection_quota,
    taxonomy_of,
)


def format_line(run: dict[str, Any], det: dict[str, Any]) -> str:
    s = det["snapshot"]
    return (
        f"fixture={run['id']} status={det['status']} fired={det['fired']} "
        f"absence_claimed={det.get('absence_claimed')} "
        f"idea_clusters={s['idea_clusters']} objection_clusters={s['objection_clusters']} "
        f"idea_quota={s['idea_quota']} objection_quota={s['objection_quota']} "
        f"idea_events={s['idea_events']} objection_events={s['objection_events']} "
        f"converge_round={s['converge_round']} covered={s['covered_categories']}"
    )


def snapshot_at_first_converge(run: dict[str, Any]) -> dict[str, Any]:
    events = list(run.get("events") or [])
    idx = first_converge_index(events)
    prior = events_until(events, idx)
    n_ideas = cluster_count(prior, "idea")
    n_obj = cluster_count(prior, "objection")
    iq, oq = idea_quota(run), objection_quota(run)
    covered = sorted(
        {
            str(e.get("category"))
            for e in items_of_kind(prior, "idea")
            if e.get("category")
        }
    )
    tax = taxonomy_of(run)
    uncovered = [c for c in tax if c not in set(covered)]
    converge_round = None
    if idx is not None:
        converge_round = events[idx].get("round")
        thesis = events[idx].get("thesis")
    else:
        thesis = None
    quotas_met = n_ideas >= iq and n_obj >= oq
    return {
        "converge_index": idx,
        "converge_round": converge_round,
        "thesis": thesis,
        "idea_clusters": n_ideas,
        "objection_clusters": n_obj,
        "idea_quota": iq,
        "objection_quota": oq,
        "idea_events": len(items_of_kind(prior, "idea")),
        "objection_events": len(items_of_kind(prior, "objection")),
        "covered_categories": covered,
        "uncovered_categories": uncovered,
        "quotas_met": quotas_met,
    }


def detect(run: dict[str, Any]) -> dict[str, Any]:
    snap = snapshot_at_first_converge(run)
    idx = snap["converge_index"]
    if idx is None:
        return {
            "status": "NO-CONVERGE",
            "fired": False,
            "absence_claimed": False,
            "reason": "no converge event; not reported as clean silence",
            "snapshot": snap,
        }
    if snap["quotas_met"]:
        return {
            "status": "SILENT",
            "fired": False,
            "absence_claimed": True,
            "reason": (
                f"quotas met at first converge: ideas "
                f"{snap['idea_clusters']}>={snap['idea_quota']} and "
                f"objections {snap['objection_clusters']}>={snap['objection_quota']}"
            ),
            "snapshot": snap,
        }
    missing_i = max(0, snap["idea_quota"] - snap["idea_clusters"])
    missing_o = max(0, snap["objection_quota"] - snap["objection_clusters"])
    return {
        "status": "FIRE",
        "fired": True,
        "absence_claimed": False,
        "reason": (
            f"premature converge at round={snap['converge_round']}: "
            f"idea_clusters={snap['idea_clusters']}<{snap['idea_quota']} "
            f"(missing {missing_i}) or "
            f"objection_clusters={snap['objection_clusters']}<{snap['objection_quota']} "
            f"(missing {missing_o}); uncovered={snap['uncovered_categories']}"
        ),
        "snapshot": snap,
        "missing_idea_clusters": missing_i,
        "missing_objection_clusters": missing_o,
    }


def decoy_round_count(run: dict[str, Any], min_rounds: int = 3) -> dict[str, Any]:
    """Gameable decoy: FIRE if first converge.round < min_rounds.

    False-positives the easy-question control (round 1, quotas met).
    False-negatives a round-10 premature stop (quotas unmet).
    """
    snap = snapshot_at_first_converge(run)
    rnd = snap["converge_round"]
    if rnd is None:
        return {"status": "NO-CONVERGE", "fired": False, "decoy": "round-count"}
    fired = int(rnd) < min_rounds
    return {
        "status": "FIRE" if fired else "SILENT",
        "fired": fired,
        "decoy": "round-count",
        "converge_round": rnd,
        "min_rounds": min_rounds,
    }


def decoy_event_count(run: dict[str, Any]) -> dict[str, Any]:
    """Gameable decoy: count idea/objection events, not clusters.

    Silent on paraphrase-padded premature runs (CNL-0052 count gaming).
    """
    snap = snapshot_at_first_converge(run)
    if snap["converge_index"] is None:
        return {"status": "NO-CONVERGE", "fired": False, "decoy": "event-count"}
    met = (
        snap["idea_events"] >= snap["idea_quota"]
        and snap["objection_events"] >= snap["objection_quota"]
    )
    fired = not met
    return {
        "status": "FIRE" if fired else "SILENT",
        "fired": fired,
        "decoy": "event-count",
        "idea_events": snap["idea_events"],
        "objection_events": snap["objection_events"],
    }


def freeze_mandate(run: dict[str, Any]) -> dict[str, Any] | None:
    """Complement-quota re-divergence mandate after a premature first stop.

    A second round of the same protocol is not this mandate. Recovery
    requires NEW clusters in uncovered taxonomy categories (or, if none
    uncovered, new clusters Jaccard-far from the frozen set) plus new
    objection clusters against the frozen thesis.
    """
    det = detect(run)
    if not det["fired"]:
        return None
    snap = det["snapshot"]
    return {
        "kind": "forced-re-divergence",
        "not": "second-round-of-same-protocol",
        "freeze_thesis": snap["thesis"],
        "freeze_converge_index": snap["converge_index"],
        "require_new_idea_clusters": det["missing_idea_clusters"],
        "require_new_objection_clusters": det["missing_objection_clusters"],
        "require_categories": list(snap["uncovered_categories"]),
        "reconverge_blocked_until": (
            "post-freeze new idea clusters in require_categories "
            "(or Jaccard-far if require_categories empty) meet the missing "
            "idea quota AND new objection clusters meet the missing "
            "objection quota"
        ),
    }


def post_freeze_progress(run: dict[str, Any]) -> dict[str, Any]:
    """Count post-freeze NEW clusters (detector clustering) with category constraint."""
    from transcript import cluster_texts, tokens, jaccard, JACCARD_DUP

    mandate = freeze_mandate(run)
    events = list(run.get("events") or [])
    if mandate is None:
        return {
            "mandate": None,
            "permitted": True,
            "reason": "no premature first stop; no intervention",
        }
    freeze_i = int(mandate["freeze_converge_index"])
    prior = events[: freeze_i]
    later = events[freeze_i + 1 :]
    later_until = later
    later_conv = None
    for i, ev in enumerate(later):
        if ev.get("kind") == "converge":
            later_conv = i
            later_until = later[:i]
            break

    prior_ideas = [str(e.get("text") or "") for e in items_of_kind(prior, "idea")]
    prior_objs = [str(e.get("text") or "") for e in items_of_kind(prior, "objection")]
    req_cats = set(mandate["require_categories"] or [])

    new_idea_texts: list[str] = []
    new_idea_cats: list[str] = []
    for e in items_of_kind(later_until, "idea"):
        text = str(e.get("text") or "")
        cat = str(e.get("category") or "")
        bag = tokens(text)
        dup = any(jaccard(bag, tokens(p)) >= JACCARD_DUP for p in prior_ideas)
        if dup:
            continue
        if req_cats and cat not in req_cats:
            continue
        new_idea_texts.append(text)
        new_idea_cats.append(cat)

    new_obj_texts: list[str] = []
    for e in items_of_kind(later_until, "objection"):
        text = str(e.get("text") or "")
        bag = tokens(text)
        dup = any(jaccard(bag, tokens(p)) >= JACCARD_DUP for p in prior_objs)
        if dup:
            continue
        new_obj_texts.append(text)

    n_new_i = len(cluster_texts(new_idea_texts)) if new_idea_texts else 0
    n_new_o = len(cluster_texts(new_obj_texts)) if new_obj_texts else 0
    need_i = int(mandate["require_new_idea_clusters"])
    need_o = int(mandate["require_new_objection_clusters"])
    permitted = n_new_i >= need_i and n_new_o >= need_o
    return {
        "mandate": mandate,
        "later_converge_present": later_conv is not None,
        "new_idea_clusters_in_complement": n_new_i,
        "new_objection_clusters": n_new_o,
        "new_idea_categories": sorted(set(new_idea_cats)),
        "need_idea_clusters": need_i,
        "need_objection_clusters": need_o,
        "permitted": permitted,
        "reason": (
            "complement quotas met; reconverge permitted"
            if permitted
            else (
                f"reconverge blocked: new_idea_clusters_in_complement="
                f"{n_new_i}<{need_i} or new_objection_clusters={n_new_o}<{need_o}"
            )
        ),
    }
