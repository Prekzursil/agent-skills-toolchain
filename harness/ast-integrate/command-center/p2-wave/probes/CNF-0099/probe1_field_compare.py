#!/usr/bin/env python3
"""Named probe 1: field-by-field user-state compare (different signal than probe 2).

Re-installs previous, seeds, upgrades with migration, then:
  * flatten+compare every field against apply_migration(before)
  * sha256 the owner skill and owner rule (must be byte-identical)
  * prefix-check the in-flight ledger
Does not consult skip-migration health; that is probe 2.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from engine import (  # noqa: E402
    USER_RULE_REL,
    USER_SKILL_REL,
    flatten,
    run_scenario,
)

ART = REPO / "command-center/confirmation/CNF-0099-upgrade-path.json"


def payload(doc: dict) -> dict:
    report = doc.get("report")
    if isinstance(report, dict) and "field_comparisons" in report:
        return report
    return doc


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0099-probe1 upgrade artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0099":
        print("FAILED:CNF-0099-probe1 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:CNF-0099" not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNF-0099-probe1 sentinel absent")
        return 1

    with tempfile.TemporaryDirectory(prefix="cnf0099-p1-") as tmp:
        result = run_scenario(Path(tmp))

    if not result["expected_match"]:
        print("FAILED:CNF-0099-probe1 expected state != after state")
        print(json.dumps({"after": result["after_state"]}, indent=2)[:2000])
        return 1
    if result["semantic_loss"]:
        print("FAILED:CNF-0099-probe1 semantic-loss")
        print(json.dumps(result["semantic_loss"], indent=2)[:2000])
        return 1
    if not result["skill_preserved"] or not result["rule_preserved"]:
        print("FAILED:CNF-0099-probe1 user file bytes changed")
        return 1
    if not result["ledger_prefix_intact"]:
        print("FAILED:CNF-0099-probe1 ledger prefix lost")
        return 1
    if not result["migration_log"].get("ran"):
        print("FAILED:CNF-0099-probe1 migration did not run")
        return 1
    if len(result["field_comparisons"]) < 6:
        print("FAILED:CNF-0099-probe1 too few field rows", len(result["field_comparisons"]))
        return 1

    body = payload(doc)
    recorded = body.get("field_comparisons") or []
    live_paths = {r["path"] for r in result["field_comparisons"]}
    rec_paths = {r["path"] for r in recorded if isinstance(r, dict)}
    if live_paths != rec_paths:
        print("FAILED:CNF-0099-probe1 artifact field-path drift")
        print("only_live", sorted(live_paths - rec_paths)[:20])
        print("only_art", sorted(rec_paths - live_paths)[:20])
        return 1

    live_skill = next(r for r in result["after_inventory"] if r["path"] == USER_SKILL_REL)
    rec_skill = next(
        r
        for r in (body.get("inventories") or {}).get("after") or []
        if r.get("path") == USER_SKILL_REL
    )
    if live_skill["sha256"] != rec_skill.get("sha256"):
        print("FAILED:CNF-0099-probe1 skill sha drift")
        return 1
    live_rule = next(r for r in result["after_inventory"] if r["path"] == USER_RULE_REL)
    rec_rule = next(
        r
        for r in (body.get("inventories") or {}).get("after") or []
        if r.get("path") == USER_RULE_REL
    )
    if live_rule["sha256"] != rec_rule.get("sha256"):
        print("FAILED:CNF-0099-probe1 rule sha drift")
        return 1

    after_flat = flatten(result["after_state"])
    if after_flat.get("settings.custom.owner.pref") is not None:
        print("FAILED:CNF-0099-probe1 custom key survived under the v1 name")
        return 1
    if after_flat.get("settings.user_keys.owner.pref") != "keep-me":
        print("FAILED:CNF-0099-probe1 owner.pref not semantically intact")
        return 1
    if after_flat.get("settings.locale.lang") != "en" or after_flat.get("settings.locale.region") != "GB":
        print("FAILED:CNF-0099-probe1 locale reshape lost meaning")
        return 1

    out = {
        "probe": "probe1-field-compare",
        "unit_id": "CNF-0099",
        "fields": len(result["field_comparisons"]),
        "skill_preserved": True,
        "rule_preserved": True,
        "ledger_prefix_intact": True,
        "expected_match": True,
        "migration_ran": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"fields={out['fields']} skill=True rule=True ledger_prefix=True "
        "owner.pref=keep-me locale=en-GB"
    )
    print("SUCCESS:CNF-0099-probe1 field-by-field user state")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
