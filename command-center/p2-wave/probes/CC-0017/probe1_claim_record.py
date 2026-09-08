#!/usr/bin/env python3
"""CC-0017 probe1: planted controls + schedule recompute + migrate round-trip."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "tools" / "command-center"))
import claim_record as cr  # noqa: E402


def main() -> int:
    pytest_cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tools/command-center/tests/test_claim_record.py",
        "-q",
    ]
    proc = subprocess.run(
        pytest_cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    pytest_out = (proc.stdout or "") + (proc.stderr or "")
    (PROBE / "pytest-claim-record.out").write_text(pytest_out, encoding="utf-8")

    meta = cr.provisional_meta()
    schedule = cr.recompute_schedule_after_soft_1_2()
    migrated = cr.migrate_registry_file(claim_ids=["CC-1", "CC-2", "CC-7"])
    migrate_errs = cr.validate_registry(migrated)
    field_loss = []
    registry = json.loads(
        (REPO / "command-center/CLAIM-REGISTRY.json").read_text(encoding="utf-8")
    )
    by_id = {c["id"]: c for c in registry["claims"]}
    for mig in migrated:
        legacy = by_id[mig["claim_id"]]
        if mig.get("legacy_fields") != legacy:
            field_loss.append(mig["claim_id"])

    # Negative controls exercised explicitly (not only via pytest).
    no_probe = {
        "schema_version": 1,
        "schema_status": "PROVISIONAL",
        "superseded_by_unit": "ARC-0085",
        "claim_id": "NEG-1",
        "canonical_mechanism": "x",
        "duplicate_of": [],
        "supports": [],
        "contradicts": [],
        "source_lineage": [{"anchor": "n"}],
        "confidence": None,
        "verification_status": "UNVERIFIED",
        "implementation_impact": "n",
        "settling_probe": "",
    }
    no_probe_errs = cr.validate_claim(no_probe, known_ids={"NEG-1"})

    cycle_errs = cr.validate_registry(
        [
            {
                **no_probe,
                "claim_id": "A",
                "settling_probe": "p",
                "duplicate_of": ["B"],
            },
            {
                **no_probe,
                "claim_id": "B",
                "settling_probe": "p",
                "duplicate_of": ["A"],
            },
        ]
    )
    ghost_errs = cr.validate_claim(
        {**no_probe, "settling_probe": "p", "contradicts": ["GHOST"]},
        known_ids={"NEG-1"},
    )

    summary = {
        "probe": "CC-0017-claim-record",
        "ok": bool(
            proc.returncode == 0
            and meta["schema_status"] == "PROVISIONAL"
            and meta["superseded_by_unit"] == "ARC-0085"
            and schedule["schedule_claim_recomputed"]["units_released"] == 224
            and schedule["schedule_claim_recomputed"]["critical_path_after"] == 10
            and schedule["schedule_claim_recomputed"]["critical_path_before"] == 11
            and not migrate_errs
            and not field_loss
            and any("settling_probe" in e for e in no_probe_errs)
            and any("duplicate_of cycle" in e for e in cycle_errs)
            and any("GHOST" in e for e in ghost_errs)
        ),
        "pytest_rc": proc.returncode,
        "provisional": True,
        "superseded_by_unit": "ARC-0085",
        "schedule": schedule["schedule_claim_recomputed"],
        "schedule_after_path": schedule["after"]["critical_path"],
        "migrated_ids": [m["claim_id"] for m in migrated],
        "migrate_errs": migrate_errs,
        "field_loss_ids": field_loss,
        "controls": {
            "no_settling_probe_rejected": any("settling_probe" in e for e in no_probe_errs),
            "duplicate_of_cycle_rejected": any("duplicate_of cycle" in e for e in cycle_errs),
            "ghost_contradiction_rejected": any("GHOST" in e for e in ghost_errs),
        },
        "cc0012_dependency": "SUCCESS",
        "success_invented": False,
        "independent_reviews_present": False,
    }

    (PROBE / "probe1-claim-record-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (PROBE / "schedule-recompute.json").write_text(
        json.dumps(schedule, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (PROBE / "migrated-three.json").write_text(
        json.dumps(
            {
                "schema_status": "PROVISIONAL",
                "superseded_by_unit": "ARC-0085",
                "claims": migrated,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    raw = (
        f"PROBE=CC-0017-claim-record\n"
        f"PYTEST_RC={proc.returncode}\n"
        f"PROVISIONAL={meta['schema_status']}\n"
        f"SUPERSEDED_BY={meta['superseded_by_unit']}\n"
        f"SCHEDULE_UNITS={schedule['schedule_claim_recomputed']['units_released']}\n"
        f"CRIT_BEFORE={schedule['schedule_claim_recomputed']['critical_path_before']}\n"
        f"CRIT_AFTER={schedule['schedule_claim_recomputed']['critical_path_after']}\n"
        f"MIGRATE_OK={not migrate_errs and not field_loss}\n"
        f"CONTROLS={json.dumps(summary['controls'])}\n"
        f"SUCCESS_INVENTED=false\n"
        f"INDEPENDENT_REVIEWS_PRESENT=false\n"
        f"PYTEST_TAIL=\n{pytest_out[-500:]}\n"
        f"VERDICT={'PASS' if summary['ok'] else 'FAIL'}\n"
    )
    (PROBE / "probe1-claim-record.raw.txt").write_text(raw, encoding="utf-8")
    print(raw)
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
