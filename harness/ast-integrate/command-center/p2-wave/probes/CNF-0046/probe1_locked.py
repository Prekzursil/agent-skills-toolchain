#!/usr/bin/env python3
"""Named probe 1: locked-file hunt + silent-skip detector control.

Re-derives the locked-run verdict from a live client hold. Distinguishes
clean refusal (aware) from mixed-version silent skip (naive). Does not
read the artifact's conclusion field before checking live behaviour.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from lab import run_suite  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0046-locked-file-rollback.json"
SENTINEL = (
    "SUCCESS:CNF-0046 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both the locked and "
    "unlocked runs completed and the resulting version inventories are "
    "attached. Any other terminal state is FAILED:CNF-0046 <classification> "
    "with the diagnostic tail attached."
)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0046-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0046":
        print("FAILED:CNF-0046-probe1 unit_id", doc.get("unit_id"))
        return 1
    text = json.dumps(doc)
    if SENTINEL not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNF-0046-probe1 sentinel absent")
        return 1

    suite = run_suite()
    locked = suite["locked_aware"]
    naive = suite["naive_skip"]

    if not suite.get("pass"):
        print("FAILED:CNF-0046-probe1 live suite")
        print(json.dumps({
            "locked_exit": locked.get("exit_code"),
            "names": locked.get("names_locking_process"),
            "error_pid": locked.get("error_names_pid"),
            "all_v2": locked.get("all_v2"),
            "mixed": locked.get("mixed_version"),
            "naive_mixed": naive.get("mixed_version"),
        }, sort_keys=True))
        return 1

    if locked.get("exit_code") != 2:
        print("FAILED:CNF-0046-probe1 expected clean refusal exit 2")
        return 1
    if locked.get("wrote"):
        print("FAILED:CNF-0046-probe1 aware rollback wrote under lock")
        return 1
    if locked.get("mixed_version"):
        print("FAILED:CNF-0046-probe1 aware left mixed version")
        return 1
    if not locked.get("names_locking_process") or not locked.get("error_names_pid"):
        print("FAILED:CNF-0046-probe1 error did not name locker pid")
        return 1
    if not naive.get("mixed_version"):
        print("FAILED:CNF-0046-probe1 naive skip did not produce mixed version")
        return 1
    if naive.get("exit_code") != 0:
        print("FAILED:CNF-0046-probe1 naive skip was not silent (exit 0)")
        return 1

    inv = doc.get("inventories") or {}
    post_locked = {r["path"]: r for r in (inv.get("post_locked_aware") or {}).get("files") or []}
    post_naive = {r["path"]: r for r in (inv.get("post_naive_skip") or {}).get("files") or []}
    known = inv.get("known_hashes") or {}
    v2 = known.get("v2") or {}
    if not post_locked or not post_naive or not v2:
        print("FAILED:CNF-0046-probe1 artifact inventories missing")
        return 1
    for rel, sha in v2.items():
        row = post_locked.get(rel) or {}
        if row.get("sha256") != sha or row.get("version") != "v2":
            print(f"FAILED:CNF-0046-probe1 artifact post_locked_aware drift {rel}")
            return 1
    naive_versions = {r["path"]: r["version"] for r in (inv.get("post_naive_skip") or {}).get("files") or []}
    if not ("v1" in naive_versions.values() and "v2" in naive_versions.values()):
        print("FAILED:CNF-0046-probe1 artifact naive inventory is not mixed")
        return 1

    locked_run = doc.get("locked_run") or {}
    if locked_run.get("exit_code") != 2:
        print("FAILED:CNF-0046-probe1 artifact locked_run exit drift")
        return 1
    if str(doc.get("verdict") or {}).find("clean-refusal") < 0 and (
        (doc.get("verdict") or {}).get("classification") != "clean-refusal"
    ):
        print("FAILED:CNF-0046-probe1 artifact classification drift")
        return 1

    out = {
        "probe": "probe1-locked",
        "unit_id": "CNF-0046",
        "pass": True,
        "locked_exit": locked["exit_code"],
        "named_pid": locked["error_names_pid"],
        "aware_mixed": False,
        "naive_mixed": True,
        "handles": len(locked.get("handle_list") or []),
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"locked_exit={locked['exit_code']} named_pid={locked['error_names_pid']} "
        f"aware_all_v2={locked['all_v2']} naive_mixed={naive['mixed_version']}"
    )
    print("SUCCESS:CNF-0046-probe1 locked hunt and silent-skip detector")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
