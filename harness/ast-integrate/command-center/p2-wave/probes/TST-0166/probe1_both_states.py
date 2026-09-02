#!/usr/bin/env python3
"""Probe 1: both-states control for pinned-SHA resume.

Unchanged HEAD resumes without a prompt and continues work.
Moved HEAD without an explicit choice raises, names both SHAs, summarises
files, and does not continue. Independent ``git diff --name-only`` must
match the gate listing.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))
sys.path.insert(0, str(HERE))

import fixtures as F  # noqa: E402
import resume_sha_gate as G  # noqa: E402

UID = "TST-0166"


def fail(msg: str) -> int:
    print(f"FAILED:{UID}-probe1 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0166-p1-") as tmp:
        tmp_path = Path(tmp)

        match_repo = F.init_repo(tmp_path / "match")
        pinned_match = G.head_sha(match_repo)
        ck_match = tmp_path / "match.json"
        G.dump_checkpoint(ck_match, pinned_match, extra={"unit_id": UID})
        match_continued = {"n": 0}

        def on_match() -> None:
            match_continued["n"] += 1

        match_out = G.resume(ck_match, match_repo, on_continue=on_match)
        match_indep = F.independent_diff_name_only(
            match_repo, pinned_match, match_out["head_sha"]
        )

        moved_repo = F.init_repo(tmp_path / "moved")
        pinned_moved = G.head_sha(moved_repo)
        G.dump_checkpoint(
            tmp_path / "moved.json",
            pinned_moved,
            extra={"unit_id": UID},
        )
        head_moved = F.move_head(moved_repo)
        if head_moved == pinned_moved:
            return fail("fixture HEAD did not move")
        moved_continued = {"n": 0}

        def on_moved() -> None:
            moved_continued["n"] += 1

        mismatch_record = None
        raised = False
        try:
            G.resume(
                tmp_path / "moved.json",
                moved_repo,
                on_continue=on_moved,
            )
        except G.ShaMismatchDecisionRequired as exc:
            raised = True
            mismatch_record = exc.record

        if mismatch_record is None:
            return fail("moved HEAD did not raise ShaMismatchDecisionRequired")

        indep_files = F.independent_diff_name_only(
            moved_repo, pinned_moved, head_moved
        )
        gate_files = list(mismatch_record.get("files_changed") or [])

        explicit_continued = {"n": 0}

        def on_explicit() -> None:
            explicit_continued["n"] += 1

        accepted = G.resume(
            tmp_path / "moved.json",
            moved_repo,
            choice=G.CHOICE_ACCEPT_NEW_HEAD,
            on_continue=on_explicit,
        )

        payload = {
            "probe": "probe1-both-states",
            "unit_id": UID,
            "pass": False,
            "unchanged_head": {
                "status": match_out.get("status"),
                "prompt": match_out.get("prompt"),
                "work_continued": match_out.get("work_continued"),
                "continue_calls": match_continued["n"],
                "pinned_sha": match_out.get("pinned_sha"),
                "head_sha": match_out.get("head_sha"),
                "independent_diff": match_indep,
            },
            "moved_head_no_choice": {
                "raised": raised,
                "work_continued": bool(mismatch_record.get("work_continued")),
                "continue_calls": moved_continued["n"],
                "pinned_sha": mismatch_record.get("pinned_sha"),
                "head_sha": mismatch_record.get("head_sha"),
                "prompt": mismatch_record.get("prompt"),
                "files_changed": gate_files,
                "independent_diff": indep_files,
            },
            "explicit_accept": {
                "status": accepted.get("status"),
                "choice": accepted.get("choice"),
                "work_continued": accepted.get("work_continued"),
                "continue_calls": explicit_continued["n"],
                "pinned_sha": accepted.get("pinned_sha"),
                "head_sha": accepted.get("head_sha"),
            },
        }
        both_named = (
            pinned_moved in str(mismatch_record.get("prompt") or "")
            and head_moved in str(mismatch_record.get("prompt") or "")
            and mismatch_record.get("pinned_sha") == pinned_moved
            and mismatch_record.get("head_sha") == head_moved
        )
        listing_agrees = gate_files == indep_files and set(indep_files) == {
            "alpha.txt",
            "beta.txt",
        }
        match_ok = (
            match_out.get("status") == G.RESUME_OK
            and match_out.get("prompt") is None
            and match_out.get("work_continued") is True
            and match_continued["n"] == 1
            and match_indep == []
            and match_out.get("pinned_sha") == match_out.get("head_sha")
        )
        mismatch_ok = (
            raised
            and moved_continued["n"] == 0
            and mismatch_record.get("work_continued") is False
            and both_named
            and listing_agrees
        )
        explicit_ok = (
            accepted.get("status") == G.HEAD_ACCEPTED
            and accepted.get("choice") == G.CHOICE_ACCEPT_NEW_HEAD
            and explicit_continued["n"] == 1
            and accepted.get("pinned_sha") == pinned_moved
            and accepted.get("head_sha") == head_moved
        )
        payload["pass"] = bool(match_ok and mismatch_ok and explicit_ok)
        print(json.dumps(payload, indent=1, sort_keys=True))

        if not match_ok:
            return fail("unchanged HEAD did not resume without a prompt")
        if not mismatch_ok:
            return fail("moved HEAD did not require a named SHA decision")
        if not listing_agrees:
            return fail(
                f"gate files {gate_files} != independent {indep_files}"
            )
        if not explicit_ok:
            return fail("explicit accept_new_head did not continue after the record")
        print(
            "SUCCESS:TST-0166-probe1 both-states: unchanged HEAD silent resume; "
            "mismatch names both SHAs and independent git diff --name-only"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
