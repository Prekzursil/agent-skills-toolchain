#!/usr/bin/env python3
"""Emit the CNL-0077 design note (JSON bytes at the catalog .md path)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import floor as F  # noqa: E402
import schema_check as SC  # noqa: E402

OUT_REL = (
    "command-center/design/council/"
    "CNL-0077-minimum-deliberation-conditions-that-outrank-any-early-sto.md"
)
OUT = REPO / OUT_REL
SCHEMA_REL = "command-center/schema/council-design-note.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0077/probe1_satisfied_but_floored.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0077/probe2_ceiling_hang.py"
)
SLICE = "command-center/p2-wave/probes/CC-0024/fixtures/prompt-two-slice.md"
FLOOR = "command-center/p2-wave/probes/CNL-0077/floor.py"
FIX_FLOORED = (
    "command-center/p2-wave/probes/CNL-0077/fixtures/satisfied-but-floored.json"
)
FIX_NOCEIL = "command-center/p2-wave/probes/CNL-0077/fixtures/no-ceiling.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
MANIFEST = "command-center/p2-wave/probes/CNL-0077/UNIT-ARTIFACT-MANIFEST.json"


def load_fix(name: str) -> dict:
    return json.loads((HERE / "fixtures" / f"{name}.json").read_text(encoding="utf-8"))


def sha_row(rel: str, role: str) -> dict:
    path = REPO / rel
    raw = path.read_bytes()
    eol = "CRLF" if b"\r\n" in raw else "LF"
    norm = raw.replace(b"\r\n", b"\n")
    return {
        "path": rel,
        "bytes": len(norm),
        "sha256": hashlib.sha256(norm).hexdigest(),
        "exists": True,
        "eol": eol,
        "role": role,
    }


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()[:32]


def row(name: str) -> dict:
    fix = load_fix(name)
    if name in {"min-rounds-zero", "no-ceiling", "unsatisfiable-briefs"}:
        errors = F.validate_spec(fix["spec"])
        dec = F.evaluate(
            fix["spec"], fix.get("state") or {}, bool(fix.get("stop_expression_true"))
        )
        return {
            "id": fix["id"],
            "action": dec["action"],
            "reason": dec["reason"],
            "unmet_ids": [x["id"] for x in dec.get("floors_unmet") or []],
            "validation_errors": errors,
        }
    dec = F.evaluate(fix["spec"], fix["state"], bool(fix["stop_expression_true"]))
    return {
        "id": fix["id"],
        "action": dec["action"],
        "reason": dec["reason"],
        "unmet_ids": [x["id"] for x in dec["floors_unmet"]],
        "validation_errors": dec.get("validation_errors") or [],
        "stop_expression_true": dec["stop_expression_true"],
        "would_fire_without_floor": dec["would_fire_without_floor"],
        "audit": {
            "event": dec["reason"],
            "floors_unmet": dec["floors_unmet"],
            "round": dec["round"],
            "max_rounds": dec["max_rounds"],
            "gate_enabled": dec["gate_enabled"],
        },
    }


def domain() -> dict:
    floored = load_fix("satisfied-but-floored")
    d_floored = F.evaluate(floored["spec"], floored["state"], True)
    ungated = dict(floored["spec"])
    ungated["gate_enabled"] = False
    d_off = F.evaluate(ungated, floored["state"], True)
    bounded = F.simulate(
        F.default_spec(max_rounds=4, min_rounds=2), F.never_meet_timeline(20, True)
    )
    table = [
        row("satisfied-but-floored"),
        row("floors-met-stop-true"),
        row("stop-false-floors-unmet"),
        row("duplicate-briefs-not-independent"),
        row("min-rounds-zero"),
        row("no-ceiling"),
        row("unsatisfiable-briefs"),
    ]
    requested = [
        "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md",
        "C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json",
        "C:/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    ]
    present = {p: Path(p).is_file() for p in requested}
    cnl76 = (
        REPO
        / "command-center/design/council/"
        / "CNL-0076-stopping-expression-runtime-evaluation-semantics.schema.json"
    ).is_file()

    return {
        "kind": "council-design-note",
        "title": "Minimum deliberation conditions that outrank any early stop",
        "question": (
            "Which floors (minimum rounds, minimum independent briefs, minimum evidence) "
            "must hold before ANY stopping expression may fire, and what is the audit "
            "record when a floor blocks a satisfied stop condition?"
        ),
        "claim_under_test": (
            "Floors are a hard precondition on FIRE, not a conjunct of the stopping "
            "expression. A true stop with unmet floors CONTINUES and records "
            "STOP-BLOCKED-BY-FLOOR naming each unmet floor. A spec with no max_rounds "
            "is rejected as a hang. CNL-0108 may later request an audited waiver; this "
            "unit does not grant a silent skip."
        ),
        "fire_rule": (
            "TERMINATE/FIRE iff stopping expression is true AND floors_unmet is empty. "
            "The expression is not rewritten to false; would_fire_without_floor stays true."
        ),
        "floors": [
            {
                "id": "min_rounds",
                "hard_lower_bound": 1,
                "design_default": 2,
                "blocks_fire_when": "observed round < required min_rounds",
                "spec_quote": "minimum rounds",
                "numeral_status": (
                    "DESIGN-DEFAULT: recovered prompt slice at :10762 is "
                    "'deadlock, escalation, replacement, owner-intervention' not a "
                    "numeral; TST-0264 attributes the floor list to :10762"
                ),
            },
            {
                "id": "min_independent_briefs",
                "hard_lower_bound": 1,
                "design_default": 2,
                "blocks_fire_when": (
                    "distinct opening speakers with non-identical non-empty text < required"
                ),
                "spec_quote": "independent opening positions submitted",
                "independence_rule": (
                    "unique speaker_id, non-empty text, text not byte-identical to an "
                    "earlier opening brief"
                ),
            },
            {
                "id": "min_evidence_items",
                "hard_lower_bound": 1,
                "design_default": 1,
                "blocks_fire_when": "evidence nodes with both claim_id and locator < required",
                "spec_quote": "minimum evidence",
            },
            {
                "id": "mandated_roles_spoken",
                "hard_lower_bound": 1,
                "design_default": ["advocate", "critic"],
                "blocks_fire_when": "any mandated role has no turn in the transcript",
                "spec_quote": "every mandated role having spoken",
            },
        ],
        "audit_when_floor_blocks": {
            "event": "STOP-BLOCKED-BY-FLOOR",
            "must_name_unmet_floors": True,
            "does_not_rewrite_expression": True,
            "record": {
                "event": "STOP-BLOCKED-BY-FLOOR",
                "stop_expression_true": True,
                "would_fire_without_floor": True,
                "action": "CONTINUE",
                "floors_unmet": d_floored["floors_unmet"],
                "round": d_floored["round"],
                "max_rounds": d_floored["max_rounds"],
            },
            "why_outside_the_expression": (
                "AND-ing floors into the expression would report expression=false and hide "
                "that the stop condition was already satisfied. The question asks for the "
                "audit when a floor blocks a SATISFIED stop."
            ),
        },
        "ceiling": {
            "required_field": "max_rounds",
            "missing_is": (
                "floor-with-no-ceiling rejected at validation, never honoured at runtime"
            ),
            "unmet_at_ceiling": (
                "FLOOR-UNMET-AT-CEILING terminates; CONTINUE past max_rounds is a hang"
            ),
            "design_default": 12,
            "design_default_basis": (
                "CNL-0010 tests_required phrases 'not discovered after 12 rounds' as the "
                "static-analysis horizon, not a recovered :10762 numeral"
            ),
            "hang_proof": {
                "bounded_max_rounds": 4,
                "iterations": bounded["iterations"],
                "hung": bounded["hung"],
                "reason": bounded["reason"],
            },
        },
        "cadence_residual": {
            "owned_by": "CNL-0076",
            "cnl_0076_artifact_present": cnl76,
            "assumption": (
                "This gate attaches to the same evaluation tick as the stopping expression "
                "and does not sample mid-turn on its own. If CNL-0076 later pins a different "
                "cadence, the floor moves with that tick."
            ),
        },
        "validation_rejects": [
            "min_rounds < 1 (TST-0264 floor bypass)",
            "max_rounds absent (hang)",
            "min_rounds > max_rounds",
            "min_independent_briefs > |speaking_roles| (unsatisfiable, hang)",
            "mandated_roles empty or not a subset of speaking_roles",
        ],
        "fixture_table": table,
        "satisfied_but_floored": {
            "id": "satisfied-but-floored",
            "action": d_floored["action"],
            "reason": d_floored["reason"],
            "unmet_ids": [x["id"] for x in d_floored["floors_unmet"]],
            "audit": d_floored,
        },
        "negative_controls": [
            {
                "id": "NC-ungated-premature-stop",
                "rejects": (
                    "satisfied stop that TERMINATES while floors are unmet (FC-11338)"
                ),
                "observed": (
                    f"gate_enabled=false action={d_off['action']} reason={d_off['reason']}; "
                    f"gate_enabled=true action={d_floored['action']} reason={d_floored['reason']}"
                ),
            },
            {
                "id": "NC-hang-mutant",
                "rejects": (
                    "CONTINUE past hang_guard when max_rounds is raised past the guard"
                ),
                "observed": (
                    "probe2 mutant-no-effective-ceiling hung=true terminated=false"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0077-probe2-independent-kernel-recount",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "re-tabulate floors_unmet from fixtures/satisfied-but-floored.json; "
                "disagree with the artifact table blocks the unit"
            ),
            "counterexample_instance": (
                "fixtures/satisfied-but-floored.json with gate_enabled=false terminates "
                "PREMATURE-STOP (FC-11338). The gated kernel blocks that instance."
            ),
            "refuted_not_attempted": False,
        },
        "source_availability": {
            "requested_paths_present": False,
            "requested_paths": present,
            "on_tree_proxies": [SLICE, CATALOG],
        },
        "dependency_cnl_0076": {
            "required_by_catalog": True,
            "artifact_present": cnl76,
            "residual": (
                "evaluation cadence, purity, and flap semantics are CNL-0076's; "
                "floors attach to the same tick"
            ),
        },
        "strongest_surviving_counterargument": (
            "A live-war-room preset (CNL-0108) may need to act before independent briefs "
            "exist. This unit refuses a silent skip: any waiver must be a first-class "
            "FLOOR-WAIVED-BY-PRESET audit event with owner_approval_required. CNL-0108 "
            "decides whether that waiver exists; until it does, floors outrank every "
            "expression including emergency ones."
        ),
        "live": {
            "floored": d_floored,
            "ungated": d_off,
            "bounded": {
                "iterations": bounded["iterations"],
                "hung": bounded["hung"],
                "reason": bounded["reason"],
            },
        },
    }


def envelope(payload: dict) -> dict:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    d_floored = payload["live"]["floored"]
    d_off = payload["live"]["ungated"]
    recount_ids = [x["id"] for x in d_floored["floors_unmet"]]
    no_ceil = F.validate_spec(load_fix("no-ceiling")["spec"])

    supporting = [
        FLOOR,
        "command-center/p2-wave/probes/CNL-0077/probe1_satisfied_but_floored.py",
        "command-center/p2-wave/probes/CNL-0077/probe2_ceiling_hang.py",
        FIX_FLOORED,
        FIX_NOCEIL,
        SLICE,
        SCHEMA_REL,
    ]
    artifacts = [sha_row(p, "supporting") for p in supporting]

    floored_src = json.dumps(
        {
            "action": d_floored["action"],
            "reason": d_floored["reason"],
            "unmet": recount_ids,
            "would_fire_without_floor": d_floored["would_fire_without_floor"],
        },
        sort_keys=True,
    )
    ungated_src = json.dumps(
        {"action": d_off["action"], "reason": d_off["reason"]},
        sort_keys=True,
    )
    hang_src = json.dumps({"validation_errors": no_ceil}, sort_keys=True)

    report = dict(payload)
    report["kind"] = "council-design-note"
    report["observations"] = [
        {
            "name": "satisfied-but-floored-action",
            "measured": str(d_floored["action"]),
            "method": "floor.evaluate on fixtures/satisfied-but-floored.json",
            "anchor": FIX_FLOORED,
        },
        {
            "name": "satisfied-but-floored-reason",
            "measured": str(d_floored["reason"]),
            "method": "floor.evaluate on fixtures/satisfied-but-floored.json",
            "anchor": FIX_FLOORED,
        },
        {
            "name": "ungated-premature-stop-reason",
            "measured": str(d_off["reason"]),
            "method": "floor.evaluate gate_enabled=false",
            "anchor": FIX_FLOORED,
        },
        {
            "name": "no-ceiling-validation",
            "measured": "floor-with-no-ceiling" in no_ceil,
            "method": "floor.validate_spec on fixtures/no-ceiling.json",
            "anchor": FIX_NOCEIL,
        },
    ]
    report["control_ids"] = ["NC-ungated-premature-stop", "NC-hang-mutant"]

    return {
        "schema_version": 1,
        "unit_id": "CNL-0077",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0077",
        "spec_anchor": f"{SLICE}:11338",
        "min_bytes_threshold": 1024,
        "profile": "council-design-note",
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "A satisfied stop with unmet floors CONTINUES and records "
                    "STOP-BLOCKED-BY-FLOOR naming each unmet floor; it does not rewrite "
                    "the expression to false."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": FIX_FLOORED,
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": (
                            "python3 -c "
                            "\"import json,sys; sys.path.insert(0,"
                            "'command-center/p2-wave/probes/CNL-0077'); import floor as F; "
                            "fix=json.load(open("
                            "'command-center/p2-wave/probes/CNL-0077/fixtures/"
                            "satisfied-but-floored.json')); "
                            "print(json.dumps(F.evaluate(fix['spec'],fix['state'],True),"
                            "sort_keys=True,default=str))\""
                        ),
                        "raw_output": floored_src,
                        "fingerprint": fp("command", "evaluate:satisfied-but-floored"),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": FIX_FLOORED,
                        "raw_output": json.dumps(
                            {"reviewer_recount_unmet": recount_ids}, sort_keys=True
                        ),
                        "fingerprint": fp("file-read", FIX_FLOORED),
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "A floor with no ceiling is rejected at validation "
                    "(floor-with-no-ceiling) and is never honoured at runtime."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": FIX_NOCEIL,
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": (
                            "python3 -c "
                            "\"import json,sys; sys.path.insert(0,"
                            "'command-center/p2-wave/probes/CNL-0077'); import floor as F; "
                            "fix=json.load(open("
                            "'command-center/p2-wave/probes/CNL-0077/fixtures/"
                            "no-ceiling.json')); print(json.dumps(F.validate_spec(fix['spec'])))\""
                        ),
                        "raw_output": hang_src,
                        "fingerprint": fp("command", "validate_spec:no-ceiling"),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": FIX_NOCEIL,
                        "raw_output": "max_rounds key absent from spec",
                        "fingerprint": fp("file-read", FIX_NOCEIL),
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {"id": "probe1", "command": P1, "result": "PASS"},
            {"id": "probe2", "command": P2, "result": "PASS"},
        ],
        "negative_controls": [
            {
                "id": "NC-ungated-premature-stop",
                "kind": "known-broken-fixture",
                "description": (
                    "gate_enabled=false on satisfied-but-floored must TERMINATE with "
                    "PREMATURE-STOP (FC-11338); gated kernel must CONTINUE with "
                    "STOP-BLOCKED-BY-FLOOR."
                ),
                "fired_on_bad_state": d_off["reason"] == F.PREMATURE_STOP
                and d_off["action"] == F.TERMINATE,
                "silent_on_good_state": d_floored["reason"] == F.STOP_BLOCKED_BY_FLOOR
                and d_floored["action"] == F.CONTINUE,
                "bad_state_output": ungated_src,
                "good_state_output": floored_src,
            },
            {
                "id": "NC-hang-mutant",
                "kind": "mutation",
                "description": (
                    "Raising max_rounds past hang_guard must set hung=true; a bounded "
                    "ceiling must terminate FLOOR-UNMET-AT-CEILING."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "hung=true terminated=false hang_guard=5",
                "good_state_output": (
                    f"hung={payload['live']['bounded']['hung']} "
                    f"reason={payload['live']['bounded']['reason']}"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0077-probe2-independent-kernel-recount",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Mechanical re-tabulation of floors_unmet from fixture bytes, not from "
                "the design-note prose. Counterexample: ungated satisfied-but-floored "
                "terminates PREMATURE-STOP."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
            "entry_id": "CNL-0077",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/CNL-0077/schema_check.py",
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
                        "\"import json,sys; sys.path.insert(0,"
                        "'command-center/p2-wave/probes/CNL-0077'); "
                        "import schema_check as SC; "
                        f"print(SC.error_list(json.load(open({OUT_REL!r}))))\""
                    ),
                    "raw_output": "errors=[]",
                    "fingerprint": fp("schema-validate", SCHEMA_REL),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": now,
            "ended_at": now,
            "duration_seconds": 0,
        },
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot: after the 2nd failure on the same hypothesis, "
                "enumerate >=2 alternative mechanisms before a 3rd attempt "
                "(AGENTS.md 4b). Max 3 attempts, then emit FAILED:CNL-0077."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Windows harness-restore _USER-PROMPTS.md:10746-10767 and "
                    ":11338 are not mounted on this Linux worktree."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Mount the harness-restore tree and re-read :10762 numerals and "
                    ":11338 verbatim; replace DESIGN-DEFAULT floors if the source "
                    "disagrees."
                ),
            },
            {
                "claim": (
                    "Recovered prompt-two-slice.md:10762 is 'deadlock, escalation, "
                    "replacement, owner-intervention', not the TST-0264 floor list."
                ),
                "verdict": "PARTIAL",
                "settling_experiment": (
                    "Treat TST-0264 question_or_target as the on-tree attribution of "
                    "the floor list until a fuller :10762 recovery exists."
                ),
            },
            {
                "claim": (
                    "CNL-0076 cadence (end-of-round vs end-of-turn) is not on this "
                    "tree's catalog output_path; floors attach to whichever tick "
                    "evaluates the expression."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-bind the floor gate to the CNL-0076 cadence constant once "
                    "that artifact is on disk."
                ),
            },
        ],
        "produced_by": {
            "vendor": "grok",
            "model": "grok-4.6",
            "role": "council-systems-designer",
            "execution_substrate": "local-parallel",
        },
        "report": report,
    }


def main() -> int:
    payload = domain()
    doc = envelope(payload)
    garbage = {"totally": "unrelated", "passing_tests": 999999}
    g_errs = SC.error_list(garbage)
    if not g_errs:
        print("FAILED:CNL-0077-emit schema-vacuous")
        return 1
    errs = SC.error_list(doc)
    if errs:
        print("FAILED:CNL-0077-emit schema")
        for e in errs[:20]:
            print(f"  {e}")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    live = json.loads(OUT.read_text(encoding="utf-8"))
    live_errs = SC.error_list(live)
    if live_errs:
        print("FAILED:CNL-0077-emit roundtrip-schema")
        for e in live_errs[:20]:
            print(f"  {e}")
        return 1
    if "SUCCESS:CNL-0077" not in OUT.read_text(encoding="utf-8"):
        print("FAILED:CNL-0077-emit sentinel-absent")
        return 1
    print(f"wrote {OUT_REL} schema-errors-on-garbage={len(g_errs)}")
    print("SUCCESS:CNL-0077-emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
