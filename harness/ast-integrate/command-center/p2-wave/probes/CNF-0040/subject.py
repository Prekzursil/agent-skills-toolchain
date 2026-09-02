"""IMP-0136 verification subject, run under a granted permission set.

Honest path: any deny is a loud failure naming the missing tool; success is
reported only after the spawn-count transcript is written.

Silent-degradation mutant: when Write is denied, skip the transcript and still
report ok=True with no degraded mark. probe2 must fire on that mutant.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from choke import Gate, OverPrivileged, PermissionDenied
import catalog_perms as C

OVERPRIV_REQUEST = ["Read", "Bash", "Network"]
COMPLIANT_REQUEST = ["Read", "Bash"]


def _run_body(gate: Gate, declared: list[str], scratch: Path, silent: bool) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": False,
        "exit_code": 1,
        "error_text": "",
        "classification": "unexplained",
        "spawns_overpriv": None,
        "spawns_compliant": None,
        "transcript_written": False,
        "artifact_marked_degraded": False,
        "permission_set": sorted(gate.granted),
        "tools_requested": [],
        "unused_declared": [],
        "overpriv_rejected_before_spawn": False,
        "mode": "silent-mutant" if silent else "honest",
    }
    try:
        gate.require("Read")
        text = C.CATALOG.read_text(encoding="utf-8")
        if '"id": "IMP-0136"' not in text and '"id":"IMP-0136"' not in text:
            result["error_text"] = "catalog does not contain IMP-0136"
            result["classification"] = "loud-deny"
            result["tools_requested"] = list(gate.requested)
            return result

        gate.require("Grep")
        if "tool_permissions" not in text:
            result["error_text"] = "Grep: catalog lacks tool_permissions"
            result["classification"] = "loud-deny"
            result["tools_requested"] = list(gate.requested)
            return result

        gate.require("Glob")
        list((C.REPO / "tools").glob("**/*"))

        before = gate.spawns
        try:
            gate.dispatch(OVERPRIV_REQUEST, declared)
            result["error_text"] = "over-privileged unit was allowed to spawn"
            result["classification"] = "unexplained"
            result["spawns_overpriv"] = gate.spawns - before
            result["tools_requested"] = list(gate.requested)
            return result
        except OverPrivileged as exc:
            result["spawns_overpriv"] = exc.spawns - before
            result["overpriv_rejected_before_spawn"] = exc.spawns == before

        before_ok = gate.spawns
        gate.dispatch(COMPLIANT_REQUEST, declared)
        result["spawns_compliant"] = gate.spawns - before_ok

        transcript = {
            "spawns_overpriv": result["spawns_overpriv"],
            "spawns_compliant": result["spawns_compliant"],
            "declared": list(declared),
        }
        if silent:
            allowed = gate.try_require("Write")
            if allowed:
                scratch.mkdir(parents=True, exist_ok=True)
                (scratch / "spawn-transcript.json").write_text(
                    json.dumps(transcript, sort_keys=True) + "\n", encoding="utf-8"
                )
                result["transcript_written"] = True
            result["ok"] = True
            result["exit_code"] = 0
            result["classification"] = "pass" if allowed else "silent-degradation"
            result["artifact_marked_degraded"] = False
        else:
            gate.require("Write")
            scratch.mkdir(parents=True, exist_ok=True)
            (scratch / "spawn-transcript.json").write_text(
                json.dumps(transcript, sort_keys=True) + "\n", encoding="utf-8"
            )
            result["transcript_written"] = True
            if result["spawns_overpriv"] != 0 or result["spawns_compliant"] != 1:
                result["error_text"] = (
                    f"spawn counts overpriv={result['spawns_overpriv']} "
                    f"compliant={result['spawns_compliant']}"
                )
                result["classification"] = "unexplained"
                result["ok"] = False
                result["exit_code"] = 1
            elif not result["overpriv_rejected_before_spawn"]:
                result["error_text"] = "over-privileged rejection was not pre-spawn"
                result["classification"] = "unexplained"
                result["ok"] = False
                result["exit_code"] = 1
            else:
                result["ok"] = True
                result["exit_code"] = 0
                result["classification"] = "pass"
    except PermissionDenied as exc:
        result["error_text"] = exc.message
        result["classification"] = "loud-deny"
        result["ok"] = False
        result["exit_code"] = 2
        result["spawns_overpriv"] = result["spawns_overpriv"]
        result["spawns_compliant"] = result["spawns_compliant"]

    requested = list(dict.fromkeys(gate.requested))
    result["tools_requested"] = requested
    result["unused_declared"] = sorted(set(declared) - set(requested))
    return result


def verify_honest(granted: list[str], declared: list[str], scratch: Path) -> dict[str, Any]:
    return _run_body(Gate(granted), declared, scratch, silent=False)


def verify_silent(granted: list[str], declared: list[str], scratch: Path) -> dict[str, Any]:
    return _run_body(Gate(granted), declared, scratch, silent=True)


def post_spawn_mutant_overpriv(granted: list[str], declared: list[str]) -> dict[str, Any]:
    """IMP-0136 mutation: move the check after spawn; zero-spawn assertion goes red."""
    gate = Gate(granted)
    gate.require("Read")
    gate.require("Grep")
    gate.require("Glob")
    try:
        gate.dispatch_after_spawn(OVERPRIV_REQUEST, declared)
        raised = False
        spawns = gate.spawns
        error = "mutant allowed over-privileged dispatch"
    except OverPrivileged as exc:
        raised = True
        spawns = exc.spawns
        error = exc.message
    except PermissionDenied as exc:
        return {
            "zero_spawn_assertion_holds": False,
            "spawns": 0,
            "raised": False,
            "error_text": exc.message,
            "detector_red": False,
        }
    zero_holds = spawns == 0
    return {
        "zero_spawn_assertion_holds": zero_holds,
        "spawns": spawns,
        "raised": raised,
        "error_text": error,
        "detector_red": (not zero_holds) and spawns >= 1,
    }


def run_pair(declared: list[str], scratch: Path) -> dict[str, Any]:
    reduced_grant = list(declared)
    full = C.full_grant(declared)
    reduced = verify_honest(reduced_grant, declared, scratch / "reduced")
    full_run = verify_honest(full, declared, scratch / "full")
    if reduced["ok"] and full_run["ok"]:
        relation = "explained"
        explanation = (
            "Both the reduced (declared) grant and the full-grant control passed. "
            "The verification only requests tools that are already in the "
            "declared set; extra tools in the full grant were unused."
        )
    elif (not reduced["ok"]) and full_run["ok"]:
        relation = "differ"
        explanation = (
            "Reduced grant failed and the full-grant control passed, isolating "
            "permissions as the variable."
        )
    else:
        relation = "differ-and-explained"
        explanation = (
            f"reduced ok={reduced['ok']} class={reduced['classification']}; "
            f"full ok={full_run['ok']} class={full_run['classification']}"
        )
    return {
        "reduced": reduced,
        "full": full_run,
        "reduced_grant": reduced_grant,
        "full_grant": full,
        "outcomes_relation": relation,
        "explanation": explanation,
    }
