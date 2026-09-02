#!/usr/bin/env python3
"""Freeze a 58-protocol stand-in catalogue from CNL-0038..CNL-0046 ranging sets."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import family as F  # noqa: E402

OUT = HERE / "fixtures" / "12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
FAMILY_RE = re.compile(r"family=([A-Z-]+)")
SOURCE_UNITS = [f"CNL-{n:04d}" for n in range(38, 47)]


def main() -> int:
    protocols = []
    families = {}
    for uid in SOURCE_UNITS:
        unit = F.catalog_unit(uid)
        ev = str(unit.get("evidence_requirement") or "")
        m = FAMILY_RE.search(ev)
        if not m:
            print(f"FAILED:fixture {uid} missing family=")
            return 1
        family = m.group(1)
        pairs = F.parse_ranging(str(unit.get("question_or_target") or ""))
        n_m = F.EXPECTED_N_RE.search(ev)
        if not n_m or int(n_m.group(1)) != len(pairs):
            print(f"FAILED:fixture {uid} ranging count {len(pairs)}")
            return 1
        families[family] = [pid for pid, _ in pairs]
        for pid, slug in pairs:
            rec = {"id": pid, "slug": slug, "family": family, "source_unit": uid}
            if pid == "P48":
                rec["alias"] = "adversarial-war-game"
                rec["alias_note"] = (
                    "Substring 'adversarial' is not family membership; "
                    "family is ENGINEERING-REVIEW"
                )
            protocols.append(rec)
    ids = [p["id"] for p in protocols]
    if len(ids) != 58 or len(set(ids)) != 58:
        print(f"FAILED:fixture unique {len(set(ids))} / {len(ids)}")
        return 1
    if families.get("ADVERSARIAL") != [
        "P07",
        "P08",
        "P09",
        "P10",
        "P11",
        "P12",
        "P13",
    ]:
        print(f"FAILED:fixture ADVERSARIAL {families.get('ADVERSARIAL')}")
        return 1
    doc = {
        "artifact": "12-COUNCIL-PROTOCOLS-AND-PRESETS",
        "reconstruction": (
            "Windows path C:/Users/Prekzursil/.claude/harness-restore-20260806/"
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is not on this Linux worktree. "
            "This fixture is a mechanical extraction of the named ranging sets "
            "in WORK-UNIT-CATALOG.json units CNL-0038 through CNL-0046 "
            "(58 protocol records, 9 families)."
        ),
        "windows_library_present": False,
        "protocol_count": 58,
        "family_counts": {k: len(v) for k, v in families.items()},
        "protocols": protocols,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(F.REPO)} n={len(protocols)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
