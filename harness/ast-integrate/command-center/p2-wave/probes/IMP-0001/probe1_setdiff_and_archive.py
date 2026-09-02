#!/usr/bin/env python3
"""Probe 1: path census set-difference vs allowlist expansion,
then tar tf listing of the emitted artifact re-checked by matcher B.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "plugin"))

import payload_allowlist as pa  # noqa: E402

ART = REPO / "command-center" / "receipts" / "IMP-0001.json"


def main() -> int:
    doc = pa.load_allowlist()
    if pa.unbounded_include_globs(doc):
        print("FAILED:IMP-0001-probe1 unbounded include glob")
        return 1
    source, census = pa.listed_paths(REPO)
    payload_a = pa.expand(census, doc, matcher="a")
    payload_b = pa.expand(census, doc, matcher="b")
    if payload_a != payload_b:
        print(json.dumps({"a": payload_a, "b": payload_b}, indent=2))
        print("FAILED:IMP-0001-probe1 detector-failure matcher A vs B")
        return 1
    diff = pa.set_difference(census, payload_a)
    if diff["only_payload_count"] != 0:
        print(json.dumps(diff, indent=2, sort_keys=True))
        print("FAILED:IMP-0001-probe1 expansion produced paths absent from census")
        return 1
    if diff["payload_count"] < 1:
        print("FAILED:IMP-0001-probe1 empty payload")
        return 1
    if diff["only_census_count"] < 1:
        print("FAILED:IMP-0001-probe1 payload is not a subset (no unmatched census paths)")
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0001-p1-") as tmp:
        archive = Path(tmp) / "payload.tar"
        packed = pa.pack_repo(REPO, archive, doc)
        members = pa.tar_members(archive)
        listing = pa.tar_tf_listing(archive)
        listing_ok = listing == payload_a
        members_ok = members == payload_a
        outside = [p for p in listing if not pa.is_allowlisted(p, doc, matcher="b")]
        report = {
            "probe": "probe1-setdiff-and-archive",
            "unit_id": "IMP-0001",
            "census_source": source,
            "census_count": diff["census_count"],
            "payload_count": diff["payload_count"],
            "unmatched_count": diff["only_census_count"],
            "symmetric_difference_count": diff["symmetric_difference_count"],
            "tar_tf": listing,
            "tarfile_members": members,
            "signals_agree": listing_ok and members_ok and packed["ok"] and not outside,
            "outside_allowlist": outside,
            "census_source_note": (
                "git ls-files when .git exists; this worktree has no .git so the "
                "census is a worktree walk (honest fallback, same set-difference)"
                if source == "worktree-walk"
                else "git ls-files"
            ),
        }
        print(json.dumps(report, indent=2, sort_keys=True))
        if not report["signals_agree"]:
            print("FAILED:IMP-0001-probe1 enumerations disagree or path outside allowlist")
            return 1

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        if "SUCCESS:IMP-0001" not in text:
            print("FAILED:IMP-0001-probe1 receipt sentinel absent")
            return 1
        body = json.loads(text)
        st = str(body.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print(f"FAILED:IMP-0001-probe1 receipt self-declared {st}")
            return 1

    print(
        f"census={diff['census_count']} payload={diff['payload_count']} "
        f"unmatched={diff['only_census_count']} source={source}"
    )
    print("SUCCESS:IMP-0001-probe1 set-difference agrees with tar tf listing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
