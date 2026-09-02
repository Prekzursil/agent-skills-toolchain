#!/usr/bin/env python3
"""Named probe 2: independent tree digest vs the gate; keep-all mutant would fail.

Reviewer stance: do not trust retain.tree_hash or the decision field. Walk the
files with a different framing, compare pre vs post, and show that a keep-all
mutant of a neutral change would leave a hash mismatch the real gate does not.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))

from selfimprove.retain import (  # noqa: E402
    apply_files,
    restore_snapshot,
    retain,
    snapshot_paths,
)

ESTATE = TOOLS / "selfimprove" / "fixtures" / "retain-estate"
NEUTRAL = {
    "score.json": json.dumps({"value": 5, "agent": "produced this"}, indent=2) + "\n"
}
HARMFUL = {
    "score.json": json.dumps({"value": 1}, indent=2) + "\n",
    "extra.txt": "side-effect\n",
}
WIN = {"score.json": json.dumps({"value": 10}, indent=2) + "\n"}


def fail(msg: str) -> int:
    print(f"FAILED:TST-0236-probe2 {msg}")
    return 1


def independent_tree_digest(root: Path) -> str:
    """Length-prefixed walk; mechanically different from retain.tree_hash."""
    h = hashlib.sha256(b"independent-v1\n")
    files: list[Path] = [p for p in root.rglob("*") if p.is_file()]
    files.sort(key=lambda p: p.relative_to(root).as_posix().encode("utf-8"))
    for path in files:
        rel = path.relative_to(root).as_posix().encode("utf-8")
        raw = path.read_bytes().replace(b"\r\n", b"\n")
        h.update(len(rel).to_bytes(4, "big"))
        h.update(rel)
        h.update(len(raw).to_bytes(8, "big"))
        h.update(raw)
    return h.hexdigest()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0236-p2-") as raw:
        tmp = Path(raw)

        # --- keep-all mutant of a NEUTRAL change: independent hashes DIVERGE ---
        mutant = tmp / "keep-all"
        shutil.copytree(ESTATE, mutant)
        pre_mut = independent_tree_digest(mutant)
        apply_files(mutant, NEUTRAL)
        post_mut = independent_tree_digest(mutant)
        if pre_mut == post_mut:
            return fail("keep-all mutant of a rewrite did not move the independent digest")
        keep_all_would_fail_restore_check = pre_mut != post_mut

        # --- real gate: same NEUTRAL candidate; independent hashes MATCH ---
        real = tmp / "real-neutral"
        shutil.copytree(ESTATE, real)
        pre_real = independent_tree_digest(real)
        row = retain(
            tree=real,
            candidate_id="neutral-agent",
            files=NEUTRAL,
            produced_by="agent",
            program_root=REPO,
        )
        post_real = independent_tree_digest(real)
        if row.get("decision") != "REVERT":
            return fail(f"reviewer saw decision {row.get('decision')}, not REVERT")
        if pre_real != post_real:
            return fail("independent digest after real revert does not match pre-candidate")
        if row.get("hashes_equal") is not True:
            return fail("gate hashes_equal was not True after revert")
        # The two hashers need not agree on the hex; they must agree on equality.
        gate_equal = row["pre_tree_hash"] == row["post_decision_tree_hash"]
        independent_equal = pre_real == post_real
        if gate_equal != independent_equal:
            return fail("gate hash equality and independent equality disagree")

        # --- residue control: restoring only one of two harmful files leaves a mismatch ---
        residue = tmp / "residue"
        shutil.copytree(ESTATE, residue)
        pre_res = independent_tree_digest(residue)
        snap = snapshot_paths(residue, HARMFUL.keys())
        apply_files(residue, HARMFUL)
        restore_snapshot(residue, {"score.json": snap["score.json"]})
        post_res = independent_tree_digest(residue)
        if pre_res == post_res:
            return fail("incomplete restore was invisible to the independent digest")
        if not (residue / "extra.txt").is_file():
            return fail("residue extra.txt missing; control is not a residue")

        # Real harmful revert restores both files; independent hashes match.
        harm_tree = tmp / "real-harm"
        shutil.copytree(ESTATE, harm_tree)
        pre_harm = independent_tree_digest(harm_tree)
        harm = retain(
            tree=harm_tree,
            candidate_id="harm",
            files=HARMFUL,
            program_root=REPO,
        )
        post_harm = independent_tree_digest(harm_tree)
        if harm.get("decision") != "REVERT" or pre_harm != post_harm:
            return fail("real harmful revert failed the independent restore check")
        if (harm_tree / "extra.txt").exists():
            return fail("real revert left extra.txt")

        # Win: independent hashes MUST differ (the improvement is retained).
        win_tree = tmp / "real-win"
        shutil.copytree(ESTATE, win_tree)
        pre_win = independent_tree_digest(win_tree)
        win = retain(
            tree=win_tree,
            candidate_id="win",
            files=WIN,
            program_root=REPO,
        )
        post_win = independent_tree_digest(win_tree)
        if win.get("decision") != "KEEP" or pre_win == post_win:
            return fail("KEEP did not change the independent digest")

        payload = {
            "probe": "probe2-independent-rehash",
            "unit_id": "TST-0236",
            "keep_all_mutant_neutral_hashes_diverge": keep_all_would_fail_restore_check,
            "real_neutral_independent_hashes_match": pre_real == post_real,
            "incomplete_restore_detected": pre_res != post_res,
            "real_harmful_independent_hashes_match": pre_harm == post_harm,
            "real_win_independent_hashes_diverge": pre_win != post_win,
            "gate_vs_independent_equality_agrees": gate_equal == independent_equal,
            "reviewer_id": "TST-0236-probe2-independent-rehash",
            "verdict": "PASS",
            "pass": True,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        print(
            "keep_all_mutant_diverges=True real_neutral_restored=True "
            "incomplete_restore_detected=True"
        )
        print("SUCCESS:TST-0236-probe2 independent rehash; keep-all mutant would fail")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
