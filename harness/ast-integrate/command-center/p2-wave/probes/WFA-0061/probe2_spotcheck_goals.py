#!/usr/bin/env python3
"""Probe 2: body-file spot checks, planted extraction miss, typed goals.

Reads fixtures/bodies/*.json directly. Does not trust the matrix cells.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import corpus as C  # noqa: E402
import coverage as CV  # noqa: E402
import extract as E  # noqa: E402
import goals as G  # noqa: E402
import sources as S  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0061-mechanism-coverage-gaps.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0061-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "WFA-0061":
        return fail(f"unit_id={doc.get('unit_id')}")

    corpus = C.load_corpus()
    bodies = C.materialize_bodies(corpus)
    if len(bodies) < 10:
        return fail(f"too few body files {len(bodies)}")

    kind_map = dict(corpus.get("kind_map") or {})
    vids = E.vocab_ids(list(corpus.get("vocabulary") or []))
    uncovered = list(doc.get("uncovered_mechanisms") or [])
    empty = list(doc.get("empty_blueprints") or [])
    if len(uncovered) < 1 or len(empty) < 1:
        return fail("artifact hid a direction")

    bp_bodies = {}
    for rec in corpus.get("blueprints") or []:
        bid = str(rec["id"])
        body = C.read_body(bid)
        bp_bodies[bid] = body
        if body.get("stages") != rec.get("stages"):
            return fail(f"body file drifted from corpus for {bid}")

    # Independent of matrix: re-derive both gap lists from body files.
    cand_mechs: dict[str, set[str]] = {}
    for rec in corpus.get("candidates") or []:
        cid = str(rec["id"])
        body = C.read_body(cid)
        cand_mechs[cid] = set(E.extract_from_definition(body, kind_map, vids))
    bp_mechs: dict[str, set[str]] = {}
    for bid, body in bp_bodies.items():
        bp_mechs[bid] = set(E.extract_from_definition(body, kind_map, vids))

    mech_in_cand = set().union(*cand_mechs.values()) if cand_mechs else set()
    mech_in_bp = set().union(*bp_mechs.values()) if bp_mechs else set()
    body_uncovered = sorted(mech_in_cand - mech_in_bp)
    body_empty = sorted(bid for bid, ms in bp_mechs.items() if not ms)
    if body_uncovered != uncovered:
        return fail(f"body-derived uncovered {body_uncovered} != artifact {uncovered}")
    if body_empty != empty:
        return fail(f"body-derived empty {body_empty} != artifact {empty}")

    spots = doc.get("spot_checks") or {}
    if int(spots.get("n_checked") or 0) < 10:
        return fail(f"spot-check n={spots.get('n_checked')} want>=10")
    if spots.get("all_survived") is not True:
        return fail("spot checks did not all survive")
    if spots.get("both_directions_in_sample") is not True:
        return fail("spot-check sample hid a direction")

    n_ok = 0
    for row in spots.get("rows") or []:
        gap_id = str(row.get("gap_id") or "")
        direction = str(row.get("direction") or "")
        if direction == "uncovered_mechanism":
            hits = [bid for bid, ms in bp_mechs.items() if gap_id in ms]
            if hits:
                return fail(f"uncovered {gap_id} implemented by {hits}")
            n_ok += 1
        elif direction == "empty_blueprint":
            body = C.read_body(gap_id)
            mechs = E.extract_from_definition(body, kind_map, vids)
            if mechs:
                return fail(f"empty {gap_id} body implements {mechs}")
            n_ok += 1
        else:
            return fail(f"unknown spot-check direction {direction}")
    if n_ok < 10:
        return fail(f"body-confirmed spot checks {n_ok} want>=10")

    planted = "bp.prose-says-empty"
    planted_body = C.read_body(planted)
    planted_def = E.extract_from_definition(planted_body, kind_map, vids)
    planted_prose = E.extract_from_self_description(planted_body, vids)
    if "mech.python-execute" not in planted_def:
        return fail("planted miss body does not implement python-execute")
    if planted_prose:
        return fail("planted miss prose field was not empty")
    if planted in empty:
        return fail("planted extraction miss published as empty")
    if planted in body_empty:
        return fail("body-derived empty still includes planted miss")

    mention = C.read_body("bp.mention-only")
    if E.extract_from_definition(mention, kind_map, vids):
        return fail("mention-only blueprint credited from definition")
    if "mech.quota-gate" not in set(E.extract_from_self_description(mention, vids)):
        return fail("mention-only self-description lost the trap")
    if "mech.fire-and-forget-dispatch" not in uncovered:
        return fail("fire-and-forget not uncovered (mention trap swallowed it)")
    docs = C.read_body("bp.docs-mention-uncovered")
    if "mech.fire-and-forget-dispatch" in E.extract_from_definition(docs, kind_map, vids):
        return fail("docs-mention blueprint credited with fire-and-forget")

    goals = doc.get("generation_lane_goals")
    if G.looks_like_bare_id_list(goals):
        return fail("goals collapsed to an id list")
    ok, missing = G.goals_cover_gaps(goals, uncovered, empty)
    if not ok:
        return fail(f"gaps without typed goals {missing}")
    bare_mutant = uncovered + empty
    if not G.looks_like_bare_id_list(bare_mutant):
        return fail("bare-id-list mutant was not detected")

    live = S.inventory(REPO)
    worktree_docs = CV.load_worktree_docs(REPO, live.get("worktree_observed") or [])
    computed = CV.compute(corpus, live, worktree_docs)
    miss = computed["planted_extraction_miss"]
    if miss["published_as_empty"] or not miss["prose_extractor_lists_as_empty"]:
        return fail("planted-miss both-states broken")

    payload = {
        "pass": True,
        "probe": "probe2-spotcheck-goals",
        "unit_id": "WFA-0061",
        "n_body_confirmed": n_ok,
        "planted_miss_not_published": True,
        "prose_mutant_fires": True,
        "use_versus_mention_holds": True,
        "typed_goals": True,
        "bare_list_mutant_detected": True,
        "reviewer_starts_from_tests": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"body_confirmed={n_ok} planted_not_empty=True typed_goals=True "
        f"bare_list_detected=True"
    )
    print("SUCCESS:WFA-0061-probe2 body spot-check and typed generation-lane goals")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
