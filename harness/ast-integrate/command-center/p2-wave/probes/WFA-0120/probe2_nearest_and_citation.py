#!/usr/bin/env python3
"""Probe 2: independent nearest-neighbour + citation check on every BUILD-NEW.

Does not call gate.evaluate(). Recomputes cover and evidence comparison from
the corpus, then requires the live artifact to agree.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from corpus import build as build_corpus  # noqa: E402
from gate import plant_rebuild  # noqa: E402
from query import by_route, by_state, registry_candidates  # noqa: E402

OUT_REL = "command-center/wfa/WFA-0120-rebuild-versus-existing-gate.json"
TIER = {"E1": 4, "E2": 3, "E3": 2, "E4": 1, "NONE": 0}


def fail(msg: str, payload: dict | None = None) -> int:
    if payload:
        print(json.dumps(payload, indent=2, sort_keys=True))
    print(f"FAILED:WFA-0120-probe2 {msg}")
    return 1


def mechs(rec: dict) -> frozenset[str]:
    raw = rec.get("mechanisms_from_definition") or []
    if not isinstance(raw, list):
        return frozenset()
    return frozenset(str(x).strip() for x in raw if isinstance(x, str) and x.strip())


def ev(rec: dict) -> tuple[int, int, int]:
    tier = str(rec.get("evidence_tier") or "NONE")
    return (
        TIER.get(tier, 0),
        int(rec.get("independent_source_count") or 0),
        int(rec.get("quality") or 0),
    )


def independent_nearest(proposal: dict, registry: list[dict]) -> dict | None:
    p = mechs(proposal)
    best = None
    best_key = None
    for cand in registry:
        e = mechs(cand)
        inter = p & e
        union = p | e
        jaccard = (len(inter) / len(union)) if union else 0.0
        covers = bool(p) and p <= e
        key = (1 if covers else 0, jaccard, ev(cand), str(cand.get("id") or ""))
        if best_key is None or key > best_key:
            best_key = key
            best = {
                "id": str(cand.get("id") or ""),
                "covers": covers,
                "jaccard": round(jaccard, 6),
                "existing_ge": ev(cand) >= ev(proposal),
                "dominates": covers and ev(cand) >= ev(proposal),
            }
    return best


def main() -> int:
    corpus = build_corpus()
    registry = registry_candidates(corpus)
    build_new = by_route(corpus, "BUILD-NEW")
    new_state = by_state(corpus, "NEW")
    if len(build_new) != 26:
        return fail(f"BUILD-NEW count {len(build_new)} != 26")
    if len(new_state) != 32:
        return fail(f"NEW count {len(new_state)} != 32")
    ids = [b["id"] for b in build_new]
    if len(set(ids)) != 26:
        return fail("duplicate BUILD-NEW ids")

    indep = []
    for bp in build_new:
        row = independent_nearest(bp, registry)
        if row is None:
            return fail(f"{bp['id']} has no nearest")
        indep.append({"proposal_id": bp["id"], **row})

    blocked = [r for r in indep if r["dominates"]]
    allowed = [r for r in indep if not r["dominates"]]
    if not blocked:
        return fail("independent recompute never dominated — detector unshown")
    if not allowed:
        return fail("independent recompute never allowed — always-block")

    # Planted rename must be dominated by cand.lit-review under the independent rule.
    incumbent = next(c for c in registry if c["id"] == "cand.lit-review")
    planted = plant_rebuild(incumbent, "bp.planted-rename-lit-review")
    plant_row = independent_nearest(planted, registry)
    if plant_row is None or not plant_row["dominates"]:
        return fail("independent recompute missed planted rebuild", plant_row)
    if plant_row["id"] != "cand.lit-review":
        return fail(
            f"independent nearest for plant is {plant_row['id']!r} not cand.lit-review",
            plant_row,
        )

    art_path = REPO / OUT_REL
    if not art_path.is_file():
        return fail("artifact missing; emit before this probe")
    art = json.loads(art_path.read_text(encoding="utf-8"))
    if art.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"artifact self-declared {art.get('state')}")
    if "SUCCESS:WFA-0120" not in json.dumps(art):
        return fail("sentinel absent from artifact")

    live_rows = {
        d["proposal_id"]: d for d in (art.get("build_new_decisions") or [])
    }
    if set(live_rows) != set(ids):
        return fail("artifact BUILD-NEW id set != corpus")

    cite_miss = []
    disagree = []
    for row in indep:
        live = live_rows[row["proposal_id"]]
        want = "BLOCK-REBUILD" if row["dominates"] else "ALLOW-BUILD-NEW"
        if live.get("verdict") != want:
            disagree.append((row["proposal_id"], live.get("verdict"), want))
            continue
        if live.get("nearest_existing_id") != row["id"]:
            disagree.append(
                (row["proposal_id"], live.get("nearest_existing_id"), row["id"])
            )
        if "overlap" not in live or live["overlap"] is None:
            disagree.append((row["proposal_id"], "overlap-missing", None))
        if "evidence_comparison" not in live or live["evidence_comparison"] is None:
            disagree.append((row["proposal_id"], "evidence-missing", None))
        if want == "BLOCK-REBUILD":
            cited = live.get("cited_candidate_id")
            if cited != row["id"]:
                cite_miss.append((row["proposal_id"], cited, row["id"]))
            if cited not in {c["id"] for c in registry}:
                cite_miss.append((row["proposal_id"], cited, "not-in-registry"))

    if disagree:
        return fail(f"artifact disagrees with independent recompute {disagree[:5]}")
    if cite_miss:
        return fail(f"BLOCK missing/wrong citation {cite_miss[:5]}")

    plant_live = None
    for ctrl in art.get("controls") or []:
        if ctrl.get("id") == "planted-rename-rebuild":
            plant_live = ctrl.get("gated") or {}
    if not plant_live:
        return fail("artifact missing planted-rename-rebuild control")
    if plant_live.get("cited_candidate_id") != "cand.lit-review":
        return fail("artifact planted control did not cite cand.lit-review", plant_live)

    payload = {
        "probe": "probe2-nearest-and-citation",
        "unit_id": "WFA-0120",
        "n_build_new": len(build_new),
        "n_new": len(new_state),
        "n_blocked": len(blocked),
        "n_allowed": len(allowed),
        "planted_independent_cited": plant_row["id"],
        "disagree": 0,
        "cite_miss": 0,
        "pass": True,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        f"build_new={len(build_new)} new={len(new_state)} "
        f"blocked={len(blocked)} allowed={len(allowed)} "
        "planted_cited=cand.lit-review artifact_agrees=True"
    )
    print("SUCCESS:WFA-0120-probe2 nearest-overlap-evidence citations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
