#!/usr/bin/env python3
"""Probe 2: independent token recount + anti-rebuild both-states.

Does not trust scout.rank(). Walks corpus files, greps recall tokens at
file:line, and re-runs scout with the superior plant excluded to show BUILD
is allowed only when that incumbent is gone.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import recall as R  # noqa: E402
import scout as S  # noqa: E402

ART = (
    REPO
    / "command-center/foundry/WFA-0145-scout-anti-rebuild-recall-control-with-a-planted-kno.json"
)
CORPUS = HERE / "fixtures" / "corpus"
LOCAL_PLANT_ID = "wf-planted-superior-stage-gate"
LOCAL_GOAL = {
    "id": "goal-local-stage-gate",
    "required_mechanisms": ["wfa0145.plant.local.stage-gate"],
}


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0145-probe2 {msg}")
    return 1


def corpus_json_files() -> list[Path]:
    return [p for p in sorted(CORPUS.rglob("*.json")) if p.is_file()]


def line_hits(path: Path, token: str) -> list[tuple[int, str]]:
    hits = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if token in line:
            hits.append((i, line.strip()))
    return hits


def main() -> int:
    if not ART.is_file():
        return fail("artifact-missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:WFA-0145" not in text:
        return fail("sentinel-absent")

    plants = R.load_plants()
    files = corpus_json_files()
    if len(files) < 7:
        return fail(f"corpus-too-small n={len(files)}")

    blob = "\n".join(p.read_text(encoding="utf-8") for p in files)
    token_rows = []
    for plant in plants["known_present"]:
        token = plant["recall_token"]
        wid = plant["workflow_id"]
        id_files: list[Path] = []
        for path in files:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict) and data.get("id") == wid:
                id_files.append(path)
            for cand in (data.get("candidates") or []) if isinstance(data, dict) else []:
                if isinstance(cand, dict) and cand.get("id") == wid:
                    id_files.append(path)
        if not id_files:
            return fail(f"independent-id-miss {wid}")
        hits = []
        for path in id_files:
            for line_no, snippet in line_hits(path, token):
                rel = path.resolve().relative_to(REPO.resolve()).as_posix()
                hits.append(
                    {
                        "path": rel,
                        "line": line_no,
                        "anchor": f"{rel}:{line_no}",
                        "snippet": snippet[:200],
                    }
                )
        if not hits:
            return fail(f"independent-token-miss {wid} token={token}")
        token_rows.append(
            {
                "workflow_id": wid,
                "token": token,
                "anchors": hits,
                "ok": True,
            }
        )
        print(f"anchor ok=True {hits[0]['anchor']} workflow_id={wid}")

    for plant in plants["known_absent"]:
        token = plant["recall_token"]
        if token in blob:
            return fail(f"absent-token-leaked-into-corpus {token}")
        print(f"absent-token-absent-from-corpus token={token}")

    # Anti-rebuild both-states on the local plant (independent of recall.measure()).
    with_plant = S.scout(LOCAL_GOAL, mode="live")
    without = S.scout(LOCAL_GOAL, mode="live", exclude_ids=frozenset({LOCAL_PLANT_ID}))
    with_ids = [h["id"] for h in with_plant["ranked"]]
    without_ids = [h["id"] for h in without["ranked"]]
    print(
        f"rebuild-gate with_plant route={with_plant['recommendation']} "
        f"cite={with_plant['cited_existing']} ranked={with_ids}"
    )
    print(
        f"rebuild-gate without_plant route={without['recommendation']} "
        f"cite={without['cited_existing']} ranked={without_ids}"
    )
    if LOCAL_PLANT_ID not in with_ids:
        return fail("live-scout-missed-local-plant")
    if with_plant["recommendation"] != "ADOPT":
        return fail(f"superior-present-not-adopt {with_plant['recommendation']}")
    if with_plant["cited_existing"] != LOCAL_PLANT_ID:
        return fail(f"cite-mismatch {with_plant['cited_existing']}")
    if LOCAL_PLANT_ID in without_ids:
        return fail("exclude-did-not-drop-plant")
    if without["recommendation"] != "BUILD":
        return fail(
            f"superior-removed-still-not-build route={without['recommendation']} "
            "(both-states did not flip)"
        )
    if with_plant["recommendation"] == without["recommendation"]:
        return fail("both-states-no-flip")

    claimed_build = (doc.get("anti_rebuild") or {}).get("build_when_superior_present") or []
    live = R.measure(mode="live")
    if live["build_when_superior_present"]:
        return fail(f"live-build-violations {live['build_when_superior_present']}")
    if claimed_build:
        return fail(f"artifact-build-violations {claimed_build}")
    if live["ranked_below_rebuild"]:
        return fail(f"plant-ranked-below-rebuild {live['ranked_below_rebuild']}")

    claimed_frac = (doc.get("recall") or {}).get("recall_fraction")
    if claimed_frac != live["recall_fraction"]:
        return fail("artifact-recall-mismatch-on-independent-recount")

    print(
        json.dumps(
            {
                "probe": "probe2-rebuild-bias-recount",
                "unit_id": "WFA-0145",
                "independent_token_rows": len(token_rows),
                "absent_tokens_missing_from_corpus": True,
                "superior_present_route": with_plant["recommendation"],
                "superior_absent_route": without["recommendation"],
                "cited_existing": with_plant["cited_existing"],
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:WFA-0145-probe2 independent token recount and BUILD both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
