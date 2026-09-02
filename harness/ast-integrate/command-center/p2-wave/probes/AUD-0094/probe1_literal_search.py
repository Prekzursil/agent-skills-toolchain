#!/usr/bin/env python3
"""Named probe 1: literal surviving-file search + use-vs-mention control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from fixtures import ensure_fixtures  # noqa: E402
from inventory import REPO, load_inventory  # noqa: E402
from scan_literal import control_verdict, scan_literal  # noqa: E402


def run() -> dict:
    ensure_fixtures()
    inv = load_inventory()
    deleted = inv["objects"]
    result = scan_literal(REPO, deleted, mention_filter=True)
    mutant = scan_literal(REPO, deleted, mention_filter=False)
    control = control_verdict(result, mutant)
    live_use = [
        h
        for h in result["use_hits"]
        if not str(h["citing_path"]).startswith(
            "command-center/p2-wave/probes/AUD-0094/fixtures/"
        )
    ]
    payload = {
        "pass": control["pass"],
        "probe": "probe1-literal-search",
        "unit_id": "AUD-0094",
        "files_scanned": result["files_scanned"],
        "bytes_scanned": result["bytes_scanned"],
        "use_hit_count": result["use_hit_count"],
        "mention_hit_count": result["mention_hit_count"],
        "dangling_paths": result["dangling_paths"],
        "mention_only_paths": result["mention_only_paths"],
        "live_use_hits_outside_fixtures": live_use[:40],
        "git_recovered_count": inv["recovered_count"],
        "git_available": inv["git"]["available"],
        "control": control,
        "computed_not_asserted": True,
    }
    return payload


def main() -> int:
    payload = run()
    print(json.dumps(payload, sort_keys=True))
    ctrl = payload["control"]
    print(
        "mention_ok={0} use_ok={1} mutant_red={2} dangling={3} mention_only={4}".format(
            ctrl["mention_not_reported_as_dangling"],
            ctrl["use_reported_as_dangling"],
            ctrl["mutant_without_filter_flags_changelog"],
            len(payload["dangling_paths"]),
            len(payload["mention_only_paths"]),
        )
    )
    if not payload["pass"]:
        print("FAILED:AUD-0094-probe1 use-vs-mention control")
        return 1
    print("SUCCESS:AUD-0094-probe1 literal search and use-vs-mention control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
