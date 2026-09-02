#!/usr/bin/env python3
"""Named probe 2: atomic tmp+replace writes, rebuild correctness, mutant controls.

Catalog tests_required: test_cache_writes_are_atomic, test_rebuild_produces_a_correct_entry
Precedent: a render cancelled mid-write leaves a half-file unless writes are tmp + mv -f.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from scenario import (  # noqa: E402
    run_atomic_interrupt,
    run_inplace_mutant,
    run_rebuild_correct,
    run_silent_serve_mutant,
)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0097-p2-") as tmp:
        root = Path(tmp)
        atomic = run_atomic_interrupt(root)
        inplace = run_inplace_mutant(root)
        rebuild = run_rebuild_correct(root)
        silent = run_silent_serve_mutant(root)

    failures = []
    if atomic.get("partial_published"):
        failures.append("atomic-interrupt-left-partial-on-publish-path")
    if not atomic.get("payload_sha256_match"):
        failures.append("atomic-rebuild-hash-mismatch")
    if not atomic.get("leftover_cleared"):
        failures.append("atomic-leftover-tmp-not-cleared")
    if atomic.get("orphan_tmp_count", 0) < 1:
        failures.append("atomic-interrupt-did-not-leave-tmp-for-sweep")
    if not inplace.get("partial_on_publish_path"):
        failures.append("inplace-mutant-did-not-leave-partial (detector silent)")
    if not inplace.get("detector_fires"):
        failures.append("integrity-inspect-silent-on-inplace-partial")
    if not rebuild.get("rebuilt"):
        failures.append("rebuild-not-triggered")
    if not rebuild.get("payload_sha256_match"):
        failures.append("rebuild-bytes-mismatch")
    if not rebuild.get("post_rebuild_inspect_ok"):
        failures.append("post-rebuild-entry-not-intact")
    if not silent.get("served_corrupt") or not silent.get("detector_fires"):
        failures.append("silent-serve-mutant-did-not-go-red")
    if silent.get("served_equals_expected"):
        failures.append("silent-serve-mutant-accidentally-correct")

    out = {
        "probe": "probe2-atomic-rebuild",
        "unit_id": "TST-0097",
        "pass": not failures,
        "atomic": {
            "partial_published": atomic["partial_published"],
            "orphan_tmp_count": atomic["orphan_tmp_count"],
            "leftover_cleared": atomic["leftover_cleared"],
            "payload_sha256_match": atomic["payload_sha256_match"],
            "publish_method": "tmp + os.replace",
        },
        "inplace_mutant_control": {
            "partial_on_publish_path": inplace["partial_on_publish_path"],
            "detector_fires": inplace["detector_fires"],
            "inspect_mode": inplace.get("inspect_mode"),
        },
        "rebuild": {
            "rebuilt": rebuild["rebuilt"],
            "payload_sha256_match": rebuild["payload_sha256_match"],
            "post_rebuild_inspect_ok": rebuild["post_rebuild_inspect_ok"],
            "served_sha256": rebuild["served_sha256"],
            "expected_sha256": rebuild["expected_sha256"],
        },
        "silent_serve_mutant_control": {
            "served_corrupt": silent["served_corrupt"],
            "detector_fires": silent["detector_fires"],
            "p0": silent["p0"],
        },
        "failures": failures,
    }
    print(json.dumps(out, sort_keys=True))
    if failures:
        print("FAILED:TST-0097-probe2 " + ",".join(failures))
        return 1
    print(
        "atomic_partial_published=False inplace_partial=True "
        "rebuild_hash_match=True silent_serve_mutant_red=True"
    )
    print("SUCCESS:TST-0097-probe2 atomic writes and correct rebuild")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
