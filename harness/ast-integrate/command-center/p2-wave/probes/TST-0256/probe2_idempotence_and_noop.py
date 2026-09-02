#!/usr/bin/env python3
"""Probe 2: second-run idempotence, already-migrated no-op, mutant detector.

Signal (b): byte-identical tree hash after a second documented apply.
Both-states: an already-migrated tree is a no-op. A stamp-on-every-file
mutant must change the hash so the detector is red-capable.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import capture as C  # noqa: E402
import harness as H  # noqa: E402

UID = "TST-0256"


def mutate_stamp(tree: Path) -> None:
    for path in H.walk_files(tree):
        data = path.read_bytes()
        if not data.endswith(b"\n"):
            data += b"\n"
        path.write_bytes(data + b"# TST-0256-MUTANT-STAMP\n")


def hash_via_doc(tree: Path) -> tuple[int, str, str]:
    rc, out = H.run_documented(H.HASH_CMD, tree)
    if rc != 0:
        return rc, "", out
    doc = H.last_json_object(out)
    return rc, str(doc.get("tree_hash") or ""), out


def main() -> int:
    if not (H.REPO / H.PROVENANCE_REL).is_file():
        rc = C.main()
        if rc != 0:
            return rc

    guide = H.GUIDE.read_text(encoding="utf-8")
    apply_cmd = H.documented_apply_command(guide)

    with H.work_copy() as tmp:
        tmp_path = Path(tmp)
        tree = tmp_path / "twice"
        H.copy_tree(H.CAPTURED, tree)
        rc1, out1 = H.run_documented(apply_cmd, tree)
        if rc1 != 0:
            print(json.dumps({"probe": "probe2", "pass": False, "first_rc": rc1, "out": out1[-1200:]}, sort_keys=True))
            print("FAILED:TST-0256-probe2 first apply")
            return 1
        first = H.last_json_object(out1)
        h1_rc, hash1, _ = hash_via_doc(tree)
        census1 = H.census(tree)
        rc2, out2 = H.run_documented(apply_cmd, tree)
        if rc2 != 0:
            print(json.dumps({"probe": "probe2", "pass": False, "second_rc": rc2, "out": out2[-1200:]}, sort_keys=True))
            print("FAILED:TST-0256-probe2 second apply")
            return 1
        second = H.last_json_object(out2)
        h2_rc, hash2, _ = hash_via_doc(tree)
        census2 = H.census(tree)
        idempotent = (
            h1_rc == 0
            and h2_rc == 0
            and hash1 == hash2
            and hash1 == first.get("tree_hash") == second.get("tree_hash")
            and H.tree_diff(census1, census2) == []
            and second.get("action") == "noop"
        )

        already = tmp_path / "already"
        H.copy_tree(tree, already)
        pre_hash = hash2
        rc_n, out_n = H.run_documented(apply_cmd, already)
        third = H.last_json_object(out_n) if rc_n == 0 else {}
        _, post_hash, _ = hash_via_doc(already)
        already_noop = (
            rc_n == 0
            and third.get("action") == "noop"
            and post_hash == pre_hash
            and H.tree_diff(H.census(already), census2) == []
        )

        mutant = tmp_path / "mutant"
        H.copy_tree(tree, mutant)
        before_mut = H.tree_hash_from_census(H.census(mutant))
        mutate_stamp(mutant)
        mut_hash = H.tree_hash_from_census(H.census(mutant))
        mutant_fired = mut_hash != hash2 and mut_hash != before_mut

    payload = {
        "probe": "probe2-idempotence-and-noop",
        "unit_id": UID,
        "pass": bool(idempotent and already_noop and mutant_fired),
        "documented_command": apply_cmd,
        "first_action": first.get("action"),
        "second_action": second.get("action"),
        "hash_run1": hash1,
        "hash_run2": hash2,
        "hashes_identical": hash1 == hash2,
        "second_run_noop": second.get("action") == "noop",
        "already_migrated_action": third.get("action"),
        "already_migrated_hash_unchanged": post_hash == pre_hash,
        "mutant_stamp_changes_hash": mutant_fired,
        "mutant_hash": mut_hash,
        "file_count": len(census1),
    }
    print(json.dumps(payload, sort_keys=True))
    if not idempotent:
        print("FAILED:TST-0256-probe2 second run changed the tree")
        return 1
    if not already_noop:
        print("FAILED:TST-0256-probe2 already-migrated tree was not a no-op")
        return 1
    if not mutant_fired:
        print("FAILED:TST-0256-probe2 mutant stamp did not change the hash")
        return 1
    print(
        "SUCCESS:TST-0256-probe2 second-run hash identical "
        f"{hash1[:12]} already-migrated=noop mutant-fired"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
