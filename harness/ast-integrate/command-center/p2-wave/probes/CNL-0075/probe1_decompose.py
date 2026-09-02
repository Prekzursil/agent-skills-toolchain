#!/usr/bin/env python3
"""Probe 1: both-states decomposition + missing-hop census.

Good fixture must PASS (silent). Orphan sentence must FAIL. Severing
about_option_card_ids must FAIL the same walk. Chase and join walkers must
agree. If the catalog artifact exists, its missing_link and counts must match.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402
import lineage as L  # noqa: E402

ART = REPO / (
    "command-center/design/council/"
    "CNL-0075-decision-lineage-decomposing-a-decision-back-to-the-ideas-.md"
)
GOOD = HERE / "fixtures/good.json"
ORPHAN = HERE / "fixtures/orphan.json"
SEVERED = HERE / "fixtures/severed-claim-hop.json"


def dump_report(label: str, report: dict) -> None:
    print(
        f"{label} pass={report['pass']} sentences={report['sentence_count']} "
        f"resolved={report['resolved_count']} orphans={report['orphan_ids']}"
    )


def main() -> int:
    good = L.load_council(GOOD)
    orphan = L.load_council(ORPHAN)
    severed = L.load_council(SEVERED)

    g1, g2 = L.both_walkers_agree(good)
    dump_report("good/chase", g1)
    dump_report("good/join", g2)
    if not g1["pass"] or g1["sentence_count"] != 2 or g1["orphan_ids"]:
        print("FAILED:CNL-0075-probe1 good fixture did not pass silently")
        return 1
    if g1["sentences"][0]["ideas"] != ["idea.http-cache"]:
        print("FAILED:CNL-0075-probe1 s1 did not resolve to idea.http-cache")
        return 1
    if g1["sentences"][1]["ideas"] != ["idea.http-cache"]:
        print("FAILED:CNL-0075-probe1 s2 did not resolve to idea.http-cache")
        return 1

    o1, _ = L.both_walkers_agree(orphan)
    dump_report("orphan/chase", o1)
    print(
        "NEGATIVE-CONTROL: orphan sentence s3 'Also migrate billing to another "
        "continent.' has empty cites; checker FAILS with orphan_ids=['s3'] "
        f"reasons={o1['sentences'][2]['orphan_reasons']}"
    )
    if o1["pass"] or o1["orphan_ids"] != ["s3"]:
        print("FAILED:CNL-0075-probe1 orphan fixture did not fail on s3 only")
        return 1
    if "empty-cites" not in o1["sentences"][2]["orphan_reasons"]:
        print("FAILED:CNL-0075-probe1 orphan reasons missing empty-cites")
        return 1
    if o1["resolved_count"] != 2:
        print("FAILED:CNL-0075-probe1 orphan fixture should still resolve s1/s2")
        return 1

    s1, _ = L.both_walkers_agree(severed)
    dump_report("severed-claim-hop/chase", s1)
    print(
        "NEGATIVE-CONTROL: claims.about_option_card_ids=[] severs option_card->"
        "claim; walk from decision/action_plan never reaches an idea, so both "
        f"sentences FAIL orphan_ids={s1['orphan_ids']}"
    )
    if s1["pass"] or set(s1["orphan_ids"]) != {"s1", "s2"}:
        print("FAILED:CNL-0075-probe1 severed hop did not orphan s1 and s2")
        return 1
    if "no-idea-reached" not in s1["sentences"][0]["orphan_reasons"]:
        print("FAILED:CNL-0075-probe1 severed hop missing no-idea-reached")
        return 1

    measured = C.measure()
    missing = measured["missing_link"]
    print(f"census missing_link={missing}")
    hop_rows = {f"{h['from_kind']}->{h['to_kind']}": h for h in measured["hops"]}
    claim_hop = hop_rows["option_card->claim"]
    print(
        "claim-hop catalog_authors="
        f"{claim_hop['catalog_authors_excluding_self']} "
        f"field_hits={claim_hop['parent_field_hits_outside_self']}"
    )
    if missing != "option_card->claim":
        print(
            f"FAILED:CNL-0075-probe1 expected missing_link option_card->claim got {missing}"
        )
        return 1
    if claim_hop["catalog_authored"] or claim_hop["parent_field_present_on_disk"]:
        print("FAILED:CNL-0075-probe1 option_card->claim unexpectedly present")
        return 1

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if doc.get("missing_link") != missing:
            print(
                "FAILED:CNL-0075-probe1 artifact missing_link "
                f"{doc.get('missing_link')!r} != census {missing!r}"
            )
            return 1
        counts = doc.get("decomposition_counts") or {}
        if counts.get("good_sentences") != 2 or counts.get("orphan_ids") != ["s3"]:
            print(f"FAILED:CNL-0075-probe1 artifact counts mismatch {counts}")
            return 1
        if "SUCCESS:CNL-0075" not in ART.read_text(encoding="utf-8"):
            print("FAILED:CNL-0075-probe1 sentinel absent from artifact")
            return 1
        print("artifact-claims-match=True")
    else:
        print("artifact-absent (fixture tests only)")

    print("SUCCESS:CNL-0075-probe1 decompose both-states missing-hop")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
