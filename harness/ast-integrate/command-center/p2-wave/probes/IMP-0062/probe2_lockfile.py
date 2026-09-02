#!/usr/bin/env python3
"""IMP-0062 probe 2: independent lockfile parse vs SBOM, set equality.

Generator reads npm `packages`. This probe's oracle walks the nested
`dependencies` tree and regex-parses Python lockfiles. A schema-valid SBOM
listing the wrong names fails here. Also: planted-dep both-states control
and vendored-tree presence (no lockfile entry).
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
FIXTURE = PLUGIN / "tests" / "fixtures" / "plugin-closure"
sys.path.insert(0, str(PLUGIN))

from lockfile_closure import (  # noqa: E402
    compare_sets,
    independent_lockfile_identities,
    vendored_dir_names,
)
from sbom import build_bom, identities_from_bom  # noqa: E402

ART = REPO / "command-center" / "receipts" / "IMP-0062.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0062-probe2 receipt missing")
        return 1
    receipt = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:IMP-0062" not in json.dumps(receipt):
        print("FAILED:IMP-0062-probe2 sentinel absent")
        return 1

    bom = build_bom(FIXTURE, timestamp="2026-08-24T18:00:00Z")
    gen = identities_from_bom(bom, source="lockfile")
    ind = independent_lockfile_identities(FIXTURE)
    diff = compare_sets(gen, ind)
    if not diff["equal"]:
        print("FAILED:IMP-0062-probe2 lockfile set inequality")
        print(json.dumps(diff, indent=2)[:3000])
        return 1
    if ("nested-dep", "0.4.0") not in gen:
        print("FAILED:IMP-0062-probe2 nested transitive dep missing")
        return 1

    vendored = identities_from_bom(bom, source="vendored")
    walked = vendored_dir_names(FIXTURE)
    vendored_names = {n for n, _ in vendored}
    if "unpinned-widget" not in walked or "unpinned-widget" not in vendored_names:
        print("FAILED:IMP-0062-probe2 vendored tree omitted", sorted(vendored_names), sorted(walked))
        return 1
    if any(n == "unpinned-widget" and v != "unpinned" for n, v in vendored):
        print("FAILED:IMP-0062-probe2 unpinned vendored given a fake version")
        return 1
    if ("unpinned-widget", "unpinned") in ind:
        print("FAILED:IMP-0062-probe2 independent parser invented a lockfile entry for vendor/")
        return 1

    planted = ("evil-planted", "9.9.9")
    with tempfile.TemporaryDirectory(prefix="imp0062-p2-") as tmp:
        dest = Path(tmp) / "plugin"
        shutil.copytree(FIXTURE, dest)
        (dest / "requirements.lock").write_text(
            (dest / "requirements.lock").read_text(encoding="utf-8") + "\nevil-planted==9.9.9\n",
            encoding="utf-8",
        )
        independent_after = independent_lockfile_identities(dest)
        stale = compare_sets(gen, independent_after)
        if stale["equal"] or planted not in independent_after:
            print("FAILED:IMP-0062-probe2 planted dep did not break unre-generated comparison")
            return 1
        regen = identities_from_bom(build_bom(dest, timestamp="2026-08-24T18:00:00Z"), source="lockfile")
        if planted not in regen:
            print("FAILED:IMP-0062-probe2 regenerated SBOM missing planted dep")
            return 1
        fresh = compare_sets(regen, independent_after)
        if not fresh["equal"]:
            print("FAILED:IMP-0062-probe2 regenerated set mismatch")
            print(json.dumps(fresh, indent=2)[:2000])
            return 1

    payload = {
        "pass": True,
        "probe": "probe2-lockfile-set-equality",
        "unit_id": "IMP-0062",
        "lockfile_count": len(gen),
        "independent_count": len(ind),
        "equal": True,
        "nested_dep_present": True,
        "vendored": sorted(vendored_names),
        "negative_control_stale_mismatch": True,
        "negative_control_regen_contains_planted": True,
        "names": sorted(n for n, _ in gen),
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"equal=True lockfile={len(gen)} vendored={sorted(vendored_names)} "
        f"planted_control=True nested-dep=True"
    )
    print("SUCCESS:IMP-0062-probe2 independent lockfile parse set equality")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
