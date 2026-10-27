#!/usr/bin/env python3
"""TST-0236 probe 2: an INDEPENDENT digest agrees with the gate.

The verifier must not reuse retain.py tree hashing. This probe implements
a different algorithm - a length-prefixed walk (len(relpath) || relpath ||
len(data) || data over raw bytes, no CRLF normalisation) - and requires:
  * real revert restores: neutral and harmful reverts show independent
    pre == post, while KEEP diverges (agrees with the gate on all three);
  * a keep-all mutant of the same neutral rewrite diverges (would fail);
  * an incomplete restore that leaves extra.txt is visible to the
    independent digest (known-broken fixture detected).
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
sys.path.insert(0, str(REPO / "tools"))

from selfimprove import retain as retain_mod  # noqa: E402
from selfimprove.retain import take_snapshot  # noqa: E402

FIXTURE = REPO / "tools" / "selfimprove" / "fixtures" / "retain-estate"


def independent_digest(root: Path) -> str:
    """Length-prefixed walk; deliberately different from take_snapshot."""
    h = hashlib.sha256()
    for path in sorted(Path(root).rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix().encode("utf-8")
        data = path.read_bytes()
        h.update(len(rel).to_bytes(4, "big"))
        h.update(rel)
        h.update(len(data).to_bytes(8, "big"))
        h.update(data)
    return h.hexdigest()


def fresh_tree(tmp: Path) -> Path:
    tree = tmp / "subject"
    shutil.copytree(FIXTURE, tree, dirs_exist_ok=True)
    return tree


def main() -> int:
    checks: dict[str, bool] = {}
    with tempfile.TemporaryDirectory(prefix="tst0236-probe2-") as td:
        tmp = Path(td)
        ledger = tmp / "ledger.jsonl"

        neutral_pre = independent_digest(fresh_tree(tmp))
        neutral = retain_mod.retain(
            tree=tmp / "subject",
            candidate_id="p2-neutral",
            files={
                "score.json": json.dumps({"value": 5}),
                "notes.md": "agent rewrite; no measured change",
            },
            ledger_path=ledger,
            produced_by="agent",
        )
        checks["real_neutral_independent_hashes_match"] = (
            neutral["decision"] == "REVERT"
            and independent_digest(tmp / "subject") == neutral_pre
        )

        harmful_pre = independent_digest(fresh_tree(tmp))
        harmful = retain_mod.retain(
            tree=tmp / "subject",
            candidate_id="p2-harmful",
            files={"score.json": json.dumps({"value": 1}), "extra.txt": "stray"},
            ledger_path=ledger,
        )
        checks["real_harmful_independent_hashes_match"] = (
            harmful["decision"] == "REVERT"
            and independent_digest(tmp / "subject") == harmful_pre
        )

        win_pre = independent_digest(fresh_tree(tmp))
        win = retain_mod.retain(
            tree=tmp / "subject",
            candidate_id="p2-win",
            files={"score.json": json.dumps({"value": 10})},
            ledger_path=ledger,
        )
        checks["real_win_independent_hashes_diverge"] = (
            win["decision"] == "KEEP"
            and independent_digest(tmp / "subject") != win_pre
        )
        checks["gate_vs_independent_equality_agrees"] = (
            (win["hashes_equal"] is False)
            == (independent_digest(tmp / "subject") != win_pre)
        )

        # keep-all mutant: the same neutral rewrite applied and KEPT.
        tree = fresh_tree(tmp)
        mutant_pre = independent_digest(tree)
        retain_mod.apply_files(
            tree,
            {
                "score.json": json.dumps({"value": 5}),
                "notes.md": "agent rewrite; no measured change",
            },
        )
        checks["keep_all_mutant_neutral_hashes_diverge"] = (
            independent_digest(tree) != mutant_pre
        )

        # incomplete restore: restore score.json but leave extra.txt behind.
        tree = fresh_tree(tmp)
        snapshot_before = take_snapshot(tree)
        inc_pre = independent_digest(tree)
        originals = {
            p.relative_to(tree).as_posix(): p.read_bytes()
            for p in tree.rglob("*")
            if p.is_file()
        }
        (tree / "score.json").write_text(json.dumps({"value": 1}), encoding="utf-8")
        (tree / "extra.txt").write_text("stray", encoding="utf-8")
        (tree / "score.json").write_bytes(originals["score.json"])
        checks["incomplete_restore_detected"] = independent_digest(tree) != inc_pre

        # the real gate must also catch the incomplete restore.
        try:
            retain_mod.check_revert(tree, snapshot_before)
            checks["gate_rejects_incomplete_restore"] = False
        except retain_mod.IncompleteRevertError:
            checks["gate_rejects_incomplete_restore"] = True

    ok = all(checks.values())
    out = {
        "probe": "probe2-independent-rehash",
        "unit_id": "TST-0236",
        "checks": checks,
        "pass": ok,
        "verdict": "PASS" if ok else "FAIL",
        "reviewer_id": "TST-0236-probe2-independent-rehash",
    }
    (HERE / "probe2_independent_rehash.raw.txt").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    print(
        "keep_all_mutant_diverges={} real_neutral_restored={} incomplete_restore_detected={}".format(
            checks["keep_all_mutant_neutral_hashes_diverge"],
            checks["real_neutral_independent_hashes_match"],
            checks["incomplete_restore_detected"],
        )
    )
    if ok:
        print("SUCCESS:TST-0236-probe2 independent rehash; keep-all mutant would fail")
    else:
        print("FAILED:TST-0236-probe2 independent rehash checks failed")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
