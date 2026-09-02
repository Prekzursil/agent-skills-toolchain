#!/usr/bin/env python3
"""Named probe 1: rehearsed supersede-then-rollback is byte-equal on two signals.

Signal 1: sha256 of the canonical serving-view dump (workflows + callers).
Signal 2: sha256 of the per-object digest map (each document/caller hashed
in isolation). Both must match the pre-supersession copy after rollback, and
decomposed source documents must be restored (tamper during the window cleared).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from engine import (  # noqa: E402
    OLD_ID,
    digest_map_sha,
    decompose,
    load_fixture,
    per_object_digests,
    rehearse_clean_cycle,
    serving_canonical_bytes,
    sha256_bytes,
    Registry,
)

ART = REPO / "command-center/foundry/WFA-0142-supersession-engine-with-migration-and-rollback-to-s.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0142-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"artifact unparseable:{exc}")
    if not isinstance(doc, dict):
        return fail("artifact not an object")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")
    if "SUCCESS:WFA-0142" not in text:
        return fail("sentinel-absent")

    cycle = rehearse_clean_cycle()
    if not cycle.pass_:
        print(json.dumps(cycle.as_dict(), sort_keys=True))
        return fail(f"cycle {cycle.reason}")
    if not cycle.byte_equal:
        return fail("serving dump not byte-equal after rollback")
    if not cycle.digest_map_equal:
        return fail("per-object digest map not equal after rollback")
    if cycle.pre_serving_sha256 != cycle.post_serving_sha256:
        return fail("serving sha mismatch")
    if cycle.pre_digest_map_sha256 != cycle.post_digest_map_sha256:
        return fail("digest-map sha mismatch")
    if cycle.pre_serving_sha256 == cycle.pre_digest_map_sha256:
        return fail("signals collapsed to one hash")
    if cycle.decomposed_sources != ["src.review", "src.test"]:
        return fail(f"decompose={cycle.decomposed_sources}")
    if not cycle.sources_restored_equal or not cycle.tamper_cleared:
        return fail("source components not restored")

    expected_callers = ["fusion.pipeline", "pack.nightly", "preset.pr-gate"]
    got_callers = sorted(m["caller_id"] for m in cycle.migration)
    if got_callers != expected_callers:
        return fail(f"migration set {got_callers}")

    rec = doc.get("rehearsal") or {}
    rec_cycle = rec.get("clean_cycle") or {}
    if rec_cycle.get("pre_serving_sha256") != cycle.pre_serving_sha256:
        return fail("artifact serving sha stale vs live")
    if rec_cycle.get("pre_digest_map_sha256") != cycle.pre_digest_map_sha256:
        return fail("artifact digest-map sha stale vs live")
    if rec.get("migration_caller_ids") != expected_callers:
        return fail("artifact migration set stale vs live")

    # Recompute signal 1 and 2 on a fresh registry to prove they are live.
    reg = Registry(load_fixture())
    sig1 = sha256_bytes(serving_canonical_bytes(reg))
    sig2 = digest_map_sha(per_object_digests(reg))
    if sig1 != cycle.pre_serving_sha256 or sig2 != cycle.pre_digest_map_sha256:
        return fail("fresh registry hashes disagree with rehearsal")
    if decompose(reg, OLD_ID) != ["src.review", "src.test"]:
        return fail("fresh decompose mismatch")

    summary = {
        "probe": "probe1-rollback-byte-equality",
        "unit_id": "WFA-0142",
        "pass": True,
        "byte_equal": cycle.byte_equal,
        "digest_map_equal": cycle.digest_map_equal,
        "signal1_serving_sha256": cycle.pre_serving_sha256,
        "signal2_digest_map_sha256": cycle.pre_digest_map_sha256,
        "signals_distinct": True,
        "migration_caller_ids": expected_callers,
        "decomposed_sources": cycle.decomposed_sources,
        "tamper_cleared": cycle.tamper_cleared,
        "anchors": cycle.anchors,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"byte_equal={cycle.byte_equal} sig1={cycle.pre_serving_sha256[:12]} "
        f"sig2={cycle.pre_digest_map_sha256[:12]} callers={expected_callers}"
    )
    print("SUCCESS:WFA-0142-probe1 supersede-rollback byte equality (two signals)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
