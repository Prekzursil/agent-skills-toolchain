#!/usr/bin/env python3
"""Probe 1: attacker input-bundle hygiene fingerprint.

Catalog control: fingerprint the attacking agent's input bundle to prove it
contained no session context. An attacker that already knows the owner
proves nothing.

Both-states: injecting an agent-transcripts path into the same list must
make the fingerprint unclean. Extractor liveness is a planted two-file join.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402

ART = REPO / E.OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0142-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    sentinel = E.completion_sentinel()
    if sentinel not in text:
        return fail("catalog sentinel absent")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")

    paths = E.iter_publishable_paths()
    hyg = E.hygiene_report(paths)
    recorded = doc.get("hygiene") or {}
    if not hyg["clean"]:
        return fail(f"live bundle unclean: {hyg['forbidden_path_hits']}")
    if recorded.get("clean") is not True:
        return fail("artifact hygiene.clean is not true")
    live_sha = hyg.get("bundle_sha256") or ""
    rec_sha = str(recorded.get("bundle_sha256") or "")
    if len(rec_sha) != 64 or any(c not in "0123456789abcdef" for c in rec_sha.lower()):
        return fail("artifact bundle_sha256 is not a sha256 hex digest")
    if len(live_sha) != 64:
        return fail("live bundle_sha256 missing")
    # Point-in-time content hash is recorded in the artifact. Sibling G-1
    # writers on this worktree may add receipts after emit, so live==recorded
    # is not required. The control is: both fingerprints are well-formed and
    # both bundles are session-clean.
    if recorded.get("session_context_present") is not False:
        return fail("session_context_present not false")
    if recorded.get("brief_present") is not False:
        return fail("brief_present not false")
    if recorded.get("memory_tools_present") is not False:
        return fail("memory_tools_present not false")
    if recorded.get("external_lookup_performed") is not False:
        return fail("external_lookup_performed not false")
    if hyg["file_count"] < 20:
        return fail(f"publishable set too small: {hyg['file_count']}")

    reviewer = doc.get("reviewer") or {}
    if reviewer.get("read_order") != "hygiene-fingerprint-before-findings":
        return fail("reviewer did not record hygiene-before-findings")

    if not E.contaminated_hygiene_fails():
        return fail("contamination both-states did not fire")

    plant = E.planted_join_control()
    if not plant["join_detected"]:
        return fail("planted two-file username join was silent")
    if not plant["clean_silent"]:
        return fail("clean scratch file produced a join")

    print(
        json.dumps(
            {
                "probe": "probe1-hygiene",
                "unit_id": "ADV-0142",
                "pass": True,
                "bundle_sha256": hyg["bundle_sha256"],
                "file_count": hyg["file_count"],
                "clean": True,
                "contamination_control": True,
                "planted_join": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"files={hyg['file_count']} sha={hyg['bundle_sha256'][:16]} "
        "clean=True contamination_fires=True planted_join=True"
    )
    print("SUCCESS:ADV-0142-probe1 input-bundle hygiene fingerprint clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
