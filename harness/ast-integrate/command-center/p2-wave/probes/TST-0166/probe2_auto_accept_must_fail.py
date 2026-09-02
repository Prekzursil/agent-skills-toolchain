#!/usr/bin/env python3
"""Probe 2: negative control — auto-accepting a moved HEAD must fail.

Production refuse: mismatch with no choice does not continue work.
AutoAcceptResume mutant: the same call continues (dead if it also refuses).
Abort / stay_pinned also refuse to continue. Detector must discriminate.
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
    print(f"FAILED:{UID}-probe2 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0166-p2-") as tmp:
        tmp_path = Path(tmp)
        repo = F.init_repo(tmp_path / "repo")
        pinned = G.head_sha(repo)
        ck = tmp_path / "ckpt.json"
        G.dump_checkpoint(ck, pinned, extra={"unit_id": UID, "role": "negative"})
        head = F.move_head(repo)
        indep = F.independent_diff_name_only(repo, pinned, head)

        prod_calls = {"n": 0}

        def on_prod() -> None:
            prod_calls["n"] += 1

        prod_raised = False
        prod_record = None
        try:
            G.resume(ck, repo, on_continue=on_prod)
        except G.ShaMismatchDecisionRequired as exc:
            prod_raised = True
            prod_record = exc.record

        mutant_calls = {"n": 0}

        def on_mut() -> None:
            mutant_calls["n"] += 1

        mutant_out = G.AutoAcceptResume.resume(ck, repo, on_continue=on_mut)

        abort_calls = {"n": 0}
        abort_out = G.resume(
            ck, repo, choice=G.CHOICE_ABORT, on_continue=lambda: abort_calls.__setitem__("n", abort_calls["n"] + 1)
        )
        stay_calls = {"n": 0}
        stay_out = G.resume(
            ck,
            repo,
            choice=G.CHOICE_STAY_PINNED,
            on_continue=lambda: stay_calls.__setitem__("n", stay_calls["n"] + 1),
        )

        prod_refused = (
            prod_raised
            and prod_record is not None
            and prod_calls["n"] == 0
            and prod_record.get("work_continued") is False
            and prod_record.get("auto_accepted") is False
            and pinned in str(prod_record.get("prompt") or "")
            and head in str(prod_record.get("prompt") or "")
            and list(prod_record.get("files_changed") or []) == indep
        )
        mutant_auto_accepted = (
            mutant_out.get("auto_accepted") is True
            and mutant_out.get("work_continued") is True
            and mutant_calls["n"] == 1
            and mutant_out.get("prompt") is None
        )
        abort_ok = abort_out.get("status") == G.ABORTED and abort_calls["n"] == 0
        stay_ok = stay_out.get("status") == G.STAY_PINNED and stay_calls["n"] == 0
        detector_discriminates = prod_refused and mutant_auto_accepted

        payload = {
            "probe": "probe2-auto-accept-must-fail",
            "unit_id": UID,
            "pass": False,
            "reviewer_id": "TST-0166-probe2-auto-accept-must-fail",
            "independent": True,
            "pinned_sha": pinned,
            "head_sha": head,
            "independent_diff": indep,
            "production": {
                "raised": prod_raised,
                "continue_calls": prod_calls["n"],
                "work_continued": (prod_record or {}).get("work_continued"),
                "prompt_names_both_shas": bool(
                    prod_record
                    and pinned in str(prod_record.get("prompt") or "")
                    and head in str(prod_record.get("prompt") or "")
                ),
            },
            "mutant": {
                "auto_accepted": mutant_out.get("auto_accepted"),
                "work_continued": mutant_out.get("work_continued"),
                "continue_calls": mutant_calls["n"],
                "prompt": mutant_out.get("prompt"),
            },
            "abort_does_not_continue": abort_ok,
            "stay_pinned_does_not_continue": stay_ok,
            "detector_discriminates": detector_discriminates,
        }
        payload["pass"] = bool(
            detector_discriminates and abort_ok and stay_ok and indep
        )
        print(json.dumps(payload, indent=1, sort_keys=True))

        if not prod_refused:
            return fail("production auto-accepted or omitted the SHA decision")
        if not mutant_auto_accepted:
            return fail("mutant did not auto-accept (dead negative control)")
        if not abort_ok or not stay_ok:
            return fail("abort/stay_pinned continued work")
        if not indep:
            return fail("independent git diff --name-only was empty after HEAD move")
        print(
            "SUCCESS:TST-0166-probe2 negative control: auto-accept mutant continues; "
            "production refuses until an explicit choice"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
