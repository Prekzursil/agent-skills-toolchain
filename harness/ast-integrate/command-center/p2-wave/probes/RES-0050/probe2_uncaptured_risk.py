#!/usr/bin/env python3
"""Probe 2: named risk the SBOM does not capture — hostile markdown skill."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sbom import (  # noqa: E402
    HOSTILE_MARK,
    NAMED_RISK_ID,
    inspect_bom,
    make_bom,
    sha256_file,
    write_hostile_fixture,
)


def main() -> int:
    root = write_hostile_fixture()
    skill = root / "skills" / "skill.council" / "SKILL.md"
    if HOSTILE_MARK not in skill.read_text(encoding="utf-8"):
        print("FAILED:RES-0050-probe2 hostile-mark-absent-from-fixture")
        return 1
    live_sha = sha256_file(skill)
    bom = make_bom(extra_roots=[root])
    blob = json.dumps(bom, indent=2, sort_keys=True)
    insp = inspect_bom(bom)
    errors: list[str] = []
    listed = None
    for c in bom["components"]:
        occ = ((c.get("evidence") or {}).get("occurrences") or [{}])[0]
        loc = str(occ.get("location") or "")
        if loc.endswith("skills/skill.council/SKILL.md"):
            listed = c
            break
    if listed is None:
        errors.append("hostile-skill-not-in-sbom")
    else:
        got = listed["hashes"][0]["content"]
        if got != live_sha:
            errors.append(f"hash-mismatch:{got}:{live_sha}")
        if listed.get("type") != "data":
            errors.append(f"skill-type:{listed.get('type')}")
    if HOSTILE_MARK in blob:
        errors.append("hostile-instruction-leaked-into-sbom")
    if (bom.get("vulnerabilities") or []) != []:
        errors.append("false-vuln-detection")
    detection_hits = []
    for c in bom["components"]:
        for prop in c.get("properties") or []:
            name = str(prop.get("name") or "").lower()
            val = str(prop.get("value") or "").lower()
            if "inject" in name or "hostile" in name or "prompt-injection" in val:
                detection_hits.append(name)
    if detection_hits:
        errors.append(f"false-semantic-detection:{detection_hits}")
    print(
        json.dumps(
            {
                "named_risk": NAMED_RISK_ID,
                "hostile_skill": skill.relative_to(HERE.parents[3]).as_posix(),
                "skill_sha256": live_sha,
                "listed": listed is not None,
                "hostile_mark_in_file": True,
                "hostile_mark_in_sbom": HOSTILE_MARK in blob,
                "vulnerabilities": bom.get("vulnerabilities"),
                "inspection": {
                    "component_count": insp["component_count"],
                    "by_type": insp["by_type"],
                    "by_payload_class": insp["by_payload_class"],
                },
            },
            indent=2,
            sort_keys=True,
        )
    )
    if errors:
        print("FAILED:RES-0050-probe2 " + ",".join(errors))
        return 1
    print(
        "SUCCESS:RES-0050-probe2 named risk "
        + NAMED_RISK_ID
        + " is listed-by-hash and not captured as a finding"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
