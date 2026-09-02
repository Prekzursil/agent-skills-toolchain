#!/usr/bin/env python3
"""Probe 2: independent refuter. Does not call engine.score_claim.

Re-reads the artifact and live CLAIM-REGISTRY. Defaults to REFUTED when
a high-severity recorded claim is missing from the BELOW set, when a
cited snapshot's sha256 has drifted, or when who_may_lower[P0] is not
owner-only.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / (
    "command-center/research/evidence-quality/"
    "RES-0184-evidence-threshold-by-claim-severity.json"
)
REGISTRY = REPO / "command-center/CLAIM-REGISTRY.json"
OWNER = REPO / "command-center/OWNER-DECISIONS.md"
SENTINEL = "SUCCESS:RES-0184"
GATE_CLAIM = "CL-CC-0014-DEFAULT-FLOOR-ENFORCED"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0184-probe2 {msg}")
    return 1


def snapshot_digests(path: Path) -> set[str]:
    raw = path.read_bytes()
    lf = raw.replace(b"\r\n", b"\n")
    return {
        hashlib.sha256(raw).hexdigest(),
        hashlib.sha256(lf).hexdigest(),
    }


def independent_p0_below(row: dict) -> bool:
    """Minimal P0 bar, re-implemented here so a green engine.score_claim cannot hide a miss."""
    n_src = int(row.get("independent_source_count") or 0)
    n_cls = int(row.get("source_class_count") or 0)
    executable = bool(row.get("executable"))
    kent = row.get("sherman_kent")
    return n_src < 2 or n_cls < 2 or not executable or not kent


def main() -> int:
    if not ART.is_file():
        return fail("artifact-absent")
    raw = ART.read_text(encoding="utf-8")
    if SENTINEL not in raw:
        return fail("sentinel-absent")
    doc = json.loads(raw)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    rescore = doc.get("rescore") or {}
    below_ids = list(rescore.get("below_bar_ids") or [])
    high_ids = list(rescore.get("high_severity_below_ids") or [])
    rows = list(rescore.get("rows") or [])
    if int(rescore.get("n") or 0) != 20:
        return fail("artifact-n-not-20")
    if int(rescore.get("below_bar_count") or 0) == 0:
        return fail("status-quo-bar-zero-below")
    if GATE_CLAIM not in below_ids or GATE_CLAIM not in high_ids:
        return fail(f"registry-p1-not-below:{GATE_CLAIM}")
    if not REGISTRY.is_file():
        return fail("claim-registry-absent")
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    live_ids = {c.get("id") for c in (registry.get("claims") or []) if isinstance(c, dict)}
    if GATE_CLAIM not in live_ids:
        return fail("gate-claim-missing-from-live-registry")
    who = (doc.get("who_may_lower") or {}).get("P0")
    if who != "owner-only":
        return fail(f"p0-who-may-lower:{who!r}")
    waiver = (doc.get("who_may_lower") or {}).get("owner_waiver") or {}
    if waiver.get("p0_waiver_recorded"):
        return fail("unexpected-p0-waiver-recorded")
    if OWNER.is_file() and not waiver.get("present"):
        return fail("owner-log-present-but-unreported")
    p0_rows = [r for r in rows if r.get("severity") == "P0"]
    if not p0_rows:
        return fail("no-p0-in-artifact")
    p0_below_independent = [
        r["claim_id"] for r in p0_rows if independent_p0_below(r)
    ]
    if not p0_below_independent:
        return fail("independent-p0-check-found-no-below")
    # Re-hash a cited snapshot from a scored row that names a live file.
    rehashed = None
    for r in rows:
        for lin in r.get("lineage") or []:
            snap = lin.get("snapshot_path")
            expect = lin.get("sha256")
            if not snap or not expect:
                continue
            path = REPO / str(snap)
            if not path.is_file():
                continue
            got_set = snapshot_digests(path)
            rehashed = {
                "claim_id": r.get("claim_id"),
                "snapshot_path": snap,
                "expected": expect,
                "got": sorted(got_set),
                "match": expect in got_set,
            }
            if expect not in got_set:
                return fail(f"snapshot-sha-drift:{snap}")
            break
        if rehashed:
            break
    if rehashed is None:
        return fail("no-rehashable-snapshot")
    print(
        json.dumps(
            {
                "probe": "probe2-refuter",
                "gate_claim_below": GATE_CLAIM in high_ids,
                "below_bar_count": rescore.get("below_bar_count"),
                "high_severity_below_ids": high_ids,
                "p0_who_may_lower": who,
                "independent_p0_below_ids": p0_below_independent,
                "rehashed": rehashed,
            },
            sort_keys=True,
        )
    )
    print(
        f"gate_below={GATE_CLAIM} p0_independent_below={p0_below_independent} "
        f"rehash_ok={rehashed['match']}"
    )
    print("SUCCESS:RES-0184-probe2 independent refuter lineage rehash and P0 owner-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
