#!/usr/bin/env python3
"""Unit tests for tools/marketplace/provenance_store.py (IMP-0080).

Runs standalone (``python3 -B test_provenance_store.py``) or under pytest.
Every test uses throwaway temp directories; the repo's own git is never
touched. Both states are exercised: verification passes on honest data and
RAISES on tampered bytes, unresolved commits, and empty-query 'successes'.
"""
from __future__ import annotations

import hashlib
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import provenance_store as ps  # noqa: E402

PACKAGE = "internal-kit"
VERSION = "1.2.3"


def _world(tmp: Path):
    src = tmp / "source"
    commit, tree = ps.init_source_repo(src, {"pkg/PAYLOAD.txt": b"IMP-0080 payload\n"})
    artifact = b"IMP-0080 artifact bytes\n"
    att = ps.make_attestation(
        package=PACKAGE,
        version=VERSION,
        artifact_digest=ps.artifact_sha256(artifact),
        source_repo=str(src),
        commit_sha=commit,
        tree_hash=tree,
        builder_id="test-builder",
    )
    store = ps.ProvenanceStore(tmp / "store")
    rec = store.publish(
        package=PACKAGE, version=VERSION, artifact=artifact, attestation=att, source_repo=src
    )
    return store, src, artifact, rec, commit, tree


def test_publish_and_query_present() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="imp0080-t1-"))
    try:
        store, _src, artifact, rec, _c, _t = _world(tmp)
        assert rec["status"] == "PRESENT"
        payload = ps.interpret_query(store.query(PACKAGE, VERSION))
        assert payload.status == "PRESENT"
        assert payload.record is not None
        assert payload.record["artifact_digest_sha256"] == hashlib.sha256(artifact).hexdigest()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_digest_verify_both_states() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="imp0080-t2-"))
    try:
        store, _src, artifact, _rec, _c, _t = _world(tmp)
        good = store.verify_against_artifact(PACKAGE, VERSION, artifact)
        assert good["verified"] is True
        raised = False
        try:
            store.verify_against_artifact(PACKAGE, VERSION, artifact + b"tamper")
        except ps.DigestMismatchError:
            raised = True
        assert raised, "tampered artifact must raise DigestMismatchError"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_commit_tree_verify_both_states() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="imp0080-t3-"))
    try:
        store, src, _artifact, _rec, commit, tree = _world(tmp)
        good = store.verify_commit_tree(PACKAGE, VERSION, src)
        assert good["verified"] is True and good["commit_sha"] == commit and good["tree_hash"] == tree
        other = tmp / "other"
        ps.init_source_repo(other, {"pkg/PAYLOAD.txt": b"different tree\n"})
        raised = False
        try:
            store.verify_commit_tree(PACKAGE, VERSION, other)
        except ps.UnresolvedCommitError:
            raised = True
        assert raised, "foreign tree must raise UnresolvedCommitError"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_empty_query_success_rejected() -> None:
    for bad in (None, {}, {"ok": True}):
        raised = False
        try:
            ps.interpret_query(bad)  # type: ignore[arg-type]
        except ps.EmptyQuerySuccess:
            raised = True
        assert raised, f"empty query payload {bad!r} must raise EmptyQuerySuccess"


def test_unresolved_commit_rejected_at_publish() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="imp0080-t5-"))
    try:
        src = tmp / "source"
        commit, tree = ps.init_source_repo(src, {"pkg/PAYLOAD.txt": b"x\n"})
        store = ps.ProvenanceStore(tmp / "store")
        att = ps.make_attestation(
            package=PACKAGE,
            version=VERSION,
            artifact_digest=ps.artifact_sha256(b"x"),
            source_repo=str(src),
            commit_sha="0" * 40,
            tree_hash=tree,
        )
        raised = False
        try:
            store.publish(package=PACKAGE, version=VERSION, attestation=att, source_repo=src)
        except ps.UnresolvedCommitError:
            raised = True
        assert raised, "all-zero commit must raise UnresolvedCommitError"
        att_bad = dict(att)
        att_bad["commit_sha"] = "f" * 40
        raised = False
        try:
            store.publish(package=PACKAGE, version=VERSION, attestation=att_bad, source_repo=src)
        except ps.UnresolvedCommitError:
            raised = True
        assert raised, "commit absent from the source repo must raise"
        assert commit  # planted commit resolvable (control)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


TESTS = (
    test_publish_and_query_present,
    test_digest_verify_both_states,
    test_commit_tree_verify_both_states,
    test_empty_query_success_rejected,
    test_unresolved_commit_rejected_at_publish,
)


def main() -> int:
    for fn in TESTS:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"SUCCESS:test_provenance_store {len(TESTS)}/{len(TESTS)} tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
