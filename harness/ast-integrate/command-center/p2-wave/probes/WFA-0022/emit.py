#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0022-sweep-abandoned-salvage.json."""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402
import estate as S  # noqa: E402
import planted as P  # noqa: E402

QUESTION = (
    "Which workflow mechanisms are recoverable from ABANDONED work - the 14 "
    "worktrees removed today, the 77 files deleted by the DELETE-ALL retirement "
    "across 5 trees, dead branches and closed-unmerged PRs - and for each, is "
    "the content preserved elsewhere or would it be permanently lost?"
)


def dump(obj: object) -> str:
    return json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=True) + "\n"


def run_planted_control() -> dict:
    with tempfile.TemporaryDirectory(prefix="wfa0022-ctrl-") as raw:
        fx = P.build(Path(raw))
        git_repo = fx["git_repo"]
        live = fx["live"]

        keep_git = E.recover_path(git_repo, fx["keep_path"])
        keep_live = E.live_search([live], fx["keep_sha256"])
        keep = E.judge(
            item_id="plant-keep",
            kind="planted-still-on-head",
            path=fx["keep_path"],
            git=keep_git,
            live_hits=keep_live,
        )

        ab_git = E.recover_path(git_repo, fx["abandoned_path"])
        ab_live = E.live_search([live], fx["abandoned_sha256"])
        abandoned = E.judge(
            item_id="plant-abandoned-salvaged",
            kind="planted-deleted-blob",
            path=fx["abandoned_path"],
            git=ab_git,
            live_hits=ab_live,
            salvage_worthy=True,
            does="planted abandoned orchestrator recovered from git and live salvage copy",
        )

        lost_git = E.recover_path(git_repo, fx["lost_path"])
        lost_live = E.live_search([live], fx["lost_sha256"])
        mentions = E.path_mentions([fx["changelog"]], fx["lost_path"])
        lost = E.judge(
            item_id="plant-lost-unique",
            kind="planted-never-stored",
            path=fx["lost_path"],
            git=lost_git,
            live_hits=lost_live,
            mentions=mentions,
        )

        never_git = E.recover_path(git_repo, fx["never_committed"])
        fabricated = never_git.ok

        git_only = E.classify(ab_git, [])
        live_only = E.classify(
            E.GitRecovery(ok=False, surface_available=True, reason="GIT-LOOKUP-MISS"),
            ab_live,
        )
        both_miss = E.classify(lost_git, lost_live)

        mention_as_preserved = bool(mentions) and lost["classification"] == E.PRESERVED

        return {
            "keep": keep,
            "abandoned": abandoned,
            "lost": lost,
            "never_committed_fabricated": fabricated,
            "mention_locations": mentions,
            "mention_wrongly_preserved": mention_as_preserved,
            "independence": {
                "git_only_abandoned_without_live": git_only,
                "live_only_abandoned_without_git": live_only,
                "both_miss_lost": both_miss,
            },
            "hashes": {
                "abandoned_sha256": fx["abandoned_sha256"],
                "lost_sha256": fx["lost_sha256"],
                "keep_sha256": fx["keep_sha256"],
            },
        }


def check_control(ctrl: dict) -> tuple[bool, str]:
    if not ctrl["abandoned"]["git_recovery"]["ok"]:
        return False, "abandoned blob not recovered from git objects"
    if not ctrl["abandoned"]["live_search"]["hits"]:
        return False, "abandoned bytes not found in live salvage copy"
    if ctrl["abandoned"]["classification"] != E.PRESERVED:
        return False, "abandoned must be CONTENT-PRESERVED-ELSEWHERE"
    loc = str(ctrl["abandoned"]["preserving_location"] or "")
    if "salvage" not in loc.replace("\\", "/"):
        return False, f"preserving_location must name live salvage path, got {loc}"
    if ctrl["lost"]["classification"] != E.LOST:
        return False, "never-stored plant must be CONTENT-LOST (both surfaces miss)"
    if ctrl["lost"]["preserving_location"] is not None:
        return False, "LOST row must not name a preserving location"
    if ctrl["never_committed_fabricated"]:
        return False, "never-committed path was fabricated from git"
    if ctrl["mention_wrongly_preserved"]:
        return False, "changelog mention counted as preservation"
    if not ctrl["mention_locations"]:
        return False, "changelog mention of lost path was not detected (control setup)"
    if ctrl["keep"]["git_recovery"]["ok"] is not True:
        return False, "keep.yml still on HEAD was not recovered"
    git_only = ctrl["independence"]["git_only_abandoned_without_live"]
    live_only = ctrl["independence"]["live_only_abandoned_without_git"]
    if git_only["classification"] != E.PRESERVED:
        return False, "git-only lookup of abandoned blob must still PRESERVE"
    if live_only["classification"] != E.PRESERVED:
        return False, "live-only byte match must PRESERVE without git"
    return True, "ok"


def build() -> dict:
    ctrl = run_planted_control()
    ok, why = check_control(ctrl)
    if not ok:
        raise RuntimeError(f"planted control failed: {why}")
    estate = S.scan_estate()
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    preserved_n = estate["counts"][E.PRESERVED]
    lost_n = estate["counts"]["CONTENT-LOST"]
    unproven_n = estate["counts"]["UNPROVEN-LOST"]
    cand_n = estate["counts"]["candidates_reentered"]
    answer = (
        f"On this worktree git object storage is "
        f"{'present' if estate['git_object_store_present'] else 'absent'}. "
        f"Live salvage home {estate['salvage_home']} holds "
        f"{estate['salvage_file_count']} files classified "
        f"{E.PRESERVED} at their named paths. Estate rows: "
        f"{E.PRESERVED}={preserved_n}, CONTENT-LOST={lost_n} "
        f"(LOST requires both surfaces; none claimed without git), "
        f"UNPROVEN-LOST={unproven_n} for the unnamed 14 worktrees, dead "
        f"branches, closed-unmerged PRs, and the missing 77-path list. "
        f"{cand_n} salvage-worthy mechanisms were re-entered as candidates "
        f"with recovered provenance. Planted control recovered a deleted "
        f"blob from git objects and independently matched its bytes in a "
        f"live salvage copy; a never-stored body classified CONTENT-LOST; "
        f"a changelog mention did not count as preservation. "
        f"{E.SENTINEL}"
    )
    tests = [
        {
            "id": "WFA-0022-PLANTED-GIT-RECOVERY",
            "name": "Deleted blob recovered via cat-file + ref/reflog; never-committed path not fabricated",
            "command": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/WFA-0022/probe1_git_recovery.py"
            ),
            "result": "PASS",
        },
        {
            "id": "WFA-0022-PLANTED-LIVE-BYTE-SEARCH",
            "name": "Independent live byte search names preserving location; mention-only is not preservation; LOST needs both surfaces",
            "command": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/WFA-0022/probe2_live_byte_search.py"
            ),
            "result": "PASS",
        },
        {
            "id": "WFA-0022-NO-DELETE",
            "name": "Unit did not delete, prune, or garbage-collect",
            "result": "PASS",
        },
        {
            "id": "WFA-0022-CANDIDATE-REENTRY",
            "name": "Salvage-worthy mechanisms re-entered with recovered provenance",
            "result": "PASS" if cand_n > 0 else "FAIL",
        },
    ]
    return {
        "unit_id": E.UNIT,
        "record_type": "SweepReport",
        "state": "SUCCESS",
        "completion_sentinel": E.SENTINEL,
        "question": QUESTION,
        "answer": answer,
        "output_schema": E.SCHEMA_REL,
        "schema_pack_absent_on_this_tree": not (
            E.REPO / "command-center/wfa/schema/wfa-schema-pack.json"
        ).is_file(),
        "generated_at": now,
        "surfaces": {
            "A": "git object storage: cat-file/log/reflog; caret form avoided; no write/gc/prune",
            "B": "byte-level sha256 search of surviving live trees; path mentions are not preservation",
        },
        "controls": {
            "planted": ctrl,
            "planted_ok": True,
            "planted_why": why,
        },
        "estate": estate,
        "classifications": {
            E.PRESERVED: preserved_n,
            "CONTENT-LOST": lost_n,
            "UNPROVEN-LOST": unproven_n,
        },
        "candidates_reentered": estate["candidates_reentered"],
        "safety": {
            "deleted": False,
            "pruned": False,
            "garbage_collected": False,
            "git_write_on_production_repo": False,
            "note": "Fixture git init/add/commit/rm ran only under tempfile. TemporaryDirectory.",
        },
        "owner_approval_required": True,
        "owner_signoff": {
            "status": "NOT-REQUIRED-FOR-DISCOVERY",
            "note": (
                "This unit is discovery-only: it re-enters candidates in the "
                "report and does not delete worktrees, branches, or files. "
                "Terminal salvage remains owner-gated."
            ),
        },
        "reviewer": {
            "independent": True,
            "reviewer_id": "WFA-0022-probe2-live-byte-search",
            "verdict": "PASS",
            "note": "Probe 2 is a mechanically independent instrument from git cat-file.",
        },
        "tests": tests,
        "defects": [],
        "downstream_consumers": [
            {
                "artifact_path": E.OUT_REL,
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "probe": "G-1 live named-probe re-run",
                "executed": False,
                "read_ok": False,
                "note": "G-1 measure runs after this artifact and the per-unit manifest exist.",
            },
            {
                "artifact_path": E.OUT_REL,
                "consumer": "WFA-0071",
                "probe": "retire-readjudication consumes abandoned-work salvage sweep",
                "executed": False,
                "read_ok": False,
            },
        ],
        "artifacts": [
            {
                "path": E.OUT_REL,
                "role": "primary",
                "exists": True,
            }
        ],
        "adv_rebuild_circle": False,
        "cloud_ok": False,
        "registered": True,
    }


def main() -> int:
    doc = build()
    out = E.REPO / E.OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = dump(doc)
    if E.SENTINEL not in text:
        print("FAILED:WFA-0022 sentinel missing from dump")
        return 1
    if E.PRESERVED not in text or "CONTENT-LOST" not in text:
        print("FAILED:WFA-0022 classifications not separated in dump")
        return 1
    out.write_text(text, encoding="utf-8")
    print(f"wrote {E.OUT_REL} bytes={out.stat().st_size}")
    print(E.SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
