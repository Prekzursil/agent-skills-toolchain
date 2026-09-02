#!/usr/bin/env python3
"""Probe 1: freeze gate mutation red, bump+migration green, non-frozen silent."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "command-center" / "freeze"))
import lib as F  # noqa: E402
import scenario as S  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:CC-0012-probe1 {msg}")
    return 1


def main() -> int:
    F.activate(REPO)
    ledger = F.loads_json(REPO / F.LEDGER_REL)
    schema_rel = S.first_schema(ledger)

    with tempfile.TemporaryDirectory(prefix="cc0012-p1-") as tmp:
        scratch = Path(tmp)
        S.copy_freeze_tree(REPO, scratch)
        live = F.evaluate_gate(scratch)
        silent_n = int(live.get("silent_count") or live.get("silent_count") or 0)
        rej_n = int(live.get("rejection_count") or live.get("rejection_count") or 0)
        print(
            f"live_gate ok={live.get('ok')} reason={live.get('reason')} "
            f"silent={silent_n} rejections={rej_n}"
        )
        if not live.get("ok"):
            print(json.dumps(live.get("rejections"), indent=2)[:2000])
            return fail("unmodified freeze snapshot tree is not silent")
        if silent_n < 3:
            return fail(f"expected several frozen files unchanged, got {silent_n}")

        S.copy_freeze_tree(REPO, scratch)
        S.mutate_schema_text(scratch / schema_rel, "MUTATION-NO-BUMP")
        red = F.evaluate_gate(scratch)
        red_reasons = [r.get("reason") for r in (red.get("rejections") or [])]
        print(f"mutation ok={red.get('ok')} reasons={red_reasons}")
        if red.get("ok"):
            return fail("unversioned frozen schema edit was admitted")
        if "no-version-bump" not in red_reasons:
            return fail(f"wanted no-version-bump, got {red_reasons}")

        S.copy_freeze_tree(REPO, scratch)
        unfrozen = scratch / S.UNFROZEN_REL
        unfrozen.parent.mkdir(parents=True, exist_ok=True)
        unfrozen.write_text(
            F.dumps_canon({"control": "not-frozen", "unit_id": "CC-0012"}),
            encoding="utf-8",
        )
        silent = F.evaluate_gate(scratch)
        print(
            f"nonfrozen ok={silent.get('ok')} rejections={silent.get('rejection_count')}"
        )
        if not silent.get("ok"):
            return fail("gate fired on a non-frozen path")

        S.copy_freeze_tree(REPO, scratch)
        S.write_schema_v1_v2_migration(scratch, schema_rel)
        target = scratch / schema_rel
        doc = F.loads_json(target)
        if not isinstance(doc, dict):
            return fail("schema subject is not an object")
        doc["schema_version"] = 2
        doc["x_cc0012_migrated"] = True
        doc["x_cc0012_probe_token"] = "POSITIVE-BUMP"
        target.write_text(F.dumps_canon(doc), encoding="utf-8")
        green = F.evaluate_gate(scratch)
        print(
            f"positive ok={green.get('ok')} admitted={green.get('admitted')} "
            f"rejections={green.get('rejections')}"
        )
        if not green.get("ok"):
            return fail("versioned schema change with migration was rejected")
        admitted_paths = [a.get("path") for a in (green.get("admitted") or [])]
        if schema_rel not in admitted_paths:
            return fail(f"admitted set missing {schema_rel}: {admitted_paths}")

    print(
        json.dumps(
            {
                "probe": "probe1-gate",
                "unit_id": "CC-0012",
                "live_silent": True,
                "mutation_rejected": True,
                "nonfrozen_silent": True,
                "positive_admitted": True,
                "schema_subject": schema_rel,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CC-0012-probe1 freeze gate mutation/positive/both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
