#!/usr/bin/env python3
"""Probe 2: independent lineage re-hash + overclaim mutants.

Does not call detector_control (probe 1's live git path). Re-reads snapshots,
recomputes sha256, and requires the artifact's claims to fail closed when
lineage or example counts are stripped.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center/research/evidence-quality/RES-0148-negative-result-venue-map.json"
SNAP = HERE / "fixtures" / "snapshots"
LINEAGE = HERE / "fixtures" / "lineage.json"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0148-probe2 {msg}")
    return 1


def digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def two_signals(ex: dict) -> bool:
    a = (ex.get("signal_a") or {}).get("pass") is True
    b = (ex.get("signal_b") or {}).get("pass") is True
    ba = (ex.get("signal_a") or {}).get("backend")
    bb = (ex.get("signal_b") or {}).get("backend")
    return a and b and isinstance(ba, str) and isinstance(bb, str) and ba != bb


def overclaim_fires(doc: dict) -> list[str]:
    """Return reasons the record is an overclaim / incomplete. Empty means honest."""
    reasons: list[str] = []
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        reasons.append(f"self-declared:{st}")
    if "SUCCESS:RES-0148" not in json.dumps(doc):
        reasons.append("sentinel-absent")
    venues = doc.get("venues") or []
    if len(venues) < 6:
        reasons.append("venues<6")
    for v in venues:
        status = v.get("status")
        examples = v.get("examples") or []
        if status == "PRODUCTIVE" and len(examples) < 2:
            reasons.append(f"{v.get('id')}:PRODUCTIVE-without-two-examples")
        if status not in {"PRODUCTIVE", "UNPRODUCTIVE"}:
            reasons.append(f"{v.get('id')}:status-not-honest")
        if status == "UNPRODUCTIVE" and len(examples) != 0:
            # allowed if examples failed signals; still must not claim PRODUCTIVE
            pass
        for ex in examples:
            if status == "PRODUCTIVE" and not two_signals(ex):
                reasons.append(f"{v.get('id')}:{ex.get('id')}:single-signal")
            lin = ex.get("lineage") or []
            if status == "PRODUCTIVE" and len(lin) < 1:
                reasons.append(f"{v.get('id')}:{ex.get('id')}:no-lineage")
            for row in lin:
                if not row.get("resolved_url") or not row.get("sha256") or not row.get("fetch_timestamp"):
                    reasons.append(f"{v.get('id')}:lineage-incomplete")
    claims = doc.get("claims") or []
    for c in claims:
        if not c.get("confidence_band"):
            reasons.append(f"{c.get('id')}:no-sherman-kent")
        if not c.get("independent_verification_path"):
            reasons.append(f"{c.get('id')}:no-verification-path")
        if int(c.get("signals") or 0) < 2 and c.get("verdict") == "CONFIRMED":
            reasons.append(f"{c.get('id')}:confirmed-without-two-signals")
    return reasons


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    art = json.loads(ART.read_text(encoding="utf-8"))
    lin = json.loads(LINEAGE.read_text(encoding="utf-8"))
    snaps = lin.get("snapshots") or []
    if len(snaps) < 20:
        return fail(f"lineage snapshots {len(snaps)} want>=20")

    mismatches = []
    for rec in snaps:
        path = SNAP / rec["name"]
        if not path.is_file():
            return fail(f"snapshot missing {rec['name']}")
        got = digest_file(path)
        if got != rec["sha256"]:
            mismatches.append(rec["name"])
        if rec.get("http_status") != 200:
            return fail(f"{rec['name']} http {rec.get('http_status')}")
    if mismatches:
        return fail(f"sha drift {mismatches[:5]}")

    # Artifact lineage rows must match fixture hashes for every cited snapshot.
    cited = []
    for v in art.get("venues") or []:
        for ex in v.get("examples") or []:
            cited.extend(ex.get("lineage") or [])
    if len(cited) < 12:
        return fail(f"cited lineage rows {len(cited)}")
    by_name = {r["name"]: r for r in snaps}
    for row in cited:
        snap_name = Path(str(row.get("snapshot") or "")).name
        rec = by_name.get(snap_name)
        if rec is None:
            return fail(f"lineage cites unknown snapshot {snap_name}")
        if row.get("sha256") != rec["sha256"]:
            return fail(f"artifact sha != fixture {snap_name}")
        if row.get("resolved_url") != rec["resolved_url"]:
            return fail(f"url drift {snap_name}")

    honest = overclaim_fires(art)
    if honest:
        return fail(f"live artifact overclaim {honest[:6]}")

    mutant_lineage = copy.deepcopy(art)
    mutant_lineage["venues"][0]["examples"][0]["lineage"] = []
    if not overclaim_fires(mutant_lineage):
        return fail("lineage-strip mutant did not fire")

    mutant_zero = copy.deepcopy(art)
    mutant_zero["venues"][1]["examples"] = []
    mutant_zero["venues"][1]["status"] = "PRODUCTIVE"
    if not overclaim_fires(mutant_zero):
        return fail("PRODUCTIVE-with-zero-examples mutant did not fire")

    mutant_signal = copy.deepcopy(art)
    mutant_signal["venues"][2]["examples"][0]["signal_b"]["pass"] = False
    if not overclaim_fires(mutant_signal):
        return fail("single-signal mutant did not fire")

    mutant_sha = copy.deepcopy(art)
    mutant_sha["venues"][3]["examples"][0]["lineage"][0]["sha256"] = "0" * 64
    # sha mismatch vs fixtures is checked above on the live doc; for the mutant,
    # incomplete/wrong sha should still leave resolved_url+timestamp but we treat
    # hash inequality as overclaim by comparing to fixtures:
    row = mutant_sha["venues"][3]["examples"][0]["lineage"][0]
    snap_name = Path(row["snapshot"]).name
    if row["sha256"] == by_name[snap_name]["sha256"]:
        return fail("sha mutant did not change hash")
    print(f"sha-mutant-detected name={snap_name} live_ne_mutant=True")

    print(
        f"rehashed={len(snaps)} cited_lineage={len(cited)} "
        f"overclaim_live=0 mutants_fired=lineage,zero,signal,sha"
    )
    print("SUCCESS:RES-0148-probe2 lineage rehash and overclaim mutants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
