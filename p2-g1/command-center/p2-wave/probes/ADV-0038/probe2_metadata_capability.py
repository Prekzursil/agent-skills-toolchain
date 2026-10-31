#!/usr/bin/env python3
"""Probe 2: metadata-capability audit — does each source even have a revocation field?"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

ART = REPO / H.ARTIFACT_REL


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:ADV-0038-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if H.SENTINEL not in text or H.COMPLETION_SENTINEL not in text:
        print("FAILED:ADV-0038-probe2 sentinel absent")
        return 1
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ADV-0038-probe2 self-declared {st}")
        return 1

    live = H.run_scenario()
    if not live["controls"]["no_source_revocation_field"]:
        print("FAILED:ADV-0038-probe2 unexpected revocation field on a source sidecar")
        print(json.dumps(live["source_metadata"], sort_keys=True)[:2000])
        return 1
    if not live["controls"]["no_schema_revocation_field"]:
        print("FAILED:ADV-0038-probe2 production schema unexpectedly has a revocation field")
        print(json.dumps(live["production"]["schemas"], sort_keys=True)[:2000])
        return 1
    if not live["controls"]["detector_plant_fires"]:
        print("FAILED:ADV-0038-probe2 planted revoked field was not detected")
        return 1
    if not live["controls"]["detector_clean_silent"]:
        print("FAILED:ADV-0038-probe2 detector not silent on clean metadata")
        return 1
    if live["production"].get("any_revocation_impl"):
        print("FAILED:ADV-0038-probe2 unexpected production revocation impl present")
        return 1
    if live["production"].get("token_hits"):
        print("FAILED:ADV-0038-probe2 revocation tokens inside install-path modules")
        print(live["production"]["token_hits"])
        return 1
    # Shard0 repair 2026-10-24: tree-wide hits (registry-side subsystem, data
    # files) are evidence, not failure - but they MUST be recorded in the
    # artifact and must match the live tree.
    art_tree = (doc.get("production") or {}).get("tree_token_hits")
    live_tree = live["production"].get("tree_token_hits")
    if art_tree != live_tree:
        print("FAILED:ADV-0038-probe2 artifact tree_token_hits drift vs live")
        return 1
    if live_tree and not str(doc.get("production", {}).get("note", "")).count("install-path"):
        print("FAILED:ADV-0038-probe2 artifact note does not record the scope split")
        return 1
    if not live["production"].get("yank_lockfile_pin_resolvable"):
        print("FAILED:ADV-0038-probe2 expected yank.py lockfile-pin corroboration absent")
        return 1

    art_meta = {
        m["source"]: m.get("revocation_fields")
        for m in (doc.get("source_metadata") or [])
    }
    live_meta = {m["source"]: m["revocation_fields"] for m in live["source_metadata"]}
    if art_meta != live_meta:
        print("FAILED:ADV-0038-probe2 artifact/live metadata mismatch")
        print(art_meta, live_meta)
        return 1

    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") != "PASS" or not reviewer.get("independent"):
        print("FAILED:ADV-0038-probe2 reviewer block", reviewer)
        return 1
    fp = H.fingerprints()
    if fp["source"] == fp["verifier"]:
        print("FAILED:ADV-0038-probe2 probe fingerprints identical")
        return 1

    schema_rows = []
    for sch in live["production"]["schemas"]:
        schema_rows.append(
            {
                "path": sch["path"],
                "exists": sch["exists"],
                "revocation_fields": sch["revocation_fields"],
                "closed": sch["additional_properties_closed"],
            }
        )
    summary = {
        "probe": "probe2-metadata-capability",
        "unit_id": H.UNIT,
        "source_revocation_fields": live_meta,
        "schema_rows": schema_rows,
        "plant_fired": True,
        "clean_silent": True,
        "token_hits": 0,
        "tree_token_hit_paths": len(live_tree or []),
        "imp0079_present": bool(
            (live["production"].get("imp0079_receipt") or {}).get("exists")
        ),
        "source_fp": fp["source"][:16],
        "verifier_fp": fp["verifier"][:16],
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:ADV-0038-probe2 no revocation field on any source or live schema")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
