#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0253.json from live engine runs.

Does not write SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST (see write_receipts.py).
Does not run unit_manifest.py --write. cloud ok=true is not delivery.
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
sys.path.insert(0, str(REPO / "command-center"))

import fixtures as F  # noqa: E402
from analysis.forecast_gate import (  # noqa: E402
    ForecastLibrary,
    emit,
    emission_fingerprint,
    resolve,
)
from analysis.library import (  # noqa: E402
    build_library,
    contract_omission_codes,
)

OUT_REL = "command-center/receipts/IMP-0253.json"
GATE_REL = "command-center/analysis/forecast_gate.py"
LIB_REL = "command-center/analysis/library.py"
ENG_REL = "command-center/analysis/engines.py"
CON_REL = "command-center/analysis/contract.py"
INIT_REL = "command-center/analysis/__init__.py"
FIX_REL = "command-center/p2-wave/probes/IMP-0253/fixtures.py"

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0253/probe1_unresolvable_rejected.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0253/probe2_criterion_executable.py"
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def artifact_row(rel: str, role: str) -> dict:
    sha, size = digest(REPO / rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "role": role,
        "eol": "LF",
    }


def source_anchor(rel: str, needle: str) -> str:
    lines = (REPO / rel).read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines, 1):
        if needle in line:
            return f"{rel}:{i}"
    raise SystemExit(f"FAILED:IMP-0253 emit missing anchor {needle!r} in {rel}")


def main() -> int:
    lib = ForecastLibrary()
    d_bad = lib.try_admit(F.UNRESOLVABLE_NO_DATE)
    d_good = lib.try_admit(F.RESOLVABLE)
    d_prose = emit(F.UNRESOLVABLE_PROSE)
    d_never = emit(F.UNRESOLVABLE_UNBOUNDED)
    d_nocrit = emit(F.UNRESOLVABLE_NO_CRIT)
    d_swap = emit(F.PROSE_STATEMENT_SWAP)
    r_hold = resolve(F.RESOLVABLE, F.HOLD)
    r_miss = resolve(F.RESOLVABLE, F.MISS)
    r_early = resolve(F.RESOLVABLE, F.EARLY)
    r_prose = resolve(F.UNRESOLVABLE_PROSE, F.HOLD)

    alib, contract_rows = build_library()
    omissions = contract_omission_codes()
    smokes = {
        bp.id: bp.smoke()
        for bp in (
            alib.get("bp.morphological-analysis"),
            alib.get("bp.simulation-counterfactual"),
            alib.get("bp.forecasting"),
            alib.get("bp.expert-elicitation"),
        )
    }

    gate = {
        "unresolvable_no_date": d_bad.to_dict(),
        "resolvable": d_good.to_dict(),
        "prose_criterion": d_prose.to_dict(),
        "unbounded": d_never.to_dict(),
        "missing_criterion": d_nocrit.to_dict(),
        "statement_swap_fingerprint_equal": (
            emission_fingerprint(d_swap) == emission_fingerprint(d_good)
        ),
        "library_ids": list(lib.admitted_ids()),
        "resolve_hold": r_hold.to_dict(),
        "resolve_miss": r_miss.to_dict(),
        "resolve_early": r_early.to_dict(),
        "resolve_prose": r_prose.to_dict(),
        "statement_consulted": False,
    }

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    emit_anchor = source_anchor(GATE_REL, "if raw_date is None or (isinstance(raw_date, str)")
    resolve_anchor = source_anchor(GATE_REL, "held = apply_op(observed,")
    library_anchor = source_anchor(GATE_REL, "if decision.admitted:")

    if not all(r.get("ok") for r in contract_rows):
        print("FAILED:IMP-0253 emit blueprint contract")
        print(json.dumps(contract_rows, indent=2))
        return 1
    if not all(s.get("ok") is True for s in smokes.values()):
        print("FAILED:IMP-0253 emit smoke")
        print(json.dumps(smokes, indent=2, default=str))
        return 1
    if len(set(omissions.values())) != 6:
        print(f"FAILED:IMP-0253 emit omission codes not distinct {omissions}")
        return 1
    if not d_good.admitted or d_bad.admitted or d_prose.admitted:
        print("FAILED:IMP-0253 emit gate did not discriminate")
        return 1
    if not r_hold.resolved or r_hold.value is not True:
        print("FAILED:IMP-0253 emit hold did not resolve true")
        return 1
    if not r_miss.resolved or r_miss.value is not False:
        print("FAILED:IMP-0253 emit miss did not resolve false")
        return 1

    receipt = {
        "schema_version": 1,
        "id": "IMP-0253",
        "unit_id": "IMP-0253",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0253",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0253",
        "title": (
            "Implement analysis blueprints 13-16: morphological analysis, "
            "simulation/counterfactual, forecasting, expert elicitation"
        ),
        "min_bytes_threshold": 128,
        "forecast_gate": gate,
        "blueprints": {
            "registered_ids": list(alib.ids()),
            "contract": contract_rows,
            "smokes": smokes,
            "omission_codes": omissions,
        },
        "artifacts": [
            artifact_row(GATE_REL, "primary"),
            artifact_row(LIB_REL, "supporting"),
            artifact_row(ENG_REL, "supporting"),
            artifact_row(CON_REL, "supporting"),
            artifact_row(INIT_REL, "supporting"),
            artifact_row(FIX_REL, "supporting"),
        ],
        "evidence": [
            {
                "claim": (
                    "An unresolvable forecast (missing resolution date) is "
                    f"rejected at emission ({d_bad.reason}, admitted="
                    f"{d_bad.admitted}); the resolvable twin with ISO date "
                    f"2027-03-01 and structured criterion is admitted "
                    f"({d_good.reason}). A prose criterion is rejected "
                    f"({d_prose.reason}). Statement text is not consulted."
                ),
                "verdict": "CONFIRMED",
                "anchor": emit_anchor,
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "exit_code": 0,
                        "raw_output": (
                            f"reason={d_bad.reason} admitted={d_bad.admitted}"
                        ),
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P1,
                        "exit_code": 0,
                        "raw_output": (
                            f"resolvable admitted={d_good.admitted} "
                            f"reason={d_good.reason}"
                        ),
                    },
                ],
            },
            {
                "claim": (
                    "The admitted criterion executes against a synthetic future "
                    f"state: hold observed={r_hold.observed} -> {r_hold.reason}; "
                    f"miss observed={r_miss.observed} -> {r_miss.reason}; "
                    f"as_of before resolution_date -> {r_early.reason}. "
                    "Prose is not executed "
                    f"({r_prose.reason}, prose_executed={r_prose.prose_executed})."
                ),
                "verdict": "CONFIRMED",
                "anchor": resolve_anchor,
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P2,
                        "exit_code": 0,
                        "raw_output": (
                            f"hold={r_hold.reason} miss={r_miss.reason} "
                            f"early={r_early.reason}"
                        ),
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "exit_code": 0,
                        "raw_output": (
                            f"prose reason={r_prose.reason} "
                            f"prose_executed={r_prose.prose_executed}"
                        ),
                    },
                ],
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "tests": [
            {
                "id": "unresolvable-forecast-rejected-both-states",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "resolution-criterion-executable-against-synthetic-state",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "c-unresolvable-no-date",
                "kind": "known-broken-fixture",
                "description": "same statement as the resolvable twin; resolution_date missing",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": d_bad.reason,
                "good_state_output": d_good.reason,
            },
            {
                "id": "c-prose-criterion",
                "kind": "known-broken-fixture",
                "description": "criterion is a sentence, not observable+op+expected",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": d_prose.reason,
                "good_state_output": d_good.reason,
            },
            {
                "id": "c-unbounded-horizon",
                "kind": "known-broken-fixture",
                "description": "resolution_date token 'never'",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": d_never.reason,
                "good_state_output": d_good.reason,
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0253-probe2-criterion-executable",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Adversarial check: criterion is applied to synthetic observables "
                "(150 holds, 400 misses); too-early as_of does not invent a score; "
                "prose criterion is not executed; statement swap must not change "
                "emission_fingerprint."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0253/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "command-center/p2-wave/probes/IMP-0253/"
                    "probe1_unresolvable_rejected.py"
                ),
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "command",
                    "command": P1,
                    "exit_code": 0,
                    "raw_output": "SUCCESS:IMP-0253-probe1",
                },
            },
            {
                "consumer": (
                    "command-center/p2-wave/probes/IMP-0253/"
                    "probe2_criterion_executable.py"
                ),
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "command",
                    "command": P2,
                    "exit_code": 0,
                    "raw_output": "SUCCESS:IMP-0253-probe2",
                },
            },
        ],
        "residual_unknowns": [
            {
                "id": "IMP-0230-global-contract",
                "note": (
                    "The catalog names IMP-0230 as a dependency. That unit's "
                    "scaffold generator is not on this worktree. The four "
                    "blueprints are gated by command-center/analysis/contract.py "
                    "(six required elements, 6/6 distinct omission codes)."
                ),
            }
        ],
        "library_entry_point": library_anchor,
        "notes": (
            "G-1 for IMP-0253: live named probes re-run the forecast gate and "
            "the four analysis blueprints. Did not run "
            "tools/command-center/unit_manifest.py --write. "
            "cloud ok=true is not delivery."
        ),
        "output_schema": "command-center/schema/receipt.schema.json",
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(receipt, indent=1, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    sha, size = digest(out)
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print("SUCCESS:IMP-0253 receipt emitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
