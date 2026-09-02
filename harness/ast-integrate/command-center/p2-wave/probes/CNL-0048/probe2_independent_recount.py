#!/usr/bin/env python3
"""Named probe 2: independent recount + non-answer negative control.

Signal 2 is set-algebra (created minus discharged minus cut) using hop-depth
from the parent walk, not the status labels synthesize() writes. Disagreement
with probe 1's labels is a detector failure, not a picked winner.

Re-runs both-states here so the reviewer signature is not a copy of probe 1.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

ART = REPO / "command-center/design/council/CNL-0048-response-obligations-and-rebuttal-depth.md"
FIX = HERE / "fixtures"
ENGINE = HERE / "engine.py"


def load_fix(name: str) -> dict:
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNL-0048-probe2 artifact missing")
        return 1
    art = json.loads(ART.read_text(encoding="utf-8"))
    if art.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNL-0048-probe2 self-declared", art.get("state"))
        return 1
    if "SUCCESS:CNL-0048" not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNL-0048-probe2 sentinel absent")
        return 1

    src = ENGINE.read_text(encoding="utf-8")
    for marker in (
        "NAMED_ADDRESSEE_REQUIRED",
        "IGNORED_SURVIVES_SYNTHESIS",
        "DEPTH_HARD_STOP_NOT_CONSENSUS",
        "NON_ANSWER_DOES_NOT_DISCHARGE",
    ):
        if marker not in src:
            print(f"FAILED:CNL-0048-probe2 missing marker {marker}")
            return 1

    names = ("known_good", "ignored_argument", "non_answer", "depth_cut")
    rows = {}
    for name in names:
        doc = load_fix(name)
        labeled = E.apply_turns(doc["turns"], int(doc["rebuttal_depth_budget"]))
        recount = E.independent_recount(doc["turns"], int(doc["rebuttal_depth_budget"]))
        lab_set = set(labeled["ignored_ids"])
        rec_set = set(recount["ignored"])
        print(
            f"{name} labeled_ignored={sorted(lab_set)} "
            f"recount_ignored={sorted(rec_set)} "
            f"labeled_fires={labeled['unanswered_fires']} "
            f"recount_fires={recount['unanswered_fires']}"
        )
        if lab_set != rec_set:
            print(f"FAILED:CNL-0048-probe2 signal disagreement on {name}")
            return 1
        if labeled["unanswered_fires"] != recount["unanswered_fires"]:
            print(f"FAILED:CNL-0048-probe2 fire disagreement on {name}")
            return 1
        rows[name] = {"labeled": labeled, "recount": recount}

    if rows["known_good"]["recount"]["unanswered_fires"]:
        print("FAILED:CNL-0048-probe2 known-good recount was not SILENT")
        return 1
    if not rows["ignored_argument"]["recount"]["unanswered_fires"]:
        print("FAILED:CNL-0048-probe2 ignored-argument recount did not FIRE")
        return 1
    if not rows["non_answer"]["recount"]["unanswered_fires"]:
        print("FAILED:CNL-0048-probe2 non-answer was treated as discharge")
        return 1
    if rows["depth_cut"]["recount"]["unanswered_fires"]:
        print("FAILED:CNL-0048-probe2 depth-cut recount treated CUT as IGNORED")
        return 1

    non_line = E.verbatim_check("non_answer", rows["non_answer"]["labeled"])
    print(non_line)
    print(
        "negative_control_verbatim the unanswered check FIRES when seat-B "
        "posts a topic_change instead of a rebuttal/concession/explicit_pass; "
        "kind=topic_change is not a discharge"
    )
    print(
        "reviewer_both_states fired_on_bad=True silent_on_good=True "
        "mechanism=set-algebra-parent-walk"
    )

    # Evidence anchors in the artifact must resolve on this tree.
    evid = art.get("evidence") or []
    file_line = [e for e in evid if (e.get("signal") or {}).get("kind") == "file_line"]
    cmd_out = [e for e in evid if (e.get("signal") or {}).get("kind") == "command_output"]
    if len(file_line) < 1 or len(cmd_out) < 1:
        print("FAILED:CNL-0048-probe2 need both file_line and command_output evidence")
        return 1
    for e in file_line:
        anchor = str((e.get("signal") or {}).get("anchor") or "")
        if ":" not in anchor:
            print("FAILED:CNL-0048-probe2 file_line missing path:line", anchor)
            return 1
        path_s, line_s = anchor.rsplit(":", 1)
        path = REPO / path_s
        if not path.is_file():
            print("FAILED:CNL-0048-probe2 missing evidence file", path_s)
            return 1
        try:
            line_no = int(line_s)
        except ValueError:
            print("FAILED:CNL-0048-probe2 bad line", line_s)
            return 1
        lines = path.read_text(encoding="utf-8").splitlines()
        if line_no < 1 or line_no > len(lines):
            print("FAILED:CNL-0048-probe2 line out of range", anchor)
            return 1
        snippet = lines[line_no - 1]
        print(f"anchor ok={anchor} snippet={snippet.strip()[:80]}")

    print("SUCCESS:CNL-0048-probe2 independent recount non-answer reviewer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
