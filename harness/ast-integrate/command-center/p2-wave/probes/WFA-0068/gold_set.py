"""20-record disposition gold set spanning 9 families and all 15 vocabulary values.

Sampling rule (written before construction, frozen as gold_set.version=1):
  1. At least one record from each family A–I.
  2. At least one positive example of each of the 15 dispositions.
  3. Exactly one record whose required input is deliberately omitted (refusal path).
  4. Extra slots go to ADOPT-AS-IS, DISTILL, RETIRE, REPAIR, UNKNOWN-NEEDS-PROBE
     (the histogram-heavy and refusal classes), never used to hide a rare class.

WFA-0042's extraction gold set is absent on this tree; this set is the
disposition-labelled scoring corpus for WFA-0068. Family identifiers match
the 284-candidate registry families named in WFA-0042.
"""
from __future__ import annotations

from vocabulary import FAMILIES, VOCABULARY

GOLD_VERSION = 1
SAMPLING_RULE = (
    "Before selection: cover all 9 families A-I; cover all 15 dispositions; "
    "include exactly one deliberate missing-required-input record; freeze "
    "version=1; later edits require a version bump."
)


def _complete(overrides: dict) -> dict:
    rec = {
        "extraction_complete": True,
        "license": "MIT",
        "maintenance": "active",
        "provenance": "git:07f465f3:path",
        "runtime": "claude-code",
        "mechanisms": ["gate", "retry"],
        "stages_state": "EVIDENCED",
        "roles_state": "EVIDENCED",
        "tools_state": "EVIDENCED",
        "stop_rules_state": "EVIDENCED",
        "task_fit_state": "EVIDENCED",
        "failure_behaviour_state": "HONEST-NULL",
        "benchmark_evidence_state": "HONEST-NULL",
        "fitness": "fit",
        "safety": "ok",
        "lifecycle": "active",
        "source_state": "present",
        "reimplementable": False,
        "spec_present": False,
        "compose_of": [],
        "duplicate_of": "",
        "specificity": "matched",
        "gaps": [],
        "defects": [],
        "core_intact": True,
        "salvageable": False,
        "take_whole": True,
        "mechanism_worth_keeping": False,
        "needs_wrapper": False,
        "smoke_passes": True,
        "probe_needed": False,
    }
    rec.update(overrides)
    return rec


def gold_records() -> list[dict]:
    return [
        _complete(
            {
                "id": "GOLD-01",
                "family": "A-saved-workflow",
                "gold": "ADOPT-AS-IS",
                "smoke_passes": True,
                "runtime": "claude-code",
            }
        ),
        _complete(
            {
                "id": "GOLD-02",
                "family": "B-repo-workflow",
                "gold": "ADOPT-WITH-WRAPPER",
                "needs_wrapper": True,
                "runtime": "claude-code",
                "smoke_passes": False,
            }
        ),
        _complete(
            {
                "id": "GOLD-03",
                "family": "C-repo-tool",
                "gold": "DISTILL",
                "take_whole": False,
                "mechanism_worth_keeping": True,
                "smoke_passes": False,
            }
        ),
        _complete(
            {
                "id": "GOLD-04",
                "family": "D-harness-runtime",
                "gold": "RETIRE",
                "lifecycle": "retired",
                "source_state": "deleted",
                "smoke_passes": False,
            }
        ),
        _complete(
            {
                "id": "GOLD-05",
                "family": "E-agent",
                "gold": "REPAIR",
                "defects": ["broken-gate"],
                "salvageable": True,
                "smoke_passes": False,
            }
        ),
        _complete(
            {
                "id": "GOLD-06",
                "family": "F-plugin",
                "gold": "EXTEND",
                "gaps": ["missing-stop-rule"],
                "core_intact": True,
                "smoke_passes": False,
            }
        ),
        _complete(
            {
                "id": "GOLD-07",
                "family": "G-skill",
                "gold": "MERGE",
                "duplicate_of": "GOLD-17",
                "smoke_passes": False,
            }
        ),
        _complete(
            {
                "id": "GOLD-08",
                "family": "H-executed-corpus",
                "gold": "SPECIALIZE",
                "specificity": "too-broad",
                "smoke_passes": False,
            }
        ),
        _complete(
            {
                "id": "GOLD-09",
                "family": "I-command",
                "gold": "UNKNOWN-NEEDS-PROBE",
                "license": "EMPTY",
                "extraction_complete": True,
                "refusal": True,
                "missing_field": "license",
                "smoke_passes": False,
            }
        ),
        _complete(
            {
                "id": "GOLD-10",
                "family": "G-skill",
                "gold": "CLEAN-ROOM-REIMPLEMENT",
                "license": "UNLICENSED",
                "reimplementable": True,
                "smoke_passes": False,
            }
        ),
        _complete(
            {
                "id": "GOLD-11",
                "family": "A-saved-workflow",
                "gold": "COMPOSE",
                "compose_of": ["GOLD-01", "GOLD-02"],
                "smoke_passes": False,
            }
        ),
        _complete(
            {
                "id": "GOLD-12",
                "family": "C-repo-tool",
                "gold": "GENERALIZE",
                "specificity": "too-narrow",
                "smoke_passes": False,
            }
        ),
        _complete(
            {
                "id": "GOLD-13",
                "family": "E-agent",
                "gold": "REBUILD-FROM-SPEC",
                "source_state": "unusable",
                "spec_present": True,
                "smoke_passes": False,
            }
        ),
        _complete(
            {
                "id": "GOLD-14",
                "family": "F-plugin",
                "gold": "REJECT",
                "fitness": "unfit",
                "safety": "hostile",
                "smoke_passes": False,
            }
        ),
        _complete(
            {
                "id": "GOLD-15",
                "family": "B-repo-workflow",
                "gold": "TRANSLATE",
                "runtime": "n8n",
                "license": "MIT",
                "smoke_passes": False,
            }
        ),
        _complete(
            {
                "id": "GOLD-16",
                "family": "I-command",
                "gold": "ADOPT-AS-IS",
                "runtime": "claude-workflows",
                "smoke_passes": True,
            }
        ),
        _complete(
            {
                "id": "GOLD-17",
                "family": "G-skill",
                "gold": "DISTILL",
                "take_whole": False,
                "mechanism_worth_keeping": True,
                "smoke_passes": False,
            }
        ),
        _complete(
            {
                "id": "GOLD-18",
                "family": "H-executed-corpus",
                "gold": "RETIRE",
                "lifecycle": "retired",
                "smoke_passes": False,
            }
        ),
        _complete(
            {
                "id": "GOLD-19",
                "family": "G-skill",
                "gold": "UNKNOWN-NEEDS-PROBE",
                "probe_needed": True,
                "refusal": False,
                "smoke_passes": False,
            }
        ),
        _complete(
            {
                "id": "GOLD-20",
                "family": "A-saved-workflow",
                "gold": "REPAIR",
                "defects": ["nondeterministic-date"],
                "salvageable": True,
                "smoke_passes": False,
            }
        ),
    ]


def overlap_reject_retire() -> dict:
    """Two rules fire (REJECT and RETIRE). Total order must pick REJECT (rank 1)."""
    return _complete(
        {
            "id": "OVERLAP-REJECT-RETIRE",
            "family": "C-repo-tool",
            "gold": "REJECT",
            "fitness": "unfit",
            "lifecycle": "retired",
            "smoke_passes": False,
        }
    )


def overlap_repair_extend() -> dict:
    """REPAIR (defects) and would-be EXTEND (gaps). Repair rank wins if both match.

    EXTEND requires empty defects, so this pair is defects+gaps: only REPAIR
    fires. Used as a negative that EXTEND does not steal a repair.
    """
    return _complete(
        {
            "id": "OVERLAP-REPAIR-GAPS",
            "family": "E-agent",
            "gold": "REPAIR",
            "defects": ["broken-gate"],
            "gaps": ["missing-stop-rule"],
            "salvageable": True,
            "core_intact": True,
            "smoke_passes": False,
        }
    )


def restored_license_adopt() -> dict:
    """GOLD-09 with license restored: both-states complement of the refusal path."""
    rec = [r for r in gold_records() if r["id"] == "GOLD-09"][0].copy()
    rec["license"] = "MIT"
    rec["smoke_passes"] = True
    rec["gold"] = "ADOPT-AS-IS"
    rec["refusal"] = False
    rec.pop("missing_field", None)
    rec["id"] = "GOLD-09-RESTORED"
    return rec


def family_coverage(records: list[dict] | None = None) -> dict:
    rows = records if records is not None else gold_records()
    seen = {r["family"] for r in rows}
    return {
        "required": list(FAMILIES),
        "seen": sorted(seen),
        "missing": [f for f in FAMILIES if f not in seen],
        "complete": set(FAMILIES) <= seen,
    }


def disposition_coverage(records: list[dict] | None = None) -> dict:
    rows = records if records is not None else gold_records()
    counts: dict[str, int] = {v: 0 for v in VOCABULARY}
    for r in rows:
        counts[str(r["gold"])] = counts.get(str(r["gold"]), 0) + 1
    missing = [v for v, n in counts.items() if n < 1]
    return {
        "counts": counts,
        "missing": missing,
        "complete": not missing,
        "n": len(rows),
    }


def assert_gold_invariants() -> None:
    rows = gold_records()
    if len(rows) != 20:
        raise AssertionError(f"gold n={len(rows)} want 20")
    fam = family_coverage(rows)
    if not fam["complete"]:
        raise AssertionError(f"family coverage missing {fam['missing']}")
    disp = disposition_coverage(rows)
    if not disp["complete"]:
        raise AssertionError(f"disposition coverage missing {disp['missing']}")
    refusals = [r for r in rows if r.get("refusal") is True]
    if len(refusals) != 1:
        raise AssertionError(f"want exactly 1 refusal record, got {len(refusals)}")
    if refusals[0]["id"] != "GOLD-09":
        raise AssertionError("refusal record must be GOLD-09")
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise AssertionError("duplicate gold ids")
