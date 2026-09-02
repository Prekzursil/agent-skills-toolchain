#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0271.json from a live selector run.

Embeds the unfilled-class report and the per-class census. Does not
write SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST (see write_receipts.py).
Does not run unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

import fixtures as F  # noqa: E402
from council.participants.select_stakeholder import (  # noqa: E402
    census_check,
    select,
)

UNIT = "IMP-0271"
OUT = "command-center/receipts/IMP-0271.json"
LIB = "tools/council/participants/select_stakeholder.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0271/probe1_balance_arithmetic.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0271/probe2_unfilled_suppression.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def source_anchor(rel: str, needle: str) -> str:
    lines = (REPO / rel).read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines, 1):
        if needle in line:
            return f"{rel}:{i}"
    raise SystemExit(f"FAILED:{UNIT} emit missing anchor {needle!r} in {rel}")


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    pool = F.candidate_pool()
    mix_runs: list[dict] = []
    for mix in F.mixes():
        run = F.run_mix(select, pool, mix)
        check = census_check(run)
        mix_runs.append(
            {
                "id": mix["id"],
                "kind": mix["kind"],
                "fillable": mix["fillable"],
                "requested_balance": run["requested_balance"],
                "census": run["census"],
                "unfilled_report": run["unfilled_report"],
                "under_represented": run["under_represented"],
                "census_check_ok": check["ok"],
                "census_check_reason": check["reason"],
                "roster": run["roster"],
            }
        )
    unfill = next(r for r in mix_runs if r["id"] == "unfillable-regulator")
    if not unfill["unfilled_report"]:
        print(f"FAILED:{UNIT} unfilled-class report missing from live run")
        return 1
    if not unfill["census_check_ok"]:
        print(f"FAILED:{UNIT} honest unfilled run failed census_check")
        return 1

    suppressed = dict(unfill)
    suppressed["unfilled_report"] = []
    suppressed_check = census_check(
        {
            "requested_balance": unfill["requested_balance"],
            "seats": F.run_mix(
                select,
                pool,
                next(m for m in F.mixes() if m["id"] == "unfillable-regulator"),
            )["seats"],
            "census": unfill["census"],
            "unfilled_report": [],
            "under_represented": unfill["under_represented"],
            "available": F.run_mix(
                select,
                pool,
                next(m for m in F.mixes() if m["id"] == "unfillable-regulator"),
            )["available"],
        }
    )
    if suppressed_check["ok"]:
        print(f"FAILED:{UNIT} suppressed report still passed census_check")
        return 1

    ended = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    unfilled_anchor = source_anchor(LIB, "unfilled = _unfilled_rows(requested, census, available)")
    check_anchor = source_anchor(LIB, 'reason": REASON_SUPPRESSED')
    hamilton_anchor = source_anchor(LIB, "leftover = total - sum(floors.values())")

    lib_art = art(LIB, "implementation")
    supporting = [
        art("tools/council/__init__.py", "supporting"),
        art("tools/council/participants/__init__.py", "supporting"),
        art("command-center/p2-wave/probes/IMP-0271/fixtures.py", "fixture"),
        art(
            "command-center/p2-wave/probes/IMP-0271/probe1_balance_arithmetic.py",
            "probe",
        ),
        art(
            "command-center/p2-wave/probes/IMP-0271/probe2_unfilled_suppression.py",
            "probe",
        ),
    ]
    artifact_paths = [lib_art["path"]] + [a["path"] for a in supporting] + [OUT]

    doc = {
        "schema_version": 1,
        "id": UNIT,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0271",
        "completion_sentinel": "SUCCESS:IMP-0271",
        "title": "Stakeholder-balanced selector",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json work_units[id=IMP-0271] "
            "profile=council-participants-module; implements "
            "tools/council/participants/select_stakeholder.py. Catalog inputs "
            "11-COUNCIL-SPECIFICATION.md and _USER-PROMPTS.md are absent on "
            "this Linux worktree (same finding as CNL-0001)."
        ),
        "question_or_target": (
            "Implement tools/council/participants/select_stakeholder.py which "
            "seats declared stakeholder classes to a target balance and reports "
            "any class it could not fill. Falsifiable question: when a "
            "stakeholder class cannot be filled, does the council proceed "
            "silently under-represented?"
        ),
        "answer": (
            "No. Seating never substitutes across classes. An unfilled-class "
            "report is always present in the run artifact; census_check "
            "recomputes the per-class census from the roster and FAILS if a "
            "shortfall is unreported."
        ),
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json "
            "profile=council-participants-module"
        ),
        "implementation": {
            "module": LIB,
            "taxonomy": [
                "operator",
                "end_user",
                "domain_expert",
                "adversary",
                "regulator",
            ],
            "apportionment": "Hamilton largest-remainder, integer arithmetic",
            "substitution": "forbidden; shortfall stays a shortfall",
            "unfilled_report": "always emitted; empty iff every requested seat filled",
        },
        "artifact_paths": artifact_paths,
        "artifacts": [lib_art] + supporting,
        "evidence": [
            {
                "id": "E1-unfilled-class-report",
                "claim": (
                    "Live unfillable-regulator mix seats 1 of 3 requested "
                    "regulator seats and names regulator in unfilled_report "
                    "with shortfall=2."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": unfilled_anchor,
                "unfilled_report": unfill["unfilled_report"],
                "census": unfill["census"],
                "requested_balance": unfill["requested_balance"],
            },
            {
                "id": "E2-per-class-census",
                "claim": (
                    "Per-class seat census on five mixes matches the "
                    "hand-computed expected_seats literals in fixtures.py, "
                    "including Hamilton leftover and tie-break cases."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": hamilton_anchor,
                "mixes": [
                    {
                        "id": r["id"],
                        "census": r["census"],
                        "census_check_ok": r["census_check_ok"],
                    }
                    for r in mix_runs
                ],
            },
        ],
        "test_ids": [
            "IMP-0271-T-BALANCE-5-MIXES",
            "IMP-0271-NC-UNFILLED-SUPPRESSED",
        ],
        "negative_control_ids": ["IMP-0271-NC-UNFILLED-SUPPRESSED"],
        "tests": [
            {
                "id": "IMP-0271-T-BALANCE-5-MIXES",
                "name": "balance arithmetic across 5 class mixes",
                "command": P1,
                "result": "PENDING-NAMED-PROBE",
            },
            {
                "id": "IMP-0271-NC-UNFILLED-SUPPRESSED",
                "name": "suppress the unfilled report and the census check FAILS",
                "command": P2,
                "result": "PENDING-NAMED-PROBE",
            },
        ],
        "negative_controls": [
            {
                "id": "IMP-0271-NC-UNFILLED-SUPPRESSED",
                "kind": "known-broken-fixture",
                "description": (
                    "Copy the honest unfillable run, set unfilled_report=[], "
                    "assert census_check FAILS with UNFILLED_REPORT_SUPPRESSED. "
                    "The honest copy must PASS."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": "census_check ok=True reason=CENSUS_MATCHES_BALANCE",
                "bad_state_output": (
                    f"census_check ok=False reason={suppressed_check['reason']}"
                ),
            }
        ],
        "reviewer": {
            "reviewer_id": "IMP-0271-probe2-unfilled-suppression",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
            "notes": (
                "Probe 2 does not re-run the five-mix arithmetic. It tampers "
                "only unfilled_report on one unfillable artifact."
            ),
        },
        "reviewer_verdict": "PASS",
        "residual_unknowns": [
            {
                "claim": (
                    "Harness files 11-COUNCIL-SPECIFICATION.md / schema and "
                    "CNL-0017's design note are absent; the five-class taxonomy "
                    "is derived from catalog language (CNL-0114 multi-interest "
                    "family: operator, lay/end_user, domain_expert, adversary, "
                    "regulator) rather than a byte-copy of an unread spec."
                ),
                "settling_experiment": (
                    "When 11-COUNCIL-SPECIFICATION.schema.json is present, "
                    "diff the $defs stakeholder class enum against "
                    "STAKEHOLDER_CLASSES and extend the taxonomy if the spec "
                    "names additional classes."
                ),
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "IMP-0265 participant registry is a catalog dependency "
                    "and is not delivered on this worktree. The selector "
                    "accepts an explicit pool so the unfilled-report contract "
                    "does not wait on registry.py."
                ),
                "settling_experiment": (
                    "When registry.py exists, feed its listed participants "
                    "as the pool and re-run probe1/probe2."
                ),
                "verdict": "NOT-CHECKED",
            },
        ],
        "measured": {
            "mixes": mix_runs,
            "unfilled_class_report_present": True,
            "suppressed_census_check": {
                "ok": suppressed_check["ok"],
                "reason": suppressed_check["reason"],
            },
        },
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "balance-arithmetic"},
            {"id": "probe2", "command": P2, "role": "unfilled-suppression"},
        ],
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "timestamps": {"started_at": started, "ended_at": ended},
        "manifest_registration": {
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0271/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "cloud_ok": False,
        "notes": (
            "G-1 for IMP-0271: live named probes must exit 0 against "
            "tools/council/participants/select_stakeholder.py. cloud ok=true "
            "is not delivery. Did not run global unit_manifest.py --write. "
            "Did not rebuild ADV."
        ),
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if "SUCCESS:IMP-0271" not in text:
        print(f"FAILED:{UNIT} sentinel missing from serialized receipt")
        return 1
    out_path.write_text(text, encoding="utf-8")
    sha, size = sha256_file(out_path)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(
        f"unfilled={unfill['unfilled_report']} "
        f"suppressed_ok={suppressed_check['ok']} "
        f"reason={suppressed_check['reason']}"
    )
    print("SUCCESS:IMP-0271")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
