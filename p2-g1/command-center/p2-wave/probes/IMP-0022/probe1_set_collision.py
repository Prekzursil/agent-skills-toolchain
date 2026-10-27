#!/usr/bin/env python3
"""Named probe 1: casefold-collision COUNT over the payload path set (signal 1).

Independent of the extract-count signal. Groups paths with the documented
NFC+casefold key using a local dict (not ``find_casefold_collisions``), then
requires the production detector to agree. Disagreement is a detector failure,
not a picked winner.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plugin.case_collision import find_casefold_collisions  # noqa: E402
from plugin.pathnorm import NORMALISATION, normalised_payload_path  # noqa: E402
from plugin.payload_paths import expand_payload_paths  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0022.json"


def independent_groups(paths: list[str]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = defaultdict(list)
    seen: set[str] = set()
    for raw in paths:
        original = raw.replace("\\", "/")
        if original in seen:
            continue
        seen.add(original)
        groups[normalised_payload_path(original)].append(original)
    return dict(groups)


def collisions_from_groups(groups: dict[str, list[str]]) -> list[tuple[str, list[str]]]:
    return [
        (key, members)
        for key, members in sorted(groups.items())
        if len(members) > 1
    ]


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0022-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:IMP-0022-probe1 receipt unparseable: {exc}")
        return 1
    if "SUCCESS:IMP-0022" not in text:
        print("FAILED:IMP-0022-probe1 sentinel absent")
        return 1
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:IMP-0022-probe1 self-declared {st}")
        return 1
    if NORMALISATION["case_mapping"] != "str.casefold":
        print("FAILED:IMP-0022-probe1 documented mapping is not casefold")
        return 1
    if NORMALISATION["order"] != ["NFC", "casefold"]:
        print(f"FAILED:IMP-0022-probe1 order={NORMALISATION['order']}")
        return 1

    payload = expand_payload_paths(REPO)
    indep = collisions_from_groups(independent_groups(payload))
    prod = find_casefold_collisions(payload)
    indep_count = len(indep)
    prod_count = len(prod)
    if indep_count != prod_count:
        print(
            f"FAILED:IMP-0022-probe1 signal disagreement "
            f"indep={indep_count} prod={prod_count}"
        )
        return 1
    if indep_count != 0:
        print(f"FAILED:IMP-0022-probe1 live payload collisions={indep_count}")
        for key, members in indep:
            print(f"  {key}: {members}")
        return 1

    planted = ["docs/README.md", "docs/readme.md", "docs/unique.txt"]
    planted_indep = collisions_from_groups(independent_groups(planted))
    planted_prod = find_casefold_collisions(planted)
    if len(planted_indep) != 1 or len(planted_prod) != 1:
        print(
            f"FAILED:IMP-0022-probe1 planted README pair silent "
            f"indep={len(planted_indep)} prod={len(planted_prod)}"
        )
        return 1
    planted_paths = set(planted_prod[0].paths)
    if planted_paths != {"docs/README.md", "docs/readme.md"}:
        print(f"FAILED:IMP-0022-probe1 planted paths {planted_paths}")
        return 1

    report = {
        "probe": "probe1-set-collision",
        "unit_id": "IMP-0022",
        "normalisation": NORMALISATION,
        "payload_path_count": len(payload),
        "casefold_collision_count": indep_count,
        "production_agrees": True,
        "planted_readme_pair_fired": True,
        "computed_not_asserted": True,
    }
    print(json.dumps(report, sort_keys=True))
    print(
        f"payload={len(payload)} collisions={indep_count} "
        "planted_readme_fired=True prod_agrees=True"
    )
    print("SUCCESS:IMP-0022-probe1 casefold-collision count over payload path set")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
