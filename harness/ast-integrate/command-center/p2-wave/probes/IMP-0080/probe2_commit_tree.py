#!/usr/bin/env python3
"""Named probe 2 (IMP-0080): independent git resolve of commit + tree match.

This does not call ProvenanceStore.verify_against_artifact. It runs git
cat-file/rev-parse itself, which is the catalog reviewer requirement: resolve
one commit sha independently and confirm the tree matches.

Also the negative control: a provenance record pointing at a non-existent
commit is rejected at publish time. And query of every published version is
PRESENT or explicit NONE — never {}.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3] / "tools" / "marketplace"))
sys.path.insert(0, str(HERE))

import provenance_store as ps  # noqa: E402
from scenario import NONE_VERSION, PACKAGE, VERSION, planted  # noqa: E402


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


def main() -> int:
    with planted() as world:
        return _run(world)


def _run(world) -> int:
    rec = ps.interpret_query(world.store.query(PACKAGE, VERSION)).record
    if rec is None:
        print("FAILED:IMP-0080-probe2 missing PRESENT record")
        return 1
    commit = rec["commit_sha"]
    kind = git(world.source, "cat-file", "-t", commit)
    if kind.returncode != 0 or kind.stdout.strip() != "commit":
        print(f"FAILED:IMP-0080-probe2 commit does not resolve: {kind.stderr}")
        return 1
    tree_p = git(world.source, "rev-parse", "--verify", f"{commit}^{{tree}}")
    if tree_p.returncode != 0:
        print(f"FAILED:IMP-0080-probe2 tree does not resolve: {tree_p.stderr}")
        return 1
    resolved_tree = tree_p.stdout.strip().lower()
    if resolved_tree != rec["tree_hash"]:
        print(
            f"FAILED:IMP-0080-probe2 tree mismatch stored={rec['tree_hash']} "
            f"resolved={resolved_tree}"
        )
        return 1
    if resolved_tree != world.tree:
        print("FAILED:IMP-0080-probe2 resolved tree != planted tree")
        return 1

    fake = "cccccccccccccccccccccccccccccccccccccccc"
    bad = ps.make_attestation(
        package=PACKAGE,
        version="9.9.9-missing-commit",
        artifact_digest=world.digest,
        source_repo="git+https://example.invalid/org/agent-skills-toolchain.git",
        commit_sha=fake,
        tree_hash="dddddddddddddddddddddddddddddddddddddddd",
    )
    rejected = False
    try:
        world.store.publish(
            package=PACKAGE,
            version="9.9.9-missing-commit",
            artifact=world.artifact,
            attestation=bad,
            source_repo=world.source,
        )
    except ps.UnresolvedCommitError:
        rejected = True
    if not rejected:
        print("FAILED:IMP-0080-probe2 missing commit was accepted at publish")
        return 1

    rows = []
    for payload in world.store.query_all_published():
        parsed = ps.interpret_query(payload)
        if parsed.status not in {"PRESENT", "NONE"}:
            print(f"FAILED:IMP-0080-probe2 published query status={parsed.status}")
            return 1
        rows.append({"package": parsed.package, "version": parsed.version, "status": parsed.status})
    statuses = {r["version"]: r["status"] for r in rows}
    if statuses.get(VERSION) != "PRESENT" or statuses.get(NONE_VERSION) != "NONE":
        print(f"FAILED:IMP-0080-probe2 published map {statuses}")
        return 1
    try:
        ps.interpret_query({})
        print("FAILED:IMP-0080-probe2 empty object accepted as query success")
        return 1
    except ps.EmptyQuerySuccess:
        pass
    try:
        ps.interpret_query({"ok": True})
        print("FAILED:IMP-0080-probe2 ok=true empty success accepted")
        return 1
    except ps.EmptyQuerySuccess:
        pass

    out = {
        "probe": "probe2-commit-tree",
        "unit_id": "IMP-0080",
        "commit_sha": commit,
        "resolved_object_type": "commit",
        "resolved_tree": resolved_tree,
        "stored_tree": rec["tree_hash"],
        "trees_match": True,
        "missing_commit_rejected": True,
        "published_query_statuses": statuses,
        "empty_success_rejected": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:IMP-0080-probe2 independent commit resolve and tree match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
