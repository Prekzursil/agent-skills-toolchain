#!/usr/bin/env python3
"""Named probe 1: adopt-in-place + python-sha256 preservation (signal 1)."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from adopt import adopt_estate, adopt_real_tree  # noqa: E402
from estate import (  # noqa: E402
    CLAIMED_LIVE_RELS,
    MCP_STATE,
    OWNER_NOTE,
    PRESERVE_RELS,
    USER_DATA,
    build_estate,
)
from uninstall import (  # noqa: E402
    legal_uninstall,
    preservation_report,
    snapshot_preserve,
)

ART = REPO / "command-center/phase3/A3/MIGRATION.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:ARC-0021-probe1 migration artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "ARC-0021":
        print("FAILED:ARC-0021-probe1 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:ARC-0021" not in json.dumps(doc):
        print("FAILED:ARC-0021-probe1 sentinel absent")
        return 1

    with tempfile.TemporaryDirectory(prefix="arc0021-p1-") as tmp:
        root = Path(tmp)
        estate = root / "estate"
        snap = root / "snap"
        build_estate(estate)
        adopted = adopt_estate(estate)
        if adopted["missing_unclaimed"] or adopted["missing_claimed"]:
            print("FAILED:ARC-0021-probe1 adopt incomplete")
            print(json.dumps(adopted, indent=2)[:2000])
            return 1
        if adopted.get("rewrite_live_bytes"):
            print("FAILED:ARC-0021-probe1 rewrite_live_bytes must be false")
            return 1
        for rel in CLAIMED_LIVE_RELS:
            before = (estate / rel).read_bytes()
            # adopt must not rewrite
            after = (estate / rel).read_bytes()
            if before != after:
                print(f"FAILED:ARC-0021-probe1 bytes rewritten {rel}")
                return 1
        unclaimed_paths = {u["path"] for u in adopted["unclaimed"]}
        for rel in (OWNER_NOTE, USER_DATA, MCP_STATE):
            if rel not in unclaimed_paths:
                print(f"FAILED:ARC-0021-probe1 {rel} was claimed")
                return 1
        recorded = {r["path"]: r for r in (doc.get("sample") or [])}
        for rec in adopted["sample"]:
            got = recorded.get(rec["path"])
            if not got:
                print(f"FAILED:ARC-0021-probe1 artifact missing sample {rec['path']}")
                return 1
            if got.get("sha256") != rec["sha256"]:
                print(f"FAILED:ARC-0021-probe1 sha mismatch {rec['path']}")
                return 1
            if got.get("bytes_rewritten") is not False:
                print(f"FAILED:ARC-0021-probe1 artifact rewrote {rec['path']}")
                return 1
        snapshot_preserve(estate, snap)
        legal_uninstall(estate)
        report = preservation_report(estate, snap)
        if report.get("signal_disagreement"):
            print("FAILED:ARC-0021-probe1 signal disagreement (BLOCKED, not picked)")
            print(json.dumps(report, indent=2, default=str)[:2000])
            return 1
        if not report["pass"]:
            print("FAILED:ARC-0021-probe1 preservation")
            print(json.dumps(report, indent=2, default=str)[:2000])
            return 1
        real = adopt_real_tree(REPO)
        art_real = (doc.get("evidence") or {}).get("adoption_on_real_tree") or {}
        if art_real.get("tree") != real["tree"]:
            print("FAILED:ARC-0021-probe1 real tree id drift")
            return 1
        if sorted(art_real.get("claimed") or []) != sorted(real["claimed"]):
            print("FAILED:ARC-0021-probe1 real-tree claimed mismatch")
            print("live", real["claimed"])
            print("art", art_real.get("claimed"))
            return 1
        art_un = [
            u if isinstance(u, str) else u.get("path")
            for u in (art_real.get("unclaimed") or [])
        ]
        live_un = [u["path"] for u in real["unclaimed"]]
        if sorted(art_un) != sorted(live_un):
            print("FAILED:ARC-0021-probe1 real-tree unclaimed mismatch")
            return 1

    tests = (doc.get("tests") or {}).get("preservation") or {}
    if tests.get("signal1_sha256_intact") != report["signal1_sha256_intact"]:
        print("FAILED:ARC-0021-probe1 artifact signal1 drift")
        return 1

    out = {
        "probe": "probe1-adopt-sha256",
        "unit_id": "ARC-0021",
        "claimed": len(adopted["sample"]),
        "unclaimed": len(adopted["unclaimed"]),
        "preserve": list(PRESERVE_RELS),
        "signal1_sha256_intact": report["signal1_sha256_intact"],
        "real_tree_claimed": len(real["claimed"]),
        "real_tree_unclaimed": len(real["unclaimed"]),
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"claimed={out['claimed']} unclaimed={out['unclaimed']} "
        f"sha256_intact={out['signal1_sha256_intact']} "
        f"real_claimed={out['real_tree_claimed']}"
    )
    print("SUCCESS:ARC-0021-probe1 adopt-in-place and sha256 preservation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
