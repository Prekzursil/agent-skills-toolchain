#!/usr/bin/env python3
"""Probe 2: additions-only is not LARGE; deletion is banned (catalog tests 2-3).

Independent of probe 1's assertions: recomputes modified vs added with
`git show` (not cat-file) and a probe-local LARGE floor, then compares
the engine's conflict_surface. Also requires deletion_recommended is
always false and the artifact, if present, has an empty deletion list.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from fixtures import (  # noqa: E402
    build_additions_only,
    build_large_modifications,
    build_superseded_rename,
    control_pack,
    temp_repo,
)
from gitcmd import git_show_path, three_dot_names  # noqa: E402
from paths import workflow_bearing  # noqa: E402

ART = "command-center/wfa/WFA-0014-sweep-branches.json"
LARGE_FLOOR = 8  # probe-local copy; not imported from engine


def _fail(msg: str) -> int:
    print(f"FAILED:WFA-0014-probe2 {msg}")
    return 1


def independent_counts(repo: Path, main: str, branch: str) -> tuple[int, int]:
    """Count same-path mismatches vs additions using git show, not cat-file."""
    modified = 0
    added = 0
    for path in three_dot_names(repo, main, branch):
        if not workflow_bearing(path):
            continue
        main_blob = git_show_path(repo, main, path)
        branch_blob = git_show_path(repo, branch, path)
        if branch_blob is None:
            continue
        if main_blob is None:
            added += 1
        elif main_blob != branch_blob:
            modified += 1
    return modified, added


def independent_surface(modified: int, added: int) -> str:
    if modified >= LARGE_FLOOR:
        return "LARGE"
    if modified > 0:
        return "SMALL"
    if added > 0:
        return "ADDITIONS-ONLY"
    return "NONE"


def main() -> int:
    src = (HERE / "engine.py").read_text(encoding="utf-8")
    emit_src = (HERE / "emit.py").read_text(encoding="utf-8") if (HERE / "emit.py").is_file() else ""
    if "deletion_recommended\": True" in src or "deletion_recommended = True" in src:
        return _fail("engine.py can recommend deletion")
    if "recommend_delete" in src or "recommend_deletion" in src:
        return _fail("engine.py contains a deletion recommender")

    pack = control_pack()
    add = pack["additions_only"]
    large = pack["large_modifications"]
    renamed = pack["superseded_rename"]
    print(
        json.dumps(
            {
                "additions_only": {
                    "added_count": add["added_count"],
                    "modified_count": add["modified_count"],
                    "conflict_surface": add["conflict_surface"],
                    "signal_a_path_count": add["signal_a_path_count"],
                    "deletion_recommended": add["deletion_recommended"],
                },
                "large_modifications": {
                    "added_count": large["added_count"],
                    "modified_count": large["modified_count"],
                    "conflict_surface": large["conflict_surface"],
                    "deletion_recommended": large["deletion_recommended"],
                },
                "superseded_rename": {
                    "unique_content_count": renamed["unique_content_count"],
                    "superseded_count": renamed["superseded_count"],
                    "classifications": sorted(
                        {h["classification"] for h in renamed["hits"]}
                    ),
                },
            },
            sort_keys=True,
        )
    )

    if add["modified_count"] != 0:
        return _fail(f"additions-only modified_count={add['modified_count']}")
    if add["added_count"] < 20:
        return _fail(f"additions-only added_count={add['added_count']} want >=20")
    if add["conflict_surface"] == "LARGE":
        return _fail("additions-only scored LARGE")
    if add["conflict_surface"] != "ADDITIONS-ONLY":
        return _fail(f"additions-only surface={add['conflict_surface']}")
    if add["deletion_recommended"] or large["deletion_recommended"] or renamed["deletion_recommended"]:
        return _fail("a control branch recommended deletion")
    if large["modified_count"] < LARGE_FLOOR:
        return _fail(f"large-mod fixture modified={large['modified_count']}")
    if large["conflict_surface"] != "LARGE":
        return _fail(
            f"large-mod surface={large['conflict_surface']} (vacuous additions test if never LARGE)"
        )
    if renamed["unique_content_count"] != 0:
        return _fail("rename-identical bytes scored unique")
    if renamed["superseded_count"] < 1:
        return _fail("rename fixture produced no SUPERSEDED-DIFFERENT-NAME")

    with temp_repo() as repo:
        build_additions_only(repo, 40)
        mod, added = independent_counts(repo, "main", "feature/many-additions")
        surface = independent_surface(mod, added)
        if mod != 0 or added < 20 or surface != "ADDITIONS-ONLY":
            return _fail(f"independent additions counts mod={mod} added={added} surface={surface}")
        if surface != add["conflict_surface"]:
            return _fail("engine surface disagrees with git-show recount on additions")

    with temp_repo() as repo:
        build_large_modifications(repo, 12)
        mod, added = independent_counts(repo, "main", "feature/large-conflict")
        surface = independent_surface(mod, added)
        if surface != "LARGE" or mod < LARGE_FLOOR:
            return _fail(f"independent large-mod mod={mod} added={added} surface={surface}")
        if surface != large["conflict_surface"]:
            return _fail("engine surface disagrees with git-show recount on modifications")

    with temp_repo() as repo:
        build_superseded_rename(repo)
        old = git_show_path(repo, "feature/old-name", ".github/workflows/old-name.yml")
        new = git_show_path(repo, "main", ".github/workflows/new-name.yml")
        if old is None or new is None or old != new:
            return _fail("rename fixture bytes are not identical under git show")

    art = REPO / ART
    if art.is_file():
        doc = json.loads(art.read_text(encoding="utf-8"))
        recs = doc.get("deletion_recommendations")
        if recs:
            return _fail(f"artifact deletion_recommendations={recs}")
        if doc.get("discovery_only") is not True:
            return _fail("artifact discovery_only is not true")
        live = doc.get("live") or {}
        if live.get("any_deletion_recommended") is True:
            return _fail("live.any_deletion_recommended is true")
        if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return _fail(f"artifact self-declared {doc.get('state')}")
        if "SUCCESS:WFA-0014" not in art.read_text(encoding="utf-8"):
            return _fail("artifact missing SUCCESS:WFA-0014")
        if emit_src and "deletion_recommendations" in emit_src:
            if "deletion_recommendations\": True" in emit_src:
                return _fail("emit.py can emit a true deletion recommendation")

    print("SUCCESS:WFA-0014-probe2 additions-not-LARGE and deletion-ban")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
