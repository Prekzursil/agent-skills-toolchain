#!/usr/bin/env python3
"""Consumer verification command for REL-0012 provenance.

Exit 0 only when:
  * the artifact sha256 matches the in-toto subject digest
  * git rev-parse HEAD in the recorded build tree equals the provenance gitCommit
  * the shipped release notes (sidecar and zip entry) carry an UNSIGNED declaration

A one-byte flip of the artifact must fail. This command never creates, uses, or
rotates a signing key.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import BUILDER_ID, PREDICATE_TYPE, STATEMENT_TYPE  # noqa: E402
from engine import find_unsigned, sha256_file, unsigned_in_zip  # noqa: E402


def git_head(tree: Path) -> tuple[str, str]:
    try:
        p = subprocess.run(
            ["git", "-C", str(tree), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        p = None
    if p is not None and p.returncode == 0:
        return p.stdout.strip(), "git-rev-parse"
    head = (tree / ".git" / "HEAD").read_text(encoding="utf-8").strip()
    if head.startswith("ref:"):
        ref = head.split(":", 1)[1].strip()
        commit = (tree / ".git" / ref).read_text(encoding="utf-8").strip()
        return commit, "git-HEAD-file-fallback"
    return head, "git-HEAD-file-fallback"


def fail(reason: str, extra: dict | None = None) -> int:
    payload = {"ok": False, "reason": reason}
    if extra:
        payload.update(extra)
    print(json.dumps(payload, sort_keys=True))
    print(f"FAILED:REL-0012-verify {reason}")
    return 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Verify REL-0012 unsigned provenance")
    ap.add_argument("--artifact", required=True)
    ap.add_argument("--provenance", required=True)
    ap.add_argument("--build-tree", required=True)
    ap.add_argument("--release-notes", required=True)
    args = ap.parse_args(argv)

    artifact = Path(args.artifact)
    prov_path = Path(args.provenance)
    tree = Path(args.build_tree)
    notes = Path(args.release_notes)
    if not artifact.is_file() or artifact.stat().st_size <= 0:
        return fail("artifact-absent")
    if not prov_path.is_file():
        return fail("provenance-absent")
    if not tree.is_dir():
        return fail("build-tree-absent")
    if not notes.is_file():
        return fail("release-notes-absent")

    try:
        stmt = json.loads(prov_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return fail(f"provenance-unparseable:{exc}")

    if stmt.get("_type") != STATEMENT_TYPE:
        return fail("statement-type-mismatch", {"got": stmt.get("_type")})
    if stmt.get("predicateType") != PREDICATE_TYPE:
        return fail("predicate-type-mismatch", {"got": stmt.get("predicateType")})

    subjects = stmt.get("subject") or []
    if not isinstance(subjects, list) or not subjects:
        return fail("subject-absent")
    want = ((subjects[0] or {}).get("digest") or {}).get("sha256")
    if not isinstance(want, str) or len(want) != 64:
        return fail("subject-digest-malformed")
    got = sha256_file(artifact)
    if got != want:
        return fail(
            "DIGEST-MISMATCH",
            {"want": want, "got": got, "artifact": str(artifact)},
        )

    pred = stmt.get("predicate") or {}
    deps = ((pred.get("buildDefinition") or {}).get("resolvedDependencies")) or []
    git_commit = None
    for dep in deps:
        digest = (dep or {}).get("digest") or {}
        if "gitCommit" in digest:
            git_commit = digest["gitCommit"]
            break
    if not git_commit:
        return fail("provenance-gitCommit-absent")

    live, how = git_head(tree)
    if live != git_commit:
        return fail(
            "COMMIT-MISMATCH",
            {"provenance": git_commit, "git": live, "via": how},
        )

    builder = ((pred.get("runDetails") or {}).get("builder") or {}).get("id")
    if builder != BUILDER_ID:
        return fail("builder-mismatch", {"got": builder, "want": BUILDER_ID})

    try:
        notes_u = find_unsigned(notes)
        zip_u = unsigned_in_zip(artifact)
    except RuntimeError as exc:
        return fail("UNSIGNED-ABSENT", {"error": str(exc)})

    unsigned_flag = (
        (pred.get("buildDefinition") or {})
        .get("internalParameters", {})
        .get("unsigned")
    )
    if unsigned_flag is not True:
        return fail("provenance-missing-unsigned-flag")

    print(
        json.dumps(
            {
                "ok": True,
                "reason": "OK",
                "artifact_sha256": got,
                "gitCommit": live,
                "git_via": how,
                "builder_id": builder,
                "unsigned_notes": notes_u,
                "unsigned_zip": zip_u,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:REL-0012-verify untampered digest+commit+UNSIGNED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
