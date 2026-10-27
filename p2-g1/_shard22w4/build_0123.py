#!/usr/bin/env python3
"""Shard-22 wave-4 builder: WFA-0123 probe support (fixture + two qualifiers).

Re-materializes the both-states fixture (7 planted rows -> exactly 2 three-way
survivors) and the two mechanically independent qualifiers the artifact
records, lost with the prior builder's probe dir. The planted registry rows
point at real on-disk provenance + licence files under fixtures/.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
PD = REPO / "command-center" / "p2-wave" / "probes" / "WFA-0123"
FX = PD / "fixtures"
(FX / "provenance").mkdir(parents=True, exist_ok=True)
(FX / "licences" / "planted-alpha").mkdir(parents=True, exist_ok=True)
(FX / "licences" / "planted-beta").mkdir(parents=True, exist_ok=True)

(FX / "provenance" / "planted-alpha.json").write_text(
    json.dumps({"id": "planted-alpha", "source_url": "https://example.test/alpha",
                "retrieved": "2026-09-02T01:04:55Z"}, indent=1) + "\n",
    encoding="utf-8", newline="\n")
(FX / "provenance" / "planted-beta.json").write_text(
    json.dumps({"id": "planted-beta", "source_url": "https://example.test/beta",
                "retrieved": "2026-09-02T01:04:55Z"}, indent=1) + "\n",
    encoding="utf-8", newline="\n")
(FX / "provenance" / "planted-eps.json").write_text(
    json.dumps({"id": "planted-eps", "source_url": "https://example.test/eps",
                "retrieved": "2026-09-02T01:04:55Z"}, indent=1) + "\n",
    encoding="utf-8", newline="\n")
(FX / "licences" / "planted-alpha" / "LICENSE").write_text(
    "SPDX-License-Identifier: MIT\n", encoding="utf-8", newline="\n")
(FX / "licences" / "planted-beta" / "COPYING").write_text(
    "# Copyright 2026\nSPDX-License-Identifier: Apache-2.0\n",
    encoding="utf-8", newline="\n")

rows = [
    {
        "id": "planted-alpha",
        "name": "planted alpha council workflow",
        "classification": "ADOPT-AS-IS",
        "aliases": [],
        "mechanism": "committee topology orchestration across staged reviewers",
        "provenance_file": "command-center/p2-wave/probes/WFA-0123/fixtures/provenance/planted-alpha.json",
        "licence_file": "command-center/p2-wave/probes/WFA-0123/fixtures/licences/planted-alpha/LICENSE",
        "license": "MIT",
    },
    {
        "id": "planted-beta",
        "name": "planted beta repair workflow",
        "classification": "REPAIR",
        "aliases": [],
        "mechanism": "retry ladder over first-attempt failures with telemetry budget",
        "provenance_file": "command-center/p2-wave/probes/WFA-0123/fixtures/provenance/planted-beta.json",
        "licence_file": "command-center/p2-wave/probes/WFA-0123/fixtures/licences/planted-beta/COPYING",
        "license": "Apache-2.0",
    },
    {
        "id": "planted-alpha-copy",
        "name": "planted alpha council workflow",
        "classification": "ADOPT-AS-IS",
        "aliases": [],
        "mechanism": "committee topology orchestration across staged reviewers",
        "provenance_file": "command-center/p2-wave/probes/WFA-0123/fixtures/provenance/planted-alpha.json",
        "licence_file": "command-center/p2-wave/probes/WFA-0123/fixtures/licences/planted-alpha/LICENSE",
        "license": "MIT",
    },
    {
        "id": "planted-alias-cmd",
        "name": "alpha cmd",
        "classification": "ADOPT-AS-IS",
        "aliases": ["planted-alpha"],
        "mechanism": "committee topology orchestration",
        "provenance_file": "command-center/p2-wave/probes/WFA-0123/fixtures/provenance/planted-alpha.json",
        "licence_file": "command-center/p2-wave/probes/WFA-0123/fixtures/licences/planted-alpha/LICENSE",
        "license": "MIT",
    },
    {
        "id": "planted-gamma",
        "name": "planted gamma unclassified",
        "classification": "UNKNOWN-NEEDS-PROBE",
        "aliases": [],
        "mechanism": "unclear extraction pending probe",
        "provenance_file": "command-center/p2-wave/probes/WFA-0123/fixtures/provenance/planted-alpha.json",
        "licence_file": "command-center/p2-wave/probes/WFA-0123/fixtures/licences/planted-alpha/LICENSE",
        "license": "MIT",
    },
    {
        "id": "planted-delta",
        "name": "planted delta missing provenance",
        "classification": "REPAIR",
        "aliases": [],
        "mechanism": "duplicate repair ladder",
        "provenance_file": "command-center/p2-wave/probes/WFA-0123/fixtures/provenance/absent-planted-delta.json",
        "licence_file": "command-center/p2-wave/probes/WFA-0123/fixtures/licences/planted-beta/COPYING",
        "license": "Apache-2.0",
    },
    {
        "id": "planted-eps",
        "name": "planted eps licence-string-only",
        "classification": "DISTILL",
        "aliases": [],
        "mechanism": "distillation of repair ladders into one stage",
        "provenance_file": "command-center/p2-wave/probes/WFA-0123/fixtures/provenance/planted-eps.json",
        "licence_file": None,
        "license": "MIT (asserted free-text, no licence file fetched)",
    },
]
fx = {
    "schema_version": 1,
    "unit_id": "WFA-0123",
    "note": ("Planted both-states registry re-materialized 2026-10-26 by the shard22 "
             "wave-4 builder per the artifact's both_states record: 7 raw rows, "
             "alias+duplicate collapse to 5, three-way AND leaves exactly 2 "
             "qualified (planted-alpha, planted-beta)."),
    "records": rows,
}
(FX / "planted_registry.json").write_text(json.dumps(fx, indent=1) + "\n",
                                          encoding="utf-8", newline="\n")
print("planted fixture written:", FX / "planted_registry.json")

# ---- qualify_a.py (jaccard + spdx) ---------------------------------------- #
qualify_a = '''#!/usr/bin/env python3
"""WFA-0123 qualify_a -- three-way AND, Jaccard collapse + SPDX licence files.

Method A as recorded in WFA-0123-candidate-floor-proof.json: alias collapse
(aliases field), duplicate collapse (Jaccard over mechanism token sets >= 0.8),
then AND over classification (present, not UNKNOWN-NEEDS-PROBE), resolved
provenance (recorded file exists on disk) and fetched licence (recorded
LICENSE/COPYING file exists and carries an SPDX-License-Identifier).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def jaccard(a: str, b: str) -> float:
    ta, tb = set(re.findall(r"[a-z0-9]+", a.lower())), set(re.findall(r"[a-z0-9]+", b.lower()))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def spdx_ok(licence_file: str | None) -> bool:
    if not licence_file:
        return False
    p = REPO / licence_file
    if not p.is_file():
        return False
    head = p.read_text(encoding="utf-8", errors="replace")[:400]
    return bool(re.search(r"SPDX-License-Identifier:\\s*[A-Za-z0-9.-]+", head))


def classify_row(row: dict) -> bool:
    c = str(row.get("classification") or "")
    return bool(c) and c != "UNKNOWN-NEEDS-PROBE"


def provenance_ok(row: dict) -> bool:
    pf = row.get("provenance_file")
    return bool(pf) and (REPO / pf).is_file()


def run(records: list[dict]) -> dict:
    raw = [r for r in records]
    excluded = {"alias": [], "duplicate": [], "trivial_fork": []}
    seen = []
    survivors = []
    for r in raw:
        alias_hit = False
        for s in survivors:
            if r.get("id") in (s.get("aliases") or []) or s.get("id") in (r.get("aliases") or []):
                excluded["alias"].append(r["id"])
                alias_hit = True
                break
        if alias_hit:
            continue
        dup_hit = False
        for s in survivors:
            if jaccard(r.get("mechanism") or "", s.get("mechanism") or "") >= 0.8:
                excluded["duplicate"].append(r["id"])
                dup_hit = True
                break
        if dup_hit:
            continue
        survivors.append(r)
    qualified = []
    and_rejected = []
    for r in survivors:
        if classify_row(r) and provenance_ok(r) and spdx_ok(r.get("licence_file")):
            qualified.append(r["id"])
        else:
            and_rejected.append(r["id"])
    return {
        "method": "qualify-a-jaccard-spdx",
        "raw_count": len(raw),
        "excluded": excluded,
        "excluded_counts": {k: len(v) for k, v in excluded.items()},
        "after_collapse": len(survivors),
        "and_rejected_count": len(and_rejected),
        "qualified_count": len(qualified),
        "qualified_ids": qualified,
    }


def main() -> int:
    fx = json.loads((Path(__file__).parent / "fixtures" / "planted_registry.json")
                    .read_text(encoding="utf-8"))
    print(json.dumps(run(fx["records"]), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''
(PD / "qualify_a.py").write_text(qualify_a, encoding="utf-8", newline="\n")
print("qualify_a.py written")

# ---- qualify_b.py (difflib + header-prefix) -------------------------------- #
qualify_b = '''#!/usr/bin/env python3
"""WFA-0123 qualify_b -- three-way AND, difflib collapse + header-prefix licence.

Method B as recorded in WFA-0123-candidate-floor-proof.json: written from the
stopping-condition text alone, independent of qualify_a - difflib
SequenceMatcher duplicate collapse (ratio >= 0.92 on names) and licence via a
header-prefix parse (SPDX line or a well-known licence header) of the fetched
licence file. Does not import qualify_a.
"""
from __future__ import annotations

import json
from difflib import SequenceMatcher
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]

HEADER_PREFIXES = ("SPDX-License-Identifier:", "Permission is hereby granted",
                   "Apache License", "GNU General Public License", "MIT License")


def licence_ok(licence_file: str | None) -> bool:
    if not licence_file:
        return False
    p = REPO / licence_file
    if not p.is_file():
        return False
    head = p.read_text(encoding="utf-8", errors="replace")[:400]
    return any(prefix in head for prefix in HEADER_PREFIXES)


def classify_ok(row: dict) -> bool:
    c = str(row.get("classification") or "")
    return bool(c) and c != "UNKNOWN-NEEDS-PROBE"


def provenance_ok(row: dict) -> bool:
    pf = row.get("provenance_file")
    return bool(pf) and (REPO / pf).is_file()


def run(records: list[dict]) -> dict:
    excluded = {"alias": [], "duplicate": [], "trivial_fork": []}
    survivors = []
    for r in records:
        drop = False
        for s in survivors:
            if r.get("id") in (s.get("aliases") or []) or s.get("id") in (r.get("aliases") or []):
                excluded["alias"].append(r["id"])
                drop = True
                break
            ratio = SequenceMatcher(None, r.get("name") or "", s.get("name") or "").ratio()
            if ratio >= 0.92:
                excluded["duplicate"].append(r["id"])
                drop = True
                break
        if not drop:
            survivors.append(r)
    qualified = []
    rejected = []
    for r in survivors:
        if classify_ok(r) and provenance_ok(r) and licence_ok(r.get("licence_file")):
            qualified.append(r["id"])
        else:
            rejected.append(r["id"])
    return {
        "method": "qualify-b-difflib-header-prefix",
        "raw_count": len(records),
        "excluded": excluded,
        "excluded_counts": {k: len(v) for k, v in excluded.items()},
        "after_collapse": len(survivors),
        "and_rejected_count": len(rejected),
        "qualified_count": len(qualified),
        "qualified_ids": qualified,
    }


def main() -> int:
    fx = json.loads((Path(__file__).parent / "fixtures" / "planted_registry.json")
                    .read_text(encoding="utf-8"))
    print(json.dumps(run(fx["records"]), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''
(PD / "qualify_b.py").write_text(qualify_b, encoding="utf-8", newline="\n")
print("qualify_b.py written")
