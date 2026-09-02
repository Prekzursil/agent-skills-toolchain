#!/usr/bin/env python3
"""Probe 2: honest empty gap + anti-rebuild both-states (independent recount)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from constants import ADEQUATE_COVERAGE, ARTIFACT_REL, REPO  # noqa: E402
import gate  # noqa: E402
import licence  # noqa: E402
import recount  # noqa: E402
import scout  # noqa: E402
import surface  # noqa: E402
import verify  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0127-probe2 {msg}")
    return 1


def verified_pool(goal: dict) -> list[dict]:
    cons = scout._constraints(goal)
    allow = cons["licence_allow"] or None
    out: list[dict] = []
    for source_class in cons["source_classes"]:
        for rec in surface.iter_class(source_class):
            root = Path(str(rec.get("_anchor_root") or ""))
            prov = verify.verify_candidate(rec, root)
            if prov.get("verdict") != "VERIFIED":
                continue
            if licence.is_unknown(rec.get("licence_class")):
                continue
            if not licence.allowed(rec.get("licence_class"), allow):
                continue
            out.append(rec)
    return out


def main() -> int:
    artifact = REPO / ARTIFACT_REL
    if not artifact.is_file():
        return fail("artifact-missing")
    doc = json.loads(artifact.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail("artifact-not-success")

    empty_goal = scout.load_goal("empty")
    empty = scout.run(empty_goal)
    if empty.get("ranked"):
        return fail(f"empty-padded {empty.get('ranked_ids')}")
    if not empty.get("empty_honest"):
        return fail("empty-not-honest")
    missing = empty.get("gap", {}).get("missing_mechanisms") or []
    if "quantum.teleport.workflow" not in missing:
        return fail(f"gap-uncharacterised {missing}")
    if "wf-unrelated-hook" in (empty.get("ranked_ids") or []):
        return fail("decoy-padded-empty")
    if empty.get("build_recommendation") is not None:
        return fail("empty-built-without-allow")

    pool = verified_pool(empty_goal)
    independent = [recount.score_row(empty_goal["mechanisms"], rec) for rec in pool]
    over = [r for r in independent if float(r["coverage"]) >= ADEQUATE_COVERAGE]
    if over:
        return fail(f"independent-recount-found-adequate {over}")
    print(
        f"empty ranked=0 gap={missing} independent_adequate=0 "
        f"verified_pool={len(pool)}"
    )

    compose_goal = scout.load_goal("compose")
    compose = scout.run(compose_goal)
    dispositions = {r.get("disposition") for r in compose.get("ranked") or []}
    ids = [str(i) for i in (compose.get("ranked_ids") or [])]
    if "COMPOSE" not in dispositions and not any(i.startswith("compose:") for i in ids):
        return fail(f"compose-miss {ids}")
    print(f"compose ranked={ids}")

    rebuild_goal = scout.load_goal("rebuild")
    cited = str(rebuild_goal.get("anti_rebuild_citation") or "wf-superior-review")
    production = scout.run(rebuild_goal, skip_anti_rebuild_gate=False)
    mutant = scout.run(rebuild_goal, skip_anti_rebuild_gate=True)
    if production.get("build_recommendation") is not None:
        return fail(f"rebuild-built {production.get('build_recommendation')}")
    if cited not in (production.get("ranked_ids") or []):
        return fail(f"rebuild-missed-existing {production.get('ranked_ids')}")
    if production.get("anti_rebuild", {}).get("cited_id") != cited:
        return fail(f"rebuild-citation {production.get('anti_rebuild')}")
    if not production.get("anti_rebuild", {}).get("block_build"):
        return fail("rebuild-gate-did-not-block")
    if (mutant.get("build_recommendation") or {}).get("disposition") != "BUILD":
        return fail("mutant-did-not-build")
    if mutant.get("anti_rebuild", {}).get("skipped") is not True:
        return fail("mutant-gate-not-skipped")

    pool_r = verified_pool(rebuild_goal)
    recount_hit = gate.nearest_existing(rebuild_goal["mechanisms"], pool_r)
    if recount_hit is None or recount_hit.get("id") != cited:
        return fail(
            f"independent-gate-miss {None if recount_hit is None else recount_hit.get('id')}"
        )
    print(
        f"rebuild production_build={production.get('build_recommendation')} "
        f"cited={cited} mutant_build={mutant.get('build_recommendation', {}).get('disposition')}"
    )

    novel = scout.run(scout.load_goal("novel_build"))
    if novel.get("ranked"):
        return fail(f"novel-padded {novel.get('ranked_ids')}")
    build = novel.get("build_recommendation") or {}
    if build.get("disposition") != "BUILD" or build.get("gate") != "PASS":
        return fail(f"novel-build-not-passed {build}")
    if novel.get("anti_rebuild", {}).get("block_build"):
        return fail("novel-false-block")
    print(f"novel build={build.get('disposition')} gate={build.get('gate')}")
    print(
        "SUCCESS:WFA-0127-probe2 honest-empty+gap; anti-rebuild blocks BUILD and "
        "cites existing; novel BUILD passes; mutant skip emits BUILD"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
