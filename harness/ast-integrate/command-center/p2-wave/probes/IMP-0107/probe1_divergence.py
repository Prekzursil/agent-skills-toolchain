#!/usr/bin/env python3
"""IMP-0107 probe 1: planted divergence is recorded; install writes nothing.

Two independent signals:
  (1) the on-disk conflict JSON names both digests and both sources
  (2) a filesystem census of the install dest is unchanged after refuse
Negative control in the same run: matching digests install normally.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "marketplace"))

from mirror_conflict import (  # noqa: E402
    MirrorConflictPolicy,
    census,
    load_conflict_file,
    sha256_digest,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0107-probe1 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0107-p1-") as tmp:
        tmp_path = Path(tmp)
        store = tmp_path / "conflicts.json"
        dest = tmp_path / "install-root"
        policy = MirrorConflictPolicy(store)

        upstream_blob = b"IMP-0107-upstream-canonical"
        mirror_blob = b"IMP-0107-mirror-substituted"
        up_d = sha256_digest(upstream_blob)
        mir_d = sha256_digest(mirror_blob)
        if up_d == mir_d:
            return fail("planted blobs unexpectedly share a digest")

        policy.compare_and_record(
            "planted-pkg",
            "1.0.0",
            upstream_url="https://upstream.example/planted-pkg/1.0.0",
            upstream_digest=up_d,
            mirror_url="file:///private-mirror/planted-pkg/1.0.0",
            mirror_digest=mir_d,
        )

        # Signal 1: parse the store bytes independently of the return value.
        raw = store.read_text(encoding="utf-8")
        recs = load_conflict_file(store)
        if len(recs) != 1:
            return fail(f"expected 1 conflict record, got {len(recs)}")
        rec = recs[0]
        sources = rec.get("sources") or []
        by_name = {s.get("name"): s for s in sources if isinstance(s, dict)}
        signal1 = (
            rec.get("upstream_digest") == up_d
            and rec.get("mirror_digest") == mir_d
            and rec.get("status") == "unresolved"
            and set(by_name) == {"upstream", "mirror"}
            and by_name["upstream"].get("digest") == up_d
            and by_name["mirror"].get("digest") == mir_d
            and by_name["upstream"].get("url", "").startswith("https://")
            and by_name["mirror"].get("url", "").startswith("file://")
            and "preferred_source" not in rec
            and "winner" not in rec
            and up_d in raw
            and mir_d in raw
        )
        if not signal1:
            return fail(f"conflict record missing both digests/sources: {json.dumps(rec)}")

        # Signal 2: census before/after install, independent of InstallResult.written.
        dest.mkdir(parents=True)
        marker = dest / ".keep-empty-check"
        # dest exists but must receive no package files
        before = census(dest)
        result = policy.install("planted-pkg", "1.0.0", dest, mirror_blob)
        after = census(dest)
        planted_rel = "planted-pkg/1.0.0/payload.bin"
        signal2 = (
            result.ok is False
            and planted_rel not in after
            and before == after
            and not (dest / "planted-pkg").exists()
            and not marker.exists()
        )
        if not signal2:
            return fail(
                f"install did not fail closed census_before={before} after={after} "
                f"ok={result.ok} reason={result.reason}"
            )

        # Negative control: matching digests install in THIS run.
        good_blob = b"IMP-0107-matching-both-sides"
        good_d = sha256_digest(good_blob)
        match = policy.compare_and_record(
            "clean-pkg",
            "1.0.0",
            upstream_url="https://upstream.example/clean-pkg/1.0.0",
            upstream_digest=good_d,
            mirror_url="file:///private-mirror/clean-pkg/1.0.0",
            mirror_digest=good_d,
        )
        if match is not None:
            return fail(f"matching digests recorded a conflict: {match}")
        allowed = policy.install("clean-pkg", "1.0.0", dest, good_blob)
        walked = census(dest)
        good_rel = "clean-pkg/1.0.0/payload.bin"
        if not allowed.ok or good_rel not in walked:
            return fail(f"matching digest did not install ok={allowed.ok} census={walked}")
        if walked[good_rel] != hashlib.sha256(good_blob).hexdigest():
            return fail("installed blob digest mismatch")
        if planted_rel in walked:
            return fail("refused package appeared in dest after matching install")

        out = {
            "probe": "probe1-divergence",
            "unit_id": "IMP-0107",
            "signal1_conflict_record_both_digests_and_sources": True,
            "signal2_census_unchanged_on_refuse": True,
            "negative_control_matching_installs_same_run": True,
            "upstream_digest": up_d,
            "mirror_digest": mir_d,
            "matching_digest": good_d,
            "census_after": walked,
            "pass": True,
        }
        print(json.dumps(out, sort_keys=True))
        print(
            "signal1_record=True signal2_census_empty_for_conflict=True "
            "negative_control_same_run=True"
        )
        print("SUCCESS:IMP-0107-probe1 divergence recorded and install refused")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
