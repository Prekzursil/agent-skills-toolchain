#!/usr/bin/env python3
"""Probe 2: independent live byte search; mention-only is not preservation.

Both-states:
  * abandoned bytes in a differently named live path -> PRESERVED with that path
  * never-stored bytes -> CONTENT-LOST only because git lookup also missed
  * changelog naming a deleted path does not preserve
  * skipping git cannot be how LOST is proven (git-only blob stays PRESERVED)
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402
import planted as P  # noqa: E402

ART = E.REPO / E.OUT_REL
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0022-probe2 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="wfa0022-p2-") as raw:
        fx = P.build(Path(raw))
        git_repo = fx["git_repo"]
        live = fx["live"]

        ab_git = E.recover_path(git_repo, fx["abandoned_path"])
        ab_live = E.live_search([live], fx["abandoned_sha256"])
        if not ab_live:
            return fail("live search missed salvage copy of abandoned bytes")
        salvage = ab_live[0]["path"].replace("\\", "/")
        if "salvage/abandoned-orchestrator.yml" not in salvage:
            return fail(f"preserving hit is not the salvage copy: {salvage}")
        if ab_live[0]["sha256"] != fx["abandoned_sha256"]:
            return fail("live hit sha mismatch")

        live_only = E.classify(
            E.GitRecovery(ok=False, surface_available=True, reason="GIT-LOOKUP-MISS"),
            ab_live,
        )
        if live_only["classification"] != E.PRESERVED:
            return fail("live-only byte match must PRESERVE")
        if "salvage" not in str(live_only["preserving_location"]):
            return fail("live-only preserving_location must name the salvage path")

        git_only = E.classify(ab_git, [])
        if git_only["classification"] != E.PRESERVED:
            return fail("git-only recovery must PRESERVE (else LOST is single-surface)")
        if not str(git_only["preserving_location"] or "").startswith("git:blob="):
            return fail("git-only location must name blob+ref")

        lost_git = E.recover_path(git_repo, fx["lost_path"])
        lost_live = E.live_search([live], fx["lost_sha256"])
        mentions = E.path_mentions([fx["changelog"]], fx["lost_path"])
        if not mentions:
            return fail("changelog should mention lost-unique.yml")
        lost = E.classify(lost_git, lost_live)
        if lost["classification"] != E.LOST:
            return fail(f"never-stored plant must be LOST, got {lost}")
        if lost_live:
            return fail("lost bytes appeared in live tree")
        if lost_git.ok:
            return fail("lost bytes appeared in git")

        unproven = E.classify(
            E.GitRecovery(
                ok=False,
                surface_available=False,
                reason="GIT-OBJECT-STORE-ABSENT",
            ),
            [],
        )
        if unproven["classification"] != E.UNPROVEN:
            return fail("single-surface miss without git must be UNPROVEN, not LOST")

        row = E.judge(
            item_id="plant-lost",
            kind="planted",
            path=fx["lost_path"],
            git=lost_git,
            live_hits=lost_live,
            mentions=mentions,
        )
        if row["classification"] == E.PRESERVED:
            return fail("mention-only classified PRESERVED")

        summary = {
            "probe": "probe2-live-byte-search",
            "live_hits": ab_live,
            "preserving_location": live_only["preserving_location"],
            "git_only_preserved": git_only["classification"] == E.PRESERVED,
            "live_only_preserved": live_only["classification"] == E.PRESERVED,
            "lost": lost["classification"],
            "unproven_without_git": unproven["classification"],
            "mentions": mentions,
            "mention_not_preserved": row["classification"] != E.PRESERVED,
            "pass": True,
            "unit_id": E.UNIT,
        }
        print(json.dumps(summary, sort_keys=True))
        print(
            f"live_preserved={live_only['preserving_location']} "
            f"lost={lost['classification']} mentions={len(mentions)}"
        )

    if not ART.is_file():
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if E.SENTINEL not in text:
        return fail("sentinel absent")
    if E.PRESERVED not in text or "CONTENT-LOST" not in text:
        return fail("artifact does not separate CONTENT-LOST from PRESERVED")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return fail(f"artifact self-declared {st}")
    if not doc.get("candidates_reentered"):
        return fail("no candidates re-entered")
    estate = doc.get("estate") or {}
    for item in estate.get("items") or []:
        if item.get("classification") == E.LOST and not (
            (item.get("git_recovery") or {}).get("surface_available")
        ):
            return fail(f"estate LOST without git surface: {item.get('id')}")
    if (doc.get("safety") or {}).get("deleted") or (
        doc.get("safety") or {}
    ).get("pruned") or (doc.get("safety") or {}).get("garbage_collected"):
        return fail("safety flags claim a destructive git action")
    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True or rev.get("verdict") != "PASS":
        return fail("reviewer independent PASS required")
    print("SUCCESS:WFA-0022-probe2 live byte-search both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
