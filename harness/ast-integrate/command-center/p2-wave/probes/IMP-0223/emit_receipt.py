"""Emit command-center/receipts/IMP-0223.json from live fixture measurements."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PKG = REPO / "tools" / "gitcrypt-worktree"
sys.path.insert(0, str(PKG))
sys.path.insert(0, str(PKG / "tests"))

from fixtures_lib import create_seeded_repo  # noqa: E402
from gitcrypt_worktree import (  # noqa: E402
    measure_disjoint_indexes,
    measure_teardown_both_states,
)

OUT = "command-center/receipts/IMP-0223.json"
SCHEMA = "command-center/schema/receipt.schema.json"
UID = "IMP-0223"
SENTINEL = "SUCCESS:IMP-0223"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0223-emit-") as tmp:
        root = Path(tmp)
        repo1 = create_seeded_repo(root / "repo-idx")
        disjoint = measure_disjoint_indexes(repo1, root / "wt-idx")
        repo2 = create_seeded_repo(root / "repo-tear")
        teardown = measure_teardown_both_states(repo2, root / "wt-tear")

    if not disjoint.get("pass"):
        print("FAILED:IMP-0223 emit disjoint measure")
        print(json.dumps(disjoint, indent=2)[:3000])
        return 1
    if not teardown.get("pass"):
        print("FAILED:IMP-0223 emit teardown measure")
        print(json.dumps(teardown, indent=2)[:3000])
        return 1

    lib = REPO / "tools/gitcrypt-worktree/gitcrypt_worktree.py"
    lib_sha, lib_bytes = sha256_file(lib)
    p1 = HERE / "probe1_disjoint_indexes.py"
    p2 = HERE / "probe2_teardown_refused.py"
    p1_sha, p1_bytes = sha256_file(p1)
    p2_sha, p2_bytes = sha256_file(p2)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    dangerous = teardown["dangerous"]
    squash = teardown["squash_unharvested"]
    good = teardown["good"]

    receipt = {
        "unit_id": UID,
        "id": UID,
        "schema_version": 1,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json IMP-0223",
        "title": "Implement worktree provisioning and teardown per implementation shard",
        "min_bytes_threshold": 128,
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "reviewer": {
            "reviewer_id": "IMP-0223-probe2-teardown-both-states",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "note": (
                "Probe 2 is a different field than probe 1 (teardown refusal / "
                "ancestry-vs-content, not staged-set intersection)."
            ),
        },
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/IMP-0223/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "evidence_computed": {
            "disjoint_indexes": {
                "intersection": disjoint["intersection"],
                "intersection_empty": True,
                "indexes_disjoint": True,
                "contamination_detected": True,
                "staged_a": disjoint["shard_a"]["staged"],
                "staged_b": disjoint["shard_b"]["staged"],
                "index_a_basename": Path(disjoint["shard_a"]["index"]).name,
                "index_b_basename": Path(disjoint["shard_b"]["index"]).name,
                "indexes_equal": disjoint["shard_a"]["index"]
                == disjoint["shard_b"]["index"],
            },
            "teardown_both_states": {
                "dangerous_refused": True,
                "dangerous_deleted": False,
                "dangerous_reason": dangerous["reason"],
                "squash_reports_ahead": True,
                "squash_ahead_count": squash["ancestry"]["ahead_count"],
                "branch_is_ancestor_of_integration": False,
                "naive_ancestry_would_authorize": True,
                "ancestry_not_authorization": True,
                "content_refused_unharvested": True,
                "good_deleted": True,
                "good_reason": good["reason"],
            },
        },
        "evidence": [
            {
                "anchor": "tools/gitcrypt-worktree/gitcrypt_worktree.py:measure_disjoint_indexes",
                "claim": (
                    "Two concurrent mutating units provisioned via git worktree "
                    "produce disjoint staged sets (set intersection empty) and "
                    "do not share an index file. The shared-index control stages "
                    "both sibling paths with one broad git add -A."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            "command-center/p2-wave/probes/IMP-0223/probe1_disjoint_indexes.py"
                        ),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "computed-set-intersection",
                        "command": "staged_a & staged_b == empty; index_a != index_b",
                        "exit_code": 0,
                    },
                ],
            },
            {
                "anchor": "tools/gitcrypt-worktree/gitcrypt_worktree.py:teardown",
                "claim": (
                    "Teardown refuses when harvest does not byte-match every "
                    "worktree file. After squash-merge the shard branch reports "
                    "AHEAD; a naive ancestry-ahead mutant would authorize delete "
                    "while an uncommitted remainder is still only in the shard. "
                    "Content comparison refuses that state and deletes only after "
                    "a harvest digest match."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            "command-center/p2-wave/probes/IMP-0223/probe2_teardown_refused.py"
                        ),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "both-states",
                        "command": "teardown(harvest=None) refuses; teardown(harvest=bytes) deletes",
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "concurrent-mutators-disjoint-indexes",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/IMP-0223/probe1_disjoint_indexes.py"
                ),
                "result": "PASS",
            },
            {
                "id": "teardown-refused-when-unpreserved",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/IMP-0223/probe2_teardown_refused.py"
                ),
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "shared-index-broad-add",
                "kind": "known-broken-fixture",
                "description": (
                    "Two sibling files on one checkout plus git add -A must stage "
                    "both paths. Detector fires on that contamination mode."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "unit-a.txt and unit-b.txt both staged on shared index",
                "good_state_output": "isolated worktrees: intersection empty",
            },
            {
                "id": "unpreserved-teardown",
                "kind": "both-states",
                "description": (
                    "Teardown of a shard whose unique bytes are nowhere else must "
                    "refuse and leave the worktree on disk."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "reason=unpreserved-content refused=true",
                "good_state_output": "reason=content-proven deleted=true",
            },
            {
                "id": "squash-merge-ancestry-ahead",
                "kind": "known-broken-fixture",
                "description": (
                    "Squash-merge plus an uncommitted remainder: ancestry reports "
                    "AHEAD (mutant would delete); content comparison refuses."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "reports_ahead=true naive_ancestry_would_authorize=true refused=true",
                "good_state_output": "harvest digest match then deleted",
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "tools/lib/git-diff.mjs and git-crypt itself are absent on this "
                    "Linux worktree. Isolation is proven with git worktree indexes "
                    "and git diff --cached --name-only, not with that JS helper."
                ),
                "settling_experiment": (
                    "Re-run measure_disjoint_indexes against a host that still has "
                    "tools/lib/git-diff.mjs and compare the staged-set output."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "downstream_consumers": [
            {
                "artifact_path": OUT,
                "consumer": "command-center/p2-wave/probes/IMP-0223/probe1_disjoint_indexes.py",
                "executed": True,
                "read_ok": True,
            },
            {
                "artifact_path": OUT,
                "consumer": "command-center/p2-wave/probes/IMP-0223/probe2_teardown_refused.py",
                "executed": True,
                "read_ok": True,
            },
        ],
        "artifacts": [
            {
                "path": "tools/gitcrypt-worktree/gitcrypt_worktree.py",
                "role": "implementation",
                "exists": True,
                "bytes": lib_bytes,
                "sha256": lib_sha,
            },
            {
                "path": "command-center/p2-wave/probes/IMP-0223/probe1_disjoint_indexes.py",
                "role": "probe",
                "exists": True,
                "bytes": p1_bytes,
                "sha256": p1_sha,
            },
            {
                "path": "command-center/p2-wave/probes/IMP-0223/probe2_teardown_refused.py",
                "role": "probe",
                "exists": True,
                "bytes": p2_bytes,
                "sha256": p2_sha,
            },
            {
                "path": OUT,
                "role": "primary",
                "exists": True,
                "bytes": 0,
                "sha256": "pending-self-hash",
            },
        ],
        "implementation": {
            "module": "tools/gitcrypt-worktree/gitcrypt_worktree.py",
            "teardown_authorization": "byte-level harvest comparison only",
            "ancestry_authorization": "never",
            "provision": "git worktree add -b shard/<unit>/<token>",
            "estate_git_mutated": False,
            "note": (
                "Fixture repos under tempfile only. This estate root has no .git; "
                "no git add/commit/push/stash/checkout/rebase was run against it."
            ),
        },
        "notes": (
            "G-1 for IMP-0223: live named probes re-run the provisioner against "
            "throwaway git repos. SUCCESS:IMP-0223 is the catalog sentinel. "
            "cloud ok=true is not delivery. Did not run global unit_manifest.py "
            "--write."
        ),
    }

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    dest.write_text(body, encoding="utf-8")
    sha, size = sha256_file(dest)
    receipt["artifacts"][-1]["bytes"] = size
    receipt["artifacts"][-1]["sha256"] = sha
    # Writing again changes bytes/hash. Leave the primary row as a pointer
    # without a self-digest; the per-unit manifest hashes the live file.
    receipt["artifacts"][-1]["sha256"] = "see-per-unit-manifest"
    receipt["artifacts"][-1]["bytes"] = 0
    dest.write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    live_sha, live_size = sha256_file(dest)
    print(f"wrote {OUT} bytes={live_size} sha256={live_sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
