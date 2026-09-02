#!/usr/bin/env python3
"""Probe 2: two-way BLOCK (no one-way sync) and reviewer destroy catch."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import parity as P  # noqa: E402
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/REL-0021.json"


def fail(msg: str) -> int:
    print(f"FAILED:REL-0021-probe2 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="rel0021-p2-") as td:
        control = S.build_control(Path(td) / "control")
        census = P.census_world(
            control["repo"], control["package_zip"], control["deployed"]
        )
        destroy = P.reviewer_destroy_attempt(
            control["package_zip"], control["deployed"], census
        )
        owner = control["deployed"] / "shipped/owner-note.txt"
        owner_after = owner.is_file()

    if census["verdict"] != "BLOCK":
        return fail(f"verdict {census['verdict']} want BLOCK")
    if census["four_way"]["divergent-both-ways"] != 1:
        return fail(f"two-way count {census['four_way']}")
    if "shipped/twoway.txt" not in census["two_way_paths"]:
        return fail(f"twoway path missing {census['two_way_paths']}")

    twoway = next(r for r in census["files"] if r["path"] == "shipped/twoway.txt")
    if twoway["class"] != "divergent-both-ways":
        return fail(f"twoway class {twoway['class']}")
    if twoway.get("sync_proposal") is not None:
        return fail(f"twoway emitted sync proposal {twoway.get('sync_proposal')}")
    if any(p["path"] == "shipped/twoway.txt" for p in census["sync_proposals"]):
        return fail(f"census sync_proposals includes twoway {census['sync_proposals']}")
    if twoway.get("verdict") != "BLOCK":
        return fail(f"twoway row verdict {twoway.get('verdict')}")
    if int(twoway.get("repo_only_line_count") or 0) < 1:
        return fail("twoway has no unique repo lines")
    if int(twoway.get("deployed_only_line_count") or 0) < 1:
        return fail("twoway has no unique deployed lines")

    if not destroy.get("caught_before_signoff"):
        return fail(f"oracle did not catch destroy {destroy}")
    if destroy.get("destroyed"):
        return fail("owner file was destroyed")
    if destroy.get("oracle_allowed"):
        return fail("oracle allowed overwrite")
    if not owner_after:
        return fail("owner file missing after attempted overwrite")
    if "shipped/owner-note.txt" not in (destroy.get("owner_paths") or []):
        return fail("owner path not in destroy record")

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        if "SUCCESS:REL-0021" not in text:
            return fail("receipt sentinel absent")
        doc = json.loads(text)
        if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail(f"receipt self-declared {doc.get('state')}")
        if doc.get("control_verdict") != "BLOCK":
            return fail(f"receipt control_verdict {doc.get('control_verdict')}")
        four = doc.get("four_way") or {}
        if int(four.get("divergent-both-ways") or 0) < 1:
            return fail("receipt four_way missing two-way count")
        rev = doc.get("reviewer") or {}
        if rev.get("verdict") != "PASS" or not rev.get("independent"):
            return fail("reviewer block missing independent PASS")
        if "overwrite" not in str(rev.get("attempt") or "").lower():
            return fail("reviewer attempt did not describe overwrite")

    print(
        json.dumps(
            {
                "probe": "probe2-two-way-block-reviewer",
                "verdict": census["verdict"],
                "divergent_both_ways": census["four_way"]["divergent-both-ways"],
                "sync_proposals_for_twoway": [
                    p for p in census["sync_proposals"] if p["path"] == "shipped/twoway.txt"
                ],
                "caught_before_signoff": destroy["caught_before_signoff"],
                "oracle_allowed": destroy["oracle_allowed"],
                "owner_survived": destroy["owner_survived"],
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:REL-0021-probe2 two-way-block-reviewer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
