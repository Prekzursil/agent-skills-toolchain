"""Both-states and anti-tautology controls for the WFA-0073 evidence gate.

Direction A: strip evidence from a passing record -> gate FIRES.
Direction B: add a valid anchor to a failing record -> gate CLEARS.
A gate that only ever passes is indistinguishable from no gate.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gate  # noqa: E402

SMOKE_REL = "command-center/p2-wave/probes/WFA-0073/fixtures/smoke-pass.json"
PRES_REL = "command-center/p2-wave/probes/WFA-0073/fixtures/preserved-payload.txt"


def passing_adopt() -> dict[str, Any]:
    return {
        "id": "ctrl-adopt-pass",
        "classification": "ADOPT-AS-IS",
        "evidence": {
            "smoke_run": {
                "command": "PYTHONDONTWRITEBYTECODE=1 python3 -c 'print(\"smoke\")'",
                "exit_code": 0,
                "artifact": SMOKE_REL,
                "size_floor": 16,
            }
        },
    }


def failing_retire() -> dict[str, Any]:
    return {
        "id": "ctrl-retire-fail",
        "classification": "RETIRE",
        "evidence": {},
    }


def failing_unknown() -> dict[str, Any]:
    return {
        "id": "ctrl-unknown-fail",
        "classification": "UNKNOWN-NEEDS-PROBE",
        "evidence": {},
    }


def failing_translate() -> dict[str, Any]:
    return {
        "id": "ctrl-translate-fail",
        "classification": "TRANSLATE",
        "evidence": {},
    }


def valid_preservation() -> dict[str, Any]:
    path = gate.REPO / PRES_REL
    return {
        "location": PRES_REL,
        "content_sha256": gate.lf_sha256(path),
    }


def valid_probe() -> dict[str, Any]:
    return {
        "id": "probe-settle-ctrl-unknown",
        "command": "PYTHONDONTWRITEBYTECODE=1 python3 -c 'print(\"fired\")'",
        "executed": True,
        "result": "fired on known-broken control; healthy state silent",
        "both_states": {"fired_on_broken": True, "silent_on_healthy": True},
    }


def both_states() -> dict[str, Any]:
    good = passing_adopt()
    good_row = gate.evaluate_record(good)
    stripped = copy.deepcopy(good)
    stripped["id"] = "ctrl-adopt-stripped"
    stripped["evidence"] = {}
    stripped_row = gate.evaluate_record(stripped)

    bad = failing_retire()
    bad_row = gate.evaluate_record(bad)
    repaired = copy.deepcopy(bad)
    repaired["id"] = "ctrl-retire-repaired"
    repaired["evidence"] = {"preservation": valid_preservation()}
    repaired_row = gate.evaluate_record(repaired)

    fires_on_strip = (
        good_row["verdict"] == "PASS" and stripped_row["verdict"] == "FAIL"
    )
    clears_on_anchor = (
        bad_row["verdict"] == "FAIL" and repaired_row["verdict"] == "PASS"
    )
    return {
        "check": (
            "strip evidence from one passing record (gate fires); "
            "add a valid anchor to one failing record (gate clears)"
        ),
        "strip_passing": {
            "before": good_row,
            "after": stripped_row,
            "fires": stripped_row["verdict"] == "FAIL",
        },
        "add_anchor": {
            "before": bad_row,
            "after": repaired_row,
            "clears": repaired_row["verdict"] == "PASS",
            "anchor": "preservation-proof retrieval+hash-match",
        },
        "silent_on_good": good_row["verdict"] == "PASS",
        "fires_on_stripped": fires_on_strip,
        "clears_on_repaired": clears_on_anchor,
        "pass": bool(fires_on_strip and clears_on_anchor and good_row["ok"] and repaired_row["ok"]),
    }


def anti_tautology() -> dict[str, Any]:
    """Boolean ok:true / exit 0 / named-but-unrun must not count as evidence."""
    cases: list[dict[str, Any]] = []

    smoke_exit_only = copy.deepcopy(passing_adopt())
    smoke_exit_only["id"] = "ctrl-smoke-exit-only"
    smoke_exit_only["evidence"]["smoke_run"] = {
        "command": "true",
        "exit_code": 0,
    }
    r1 = gate.evaluate_record(smoke_exit_only)
    cases.append(
        {
            "id": smoke_exit_only["id"],
            "want": "FAIL",
            "got": r1["verdict"],
            "reason": r1["reason"],
            "ok": r1["verdict"] == "FAIL" and r1["reason"] == "smoke-run-artifact-path-absent",
        }
    )

    smoke_missing_file = copy.deepcopy(passing_adopt())
    smoke_missing_file["id"] = "ctrl-smoke-missing-file"
    smoke_missing_file["evidence"]["smoke_run"]["artifact"] = (
        "command-center/p2-wave/probes/WFA-0073/fixtures/does-not-exist.json"
    )
    r2 = gate.evaluate_record(smoke_missing_file)
    cases.append(
        {
            "id": smoke_missing_file["id"],
            "want": "FAIL",
            "got": r2["verdict"],
            "reason": r2["reason"],
            "ok": r2["verdict"] == "FAIL" and r2["reason"] == "smoke-run-artifact-missing-on-disk",
        }
    )

    pres_claim_only = failing_retire()
    pres_claim_only["id"] = "ctrl-pres-claim-only"
    pres_claim_only["evidence"] = {
        "preservation": {
            "location": "command-center/p2-wave/probes/WFA-0073/fixtures/does-not-exist.bin",
            "content_sha256": "0" * 64,
        }
    }
    r3 = gate.evaluate_record(pres_claim_only)
    cases.append(
        {
            "id": pres_claim_only["id"],
            "want": "FAIL",
            "got": r3["verdict"],
            "reason": r3["reason"],
            "ok": r3["verdict"] == "FAIL" and r3["reason"] == "preservation-location-unretrievable",
        }
    )

    named_unrun = failing_unknown()
    named_unrun["id"] = "ctrl-probe-named-unrun"
    named_unrun["evidence"] = {
        "probe": {"id": "would-settle", "command": "", "executed": False}
    }
    r4 = gate.evaluate_record(named_unrun)
    cases.append(
        {
            "id": named_unrun["id"],
            "want": "FAIL",
            "got": r4["verdict"],
            "reason": r4["reason"],
            "ok": r4["verdict"] == "FAIL",
        }
    )

    translate_empty = failing_translate()
    translate_empty["id"] = "ctrl-translate-empty"
    r5 = gate.evaluate_record(translate_empty)
    cases.append(
        {
            "id": translate_empty["id"],
            "want": "FAIL",
            "got": r5["verdict"],
            "reason": r5["reason"],
            "ok": r5["verdict"] == "FAIL" and r5["reason"] == "target-adapter-absent",
        }
    )

    unknown_clears = failing_unknown()
    unknown_clears["id"] = "ctrl-unknown-clears"
    unknown_clears["evidence"] = {"probe": valid_probe()}
    r6 = gate.evaluate_record(unknown_clears)
    cases.append(
        {
            "id": unknown_clears["id"],
            "want": "PASS",
            "got": r6["verdict"],
            "reason": r6["reason"],
            "ok": r6["verdict"] == "PASS",
        }
    )

    translate_clears = failing_translate()
    translate_clears["id"] = "ctrl-translate-clears"
    translate_clears["evidence"] = {"target_adapter": "adapter.claude-code-skill"}
    r7 = gate.evaluate_record(translate_clears)
    cases.append(
        {
            "id": translate_clears["id"],
            "want": "PASS",
            "got": r7["verdict"],
            "reason": r7["reason"],
            "ok": r7["verdict"] == "PASS",
        }
    )

    ungated = {"id": "ctrl-distill-ungated", "classification": "DISTILL", "evidence": {}}
    r8 = gate.evaluate_record(ungated)
    cases.append(
        {
            "id": ungated["id"],
            "want": "PASS",
            "got": r8["verdict"],
            "reason": r8["reason"],
            "ok": r8["verdict"] == "PASS" and r8["reason"] == "class-not-gated-by-WFA-0073",
        }
    )

    return {
        "n": len(cases),
        "n_ok": sum(1 for c in cases if c["ok"]),
        "cases": cases,
        "pass": all(c["ok"] for c in cases),
    }
