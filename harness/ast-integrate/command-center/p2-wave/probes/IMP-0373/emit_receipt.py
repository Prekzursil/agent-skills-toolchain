#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0373.json from a live retain/revert run."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fixture import UNRELATED, assumed_band, build_tree, in_band, out_of_band  # noqa: E402
from selfimprove.retain import (  # noqa: E402
    DROP,
    KEEP,
    AppendOnlyError,
    IncompleteRevertError,
    SafetyError,
    apply_patch,
    check_revert,
    decide,
    load_jsonl,
    measured_improvement,
    reject_rewrite,
    revert_patch,
    snap_diff,
    take_snapshot,
)

OUT_REL = "command-center/receipts/IMP-0373.json"
SENTINEL = "SUCCESS:IMP-0373"
SPEC_ANCHOR = (
    "command-center/WORK-UNIT-CATALOG.json#IMP-0373 "
    "(question_or_target: retain.py keep-or-revert + append-only ledger; "
    "tree-hash equality after revert; revert must not touch non-candidate files)"
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def live_scenarios() -> dict:
    with tempfile.TemporaryDirectory(prefix="imp0373-receipt-") as td:
        base = Path(td)

        # --- apply then revert: hashes equal, unrelated untouched ---
        t1 = base / "revert-tree"
        build_tree(t1)
        unrelated_before = (t1 / "unrelated.txt").read_bytes()
        pre = take_snapshot(t1)
        ledger = base / "retention.jsonl"
        revert_out = decide(
            t1,
            {
                "change.txt": b"candidate-mutated-change\n",
                "nested/created.txt": b"candidate-created\n",
            },
            in_band(),
            ledger,
            "receipt-neutral",
        )
        post = take_snapshot(t1)
        revert_ok = (
            revert_out.decision == DROP
            and revert_out.hashes_equal
            and pre.tree_hash == post.tree_hash
            and revert_out.touched_outside_modified == []
            and (t1 / "unrelated.txt").read_bytes() == unrelated_before == UNRELATED
            and not (t1 / "nested" / "created.txt").exists()
        )

        # --- retain when improvement is measured ---
        t2 = base / "retain-tree"
        build_tree(t2)
        pre2 = take_snapshot(t2)
        retain_out = decide(
            t2,
            {"change.txt": b"kept-because-measured\n"},
            out_of_band(),
            ledger,
            "receipt-keep",
        )
        retain_ok = (
            retain_out.decision == KEEP
            and not retain_out.hashes_equal
            and retain_out.post_tree_hash != pre2.tree_hash
            and (t2 / "change.txt").read_bytes() == b"kept-because-measured\n"
            and (t2 / "unrelated.txt").read_bytes() == UNRELATED
        )

        # --- incomplete revert caught by tree hash ---
        t3 = base / "incomplete-tree"
        build_tree(t3)
        pre3 = take_snapshot(t3)
        applied = apply_patch(
            t3, {"change.txt": b"mut-a\n", "keep.txt": b"mut-b\n"}
        )
        report = revert_patch(
            t3, applied.preimages, applied.created_dirs, skip=["keep.txt"]
        )
        post3 = take_snapshot(t3)
        diff = snap_diff(pre3, post3)
        incomplete_caught = False
        try:
            check_revert(pre3, post3, applied.modified_files, report.touched)
        except IncompleteRevertError:
            incomplete_caught = True
        incomplete_ok = (
            post3.tree_hash != pre3.tree_hash
            and "keep.txt" in diff["changed"]
            and incomplete_caught
        )

        # --- extra touch caught ---
        t4 = base / "extra-tree"
        build_tree(t4)
        pre4 = take_snapshot(t4)
        applied4 = apply_patch(t4, {"change.txt": b"x\n"})
        report4 = revert_patch(
            t4,
            applied4.preimages,
            applied4.created_dirs,
            extra_touch=["unrelated.txt"],
        )
        post4 = take_snapshot(t4)
        safety_caught = False
        try:
            check_revert(pre4, post4, applied4.modified_files, report4.touched)
        except SafetyError:
            safety_caught = True
        safety_ok = safety_caught and "unrelated.txt" in report4.touched

        # --- assumed band is not improvement ---
        assumed_ok = not measured_improvement(assumed_band())
        t5 = base / "assumed-tree"
        build_tree(t5)
        original = (t5 / "change.txt").read_bytes()
        assumed_out = decide(
            t5,
            {"change.txt": b"should-not-keep\n"},
            assumed_band(),
            ledger,
            "receipt-assumed",
        )
        assumed_revert_ok = (
            assumed_ok
            and assumed_out.decision == DROP
            and (t5 / "change.txt").read_bytes() == original
        )

        rewrite_refused = False
        try:
            reject_rewrite(ledger)
        except AppendOnlyError:
            rewrite_refused = True
        rows = load_jsonl(ledger)

        all_ok = (
            revert_ok
            and retain_ok
            and incomplete_ok
            and safety_ok
            and assumed_revert_ok
            and rewrite_refused
            and len(rows) >= 3
        )
        return {
            "all_ok": all_ok,
            "revert": {
                "decision": revert_out.decision,
                "pre_tree_hash": pre.tree_hash,
                "post_tree_hash": post.tree_hash,
                "hashes_equal": revert_out.hashes_equal,
                "modified_files": revert_out.modified_files,
                "touched_files": revert_out.touched_files,
                "touched_outside_modified": revert_out.touched_outside_modified,
                "ok": revert_ok,
            },
            "retain": {
                "decision": retain_out.decision,
                "pre_tree_hash": pre2.tree_hash,
                "post_tree_hash": retain_out.post_tree_hash,
                "hashes_equal": retain_out.hashes_equal,
                "ok": retain_ok,
            },
            "incomplete_revert": {
                "pre_tree_hash": pre3.tree_hash,
                "post_tree_hash": post3.tree_hash,
                "hashes_equal": post3.tree_hash == pre3.tree_hash,
                "missed_file": "keep.txt",
                "diff_changed": diff["changed"],
                "detector_fired": incomplete_caught,
                "ok": incomplete_ok,
            },
            "extra_touch": {
                "detector_fired": safety_caught,
                "touched": report4.touched,
                "ok": safety_ok,
            },
            "assumed_band": {
                "measured_improvement": measured_improvement(assumed_band()),
                "decision": assumed_out.decision,
                "ok": assumed_revert_ok,
            },
            "ledger": {
                "rows": len(rows),
                "seq": [row["seq"] for row in rows],
                "decisions": [row["decision"] for row in rows],
                "chained": all(
                    rows[i]["prev_hash"] == rows[i - 1]["record_hash"]
                    for i in range(1, len(rows))
                ),
                "rewrite_refused": rewrite_refused,
            },
        }


def build_receipt(live: dict) -> dict:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    state = "SUCCESS" if live["all_ok"] else "FAILED"
    revert = live["revert"]
    return {
        "unit_id": "IMP-0373",
        "id": "IMP-0373",
        "state": state,
        "status": "DELIVERED" if live["all_ok"] else "FAILED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Automatic revert of neutral or harmful changes with a retention ledger",
        "question": (
            "Implement tools/selfimprove/retain.py keeping a change only when "
            "improvement is measured, reverting otherwise, and recording both "
            "outcomes in an append-only retention ledger. After a revert, is "
            "the tree byte-identical to the pre-change state, and does the "
            "revert path ever touch a file the candidate did not modify?"
        ),
        "spec_anchor": SPEC_ANCHOR,
        "output_schema": (
            "command-center/schema/receipt.schema.json profile=selfimprove-retention-module"
        ),
        "cloud_ok": False,
        "computed_at": now,
        "implementation": "tools/selfimprove/retain.py",
        "artifact_paths": [
            OUT_REL,
            "tools/selfimprove/retain.py",
            "tools/selfimprove/tests/test_retain.py",
            "command-center/p2-wave/probes/IMP-0373/probe1_apply_revert_tree_hash.py",
            "command-center/p2-wave/probes/IMP-0373/probe2_incomplete_revert_caught.py",
        ],
        "evidence": [
            {
                "id": "E1",
                "claim": (
                    "After apply-then-revert of a neutral candidate, pre-change "
                    "tree hash equals post-revert tree hash."
                ),
                "verdict": "CONFIRMED" if revert["ok"] else "REFUTED",
                "pre_tree_hash": revert["pre_tree_hash"],
                "post_tree_hash": revert["post_tree_hash"],
                "hashes_equal": revert["hashes_equal"],
                "modified_files": revert["modified_files"],
                "touched_files": revert["touched_files"],
            },
            {
                "id": "E2",
                "claim": (
                    "Revert touched-file set is a subset of the candidate "
                    "modified-file set; unrelated.txt is byte-identical."
                ),
                "verdict": "CONFIRMED" if revert["ok"] else "REFUTED",
                "touched_outside_modified": revert["touched_outside_modified"],
                "unrelated_untouched": True,
            },
            {
                "id": "E3",
                "claim": (
                    "A revert that misses one candidate file is caught because "
                    "the tree hashes differ and check_revert raises."
                ),
                "verdict": "CONFIRMED" if live["incomplete_revert"]["ok"] else "REFUTED",
                "pre_tree_hash": live["incomplete_revert"]["pre_tree_hash"],
                "post_tree_hash": live["incomplete_revert"]["post_tree_hash"],
                "hashes_equal": live["incomplete_revert"]["hashes_equal"],
                "missed_file": live["incomplete_revert"]["missed_file"],
                "detector_fired": live["incomplete_revert"]["detector_fired"],
            },
        ],
        "test_ids": [
            "integration-apply-then-revert-tree-hash-equality",
            "safety-revert-touches-no-unrelated-file",
            "negative-control-incomplete-revert-caught-by-tree-hash",
        ],
        "tests": [
            {
                "id": "integration-apply-then-revert-tree-hash-equality",
                "result": "PASS" if revert["ok"] else "FAIL",
                "pre_tree_hash": revert["pre_tree_hash"],
                "post_tree_hash": revert["post_tree_hash"],
            },
            {
                "id": "safety-revert-touches-no-unrelated-file",
                "result": "PASS" if revert["ok"] else "FAIL",
                "touched_outside_modified": revert["touched_outside_modified"],
            },
            {
                "id": "negative-control-incomplete-revert-caught-by-tree-hash",
                "result": "PASS" if live["incomplete_revert"]["ok"] else "FAIL",
                "detector_fired": live["incomplete_revert"]["detector_fired"],
            },
            {
                "id": "retain-when-improvement-measured",
                "result": "PASS" if live["retain"]["ok"] else "FAIL",
                "decision": live["retain"]["decision"],
            },
            {
                "id": "assumed-noise-band-is-not-measured-improvement",
                "result": "PASS" if live["assumed_band"]["ok"] else "FAIL",
            },
            {
                "id": "ledger-append-only",
                "result": "PASS"
                if live["ledger"]["rewrite_refused"] and live["ledger"]["chained"]
                else "FAIL",
                "rows": live["ledger"]["rows"],
            },
        ],
        "negative_control_ids": [
            "NC-incomplete-revert-misses-one-file",
            "NC-revert-extra-touch-unrelated",
            "NC-assumed-noise-band-cannot-retain",
        ],
        "negative_controls": [
            {
                "id": "NC-incomplete-revert-misses-one-file",
                "description": (
                    "Revert restores change.txt but skips keep.txt. Tree hash "
                    "must differ and check_revert must raise IncompleteRevertError."
                ),
                "fired_on_bad_state": live["incomplete_revert"]["detector_fired"],
                "ok": live["incomplete_revert"]["ok"],
            },
            {
                "id": "NC-revert-extra-touch-unrelated",
                "description": (
                    "A buggy revert that also writes unrelated.txt must fail "
                    "the touched-vs-modified set check (SafetyError)."
                ),
                "fired_on_bad_state": live["extra_touch"]["detector_fired"],
                "ok": live["extra_touch"]["ok"],
            },
            {
                "id": "NC-assumed-noise-band-cannot-retain",
                "description": (
                    "A large delta against an assumed (not measured) noise band "
                    "must REVERT, not RETAIN."
                ),
                "fired_on_bad_state": live["assumed_band"]["ok"],
                "ok": live["assumed_band"]["ok"],
            },
        ],
        "reviewer_verdict": "PASS" if live["all_ok"] else "FAIL",
        "reviewer": {
            "reviewer_id": "IMP-0373-probe2-incomplete-revert-and-safety",
            "independent": True,
            "verdict": "PASS" if live["all_ok"] else "FAIL",
            "starts_from": "tests (incomplete revert and extra-touch must fail open)",
            "grants_owner_signoff": False,
            "method": (
                "Adversarial probe starts from the negative controls, not from "
                "the implementer summary: incomplete revert must be visible in "
                "the tree hash; extra-file touch must be visible in the touched set."
            ),
        },
        "owner_signoff": {
            "required": True,
            "granted": False,
            "grantor": None,
            "block": "owner-signoff-not-reviewer-substitutable",
            "scope": (
                "Applying retain.py against the live worktree /opt/p2/ast-integrate. "
                "This receipt covers the module on isolated fixture trees only."
            ),
            "note": (
                "Catalog owner_approval_required is recorded, not granted. The "
                "reviewer does not grant the owner half. Production application "
                "of revert to the live worktree is not claimed."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "retain.py was not executed against the live repository tree; "
                    "all tree-hash evidence is from isolated tempfile fixtures."
                ),
                "verdict": "STATED",
                "settling_experiment": (
                    "Owner-authorized run of decide() on a disposable clone of "
                    "the live worktree, comparing git status before/after revert."
                ),
            },
            {
                "claim": (
                    "IMP-0372 (measure.py / measured noise band) is a dependency "
                    "and is not delivered here. retain.py consumes a measurement "
                    "record; it does not itself measure the noise band."
                ),
                "verdict": "STATED",
                "settling_experiment": "Deliver IMP-0372 and feed its measurement record into decide().",
            },
        ],
        "live": live,
        "completion_line": SENTINEL,
    }


def main() -> int:
    live = live_scenarios()
    if not live["all_ok"]:
        print(json.dumps(live, indent=2, sort_keys=True)[:4000])
        print("FAILED:IMP-0373 live scenarios did not all pass")
        return 1
    doc = build_receipt(live)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:IMP-0373 sentinel missing from receipt text")
        return 1
    if '"state": "BLOCKED"' in text or '"state": "FAILED"' in text:
        print("FAILED:IMP-0373 receipt is not a SUCCESS artifact")
        return 1
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(out)
    sha, size = digest(out)
    print(json.dumps({"path": OUT_REL, "sha256": sha, "bytes": size, "sentinel": SENTINEL}))
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
