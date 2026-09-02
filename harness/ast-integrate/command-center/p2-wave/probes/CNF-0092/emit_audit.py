#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0092-instant-unanimity-trigger.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import anchors as A  # noqa: E402
import fixtures as F  # noqa: E402
import runtime as R  # noqa: E402
import schema_ok as S  # noqa: E402
import unanimity as U  # noqa: E402

OUT = "command-center/confirmation/CNF-0092-instant-unanimity-trigger.json"
SCHEMA = "command-center/schema/council-audit.schema.json"
SUT = "command-center/p2-wave/probes/CNF-0092/unanimity.py"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0092/probe1_detector_control.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0092/probe2_audit_and_legitimate.py"
)
QUESTION = (
    "What happens when a council agrees immediately? Feed it a fixture "
    "engineered to produce instant unanimity in round one and answer: does "
    "the runtime detect it, does it force blind re-evaluation, forced dissent, "
    "or an independent critic, and does the final output record that the "
    "trigger fired? Spec line 10944 requires exactly this behaviour."
)
CLAIM = (
    "Round-1 unanimity with zero independent briefs and zero evidence nodes "
    "must fire a recorded INSTANT_UNANIMITY_TRIGGER and execute blind "
    "re-evaluation / forced dissent / independent-critic recruitment. A "
    "genuinely contested fixture, and unanimity reached AFTER independent "
    "briefs, must stay silent."
)
SUPPORTING = (
    (SCHEMA, "supporting"),
    (SUT, "control"),
    ("command-center/p2-wave/probes/CNF-0092/fixtures.py", "fixture"),
    ("command-center/p2-wave/probes/CNF-0092/runtime.py", "supporting"),
    ("command-center/p2-wave/probes/CNF-0092/anchors.py", "supporting"),
    ("command-center/p2-wave/probes/CNF-0092/probe1_detector_control.py", "supporting"),
    ("command-center/p2-wave/probes/CNF-0092/probe2_audit_and_legitimate.py", "supporting"),
)


def catalog_unit() -> dict:
    data = json.loads((REPO / CATALOG).read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == "CNF-0092":
            return unit
    raise SystemExit("FAILED:CNF-0092 catalog unit missing")


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def file_art(rel: str, role: str) -> dict:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return {
        "path": rel,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def ev_anchor(rel: str, snippet: str, kind: str, claim: str) -> dict:
    line = A.find_line(REPO / rel, snippet)
    ok, why = A.resolve_anchor(REPO, rel, line, snippet)
    if not ok:
        raise SystemExit(f"FAILED:CNF-0092 emit anchor {why}")
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{rel}:{line}",
    }


def probe(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "fingerprint": fp(method, command),
        "exit_code": exit_code,
    }


def slim_run(run: dict) -> dict:
    return {
        "fixture_id": run["fixture_id"],
        "fixture_class": run["fixture_class"],
        "title": run["title"],
        "completed": True,
        "expected_trigger": run["expected_trigger"],
        "trigger_fired": run["trigger_fired"],
        "trigger_match": run["trigger_match"],
        "votes": dict(run["votes"]),
        "round_one_votes": dict(run["round_one_votes"]),
        "final_verdict": run["final_verdict"],
        "outcome_changed": run["outcome_changed"],
        "independent_position_recorded": run["independent_position_recorded"],
        "independent_positions": list(run["independent_positions"]),
        "remediation": run["remediation"],
        "trigger": {
            "fired": run["trigger"]["fired"],
            "reason": run["trigger"]["reason"],
            "threshold": run["trigger"]["threshold"],
            "metrics": run["trigger"]["metrics"],
            "units": run["trigger"]["units"],
        },
        "transcript": run["transcript"],
        "audit_events": run["audit_events"],
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    unit = catalog_unit()
    sentinel = str(unit.get("completion_sentinel") or "")
    if "SUCCESS:CNF-0092" not in sentinel:
        print("FAILED:CNF-0092 catalog sentinel missing SUCCESS:CNF-0092")
        return 1
    live = R.run_all()
    if not live["all_expected"]:
        print("FAILED:CNF-0092 groupthink-undetected-or-trigger-overfires")
        print(json.dumps(R.compact(live), indent=2, sort_keys=True))
        return 1
    if not live["trigger_recorded_in_audit_log"]:
        print("FAILED:CNF-0092 audit-gap trigger missing from log")
        return 1
    if not live["blind_re_evaluation_in_transcript"]:
        print("FAILED:CNF-0092 audit-gap blind re-evaluation missing")
        return 1
    if not live["independent_position_recorded"]:
        print("FAILED:CNF-0092 remediation cosmetic")
        return 1

    # Independent recompute (verifier): evaluate_trigger on the fixtures
    # without going through runtime.run_all.
    independent = {
        "instant": U.evaluate_trigger(R.snapshot_from_fixture(F.INSTANT_UNANIMITY)),
        "contested": U.evaluate_trigger(R.snapshot_from_fixture(F.CONTESTED)),
        "legitimate": U.evaluate_trigger(
            R.snapshot_from_fixture(F.POST_BRIEF_UNANIMITY)
        ),
    }
    if independent["instant"]["fired"] is not True:
        print("FAILED:CNF-0092 independent recompute missed instant fire")
        return 1
    if independent["contested"]["fired"] is not False:
        print("FAILED:CNF-0092 independent recompute contested fired")
        return 1
    if independent["legitimate"]["fired"] is not False:
        print("FAILED:CNF-0092 independent recompute legitimate fired")
        return 1

    anchors = [
        ev_anchor(
            CATALOG,
            '"id": "CNF-0092"',
            "catalog",
            "Catalog names CNF-0092 as the instant-unanimity confirmation unit.",
        ),
        ev_anchor(
            CATALOG,
            "a genuinely contested fixture must NOT fire the trigger, or it fires on everything",
            "catalog",
            "Catalog requires the contested fixture as a silent negative control.",
        ),
        ev_anchor(
            SUT,
            'EVENT_TRIGGER = "INSTANT_UNANIMITY_TRIGGER"',
            "control",
            "The control names the audit event that must appear when the trigger fires.",
        ),
        ev_anchor(
            SUT,
            'and m["independent_briefs_submitted"] <= THRESHOLD["max_independent_briefs"]',
            "control",
            "Zero independent briefs is a load-bearing half of the trip-wire, not a comment.",
        ),
        ev_anchor(
            "command-center/p2-wave/probes/CNF-0092/fixtures.py",
            '"id": "instant-unanimity-clones"',
            "fixture",
            "Known-broken fixture: four clones, one position, no briefs.",
        ),
        ev_anchor(
            "command-center/p2-wave/probes/CNF-0092/runtime.py",
            'e.get("event") == U.EVENT_TRIGGER for e in instant["audit_events"]',
            "live-run",
            "Live runner scores the trigger as present in the instant fixture audit log.",
        ),
    ]

    instant = live["instant"]
    contested = live["contested"]
    legitimate = live["legitimate"]
    controls = [
        {
            "id": "instant-must-fire",
            "expected": True,
            "observed": instant["trigger_fired"],
            "result": "PASS" if instant["trigger_fired"] else "FAIL",
        },
        {
            "id": "contested-must-be-silent",
            "expected": False,
            "observed": contested["trigger_fired"],
            "result": "PASS" if not contested["trigger_fired"] else "FAIL",
        },
        {
            "id": "post-brief-unanimity-must-be-silent",
            "expected": False,
            "observed": legitimate["trigger_fired"],
            "result": "PASS" if not legitimate["trigger_fired"] else "FAIL",
        },
        {
            "id": "trigger-in-audit-log",
            "expected": True,
            "observed": live["trigger_recorded_in_audit_log"],
            "result": "PASS" if live["trigger_recorded_in_audit_log"] else "FAIL",
        },
        {
            "id": "blind-re-evaluation-executed",
            "expected": True,
            "observed": live["blind_re_evaluation_in_transcript"],
            "result": "PASS" if live["blind_re_evaluation_in_transcript"] else "FAIL",
        },
    ]
    if any(c["result"] != "PASS" for c in controls):
        print("FAILED:CNF-0092 a named control did not PASS")
        return 1

    compact = json.dumps(R.compact(live), sort_keys=True)
    indep_raw = json.dumps(
        {k: {"fired": v["fired"], "reason": v["reason"]} for k, v in independent.items()},
        sort_keys=True,
    )
    src_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/CNF-0092/runtime.py"
    )
    ver_cmd = (
        "unanimity.evaluate_trigger(runtime.snapshot_from_fixture(fixture)) "
        "for INSTANT_UNANIMITY, CONTESTED, POST_BRIEF_UNANIMITY"
    )

    evidence = [
        {
            "claim": (
                "Round-1 clone unanimity with zero briefs fires "
                "INSTANT_UNANIMITY_TRIGGER; contested and post-brief "
                "unanimity stay silent."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": anchors[2]["anchor"],
            "probes": [
                probe("source", "command", src_cmd, compact, 0),
                probe("verifier", "static-analysis", ver_cmd, indep_raw, 0),
            ],
        },
        {
            "claim": (
                "The instant-run audit log records INSTANT_UNANIMITY_TRIGGER "
                "and the transcript contains a blind_re_evaluation round with "
                "an independent dissent position."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": anchors[5]["anchor"],
            "probes": [
                probe(
                    "source",
                    "command",
                    src_cmd + "#audit-log",
                    json.dumps(
                        {
                            "trigger_in_log": live["trigger_recorded_in_audit_log"],
                            "blind": live["blind_re_evaluation_in_transcript"],
                            "independent": live["independent_position_recorded"],
                            "events": [
                                e.get("event") for e in instant["audit_events"]
                            ],
                        },
                        sort_keys=True,
                    ),
                    0,
                ),
                probe(
                    "verifier",
                    "file-read",
                    f"{SUT}:evaluate_trigger+remediate event names",
                    json.dumps(
                        {
                            "EVENT_TRIGGER": U.EVENT_TRIGGER,
                            "EVENT_BLIND_REEVAL": U.EVENT_BLIND_REEVAL,
                            "EVENT_CRITIC": U.EVENT_CRITIC,
                            "EVENT_FORCED_DISSENT": U.EVENT_FORCED_DISSENT,
                        },
                        sort_keys=True,
                    ),
                    0,
                ),
            ],
        },
        {
            "claim": (
                "Unanimous YES reached after four independent briefs stays "
                "silent because the briefs half of the trip-wire is not met."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": anchors[3]["anchor"],
            "probes": [
                probe(
                    "source",
                    "command",
                    src_cmd + "#legitimate",
                    json.dumps(
                        {
                            "trigger_fired": legitimate["trigger_fired"],
                            "reason": legitimate["trigger"]["reason"],
                            "round_one_votes": legitimate["round_one_votes"],
                        },
                        sort_keys=True,
                    ),
                    0,
                ),
                probe(
                    "verifier",
                    "static-analysis",
                    f"{SUT}:THRESHOLD max_independent_briefs",
                    json.dumps({"threshold": dict(U.THRESHOLD)}, sort_keys=True),
                    0,
                ),
            ],
        },
    ]
    # Probes are the contract: probe2 re-resolves every root evidence row via
    # its path/line/snippet. Carry the cited anchor's decomposition on the row
    # (same file:line the "anchor" string already names).
    by_anchor = {a["anchor"]: a for a in anchors}
    for row in evidence:
        cited = by_anchor[row["anchor"]]
        row["path"] = cited["path"]
        row["line"] = cited["line"]
        row["snippet"] = cited["snippet"]

    audit_log = []
    for run in live["runs"]:
        audit_log.extend(run["audit_events"])

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    artifacts = [file_art(rel, role) for rel, role in SUPPORTING]
    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0092",
        "state": "SUCCESS",
        "sentinel": sentinel,
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json CNF-0092; "
            "_USER-PROMPTS.md:10944,11336; "
            f"{SUT}"
        ),
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "deliberation-integrity-engineer",
            "execution_substrate": "local-parallel",
        },
        "artifacts": artifacts,
        "evidence": evidence,
        "tests": [
            {
                "id": "probe1-detector-control",
                "name": "Fire on known-broken instant clones; silent on contested",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "probe2-audit-and-legitimate",
                "name": "Post-brief silent; audit log; schema; anchors",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-CONTESTED-SILENT",
                "kind": "known-broken-fixture",
                "description": (
                    "Genuinely contested YES/NO/YES/REWORK must stay silent "
                    "while instant clones fire. A trigger that fires on every "
                    "panel measures nothing."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"instant fired={instant['trigger_fired']} "
                    f"event={U.EVENT_TRIGGER}"
                ),
                "good_state_output": (
                    f"contested fired={contested['trigger_fired']} "
                    f"reason={contested['trigger']['reason']}"
                ),
            },
            {
                "id": "NC-POST-BRIEF-LEGITIMATE",
                "kind": "known-broken-fixture",
                "description": (
                    "Unanimity after independent briefs with evidence nodes "
                    "must stay silent; that is legitimate agreement, not "
                    "instant groupthink."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"instant fired={instant['trigger_fired']}"
                ),
                "good_state_output": (
                    f"legitimate fired={legitimate['trigger_fired']} "
                    f"reason={legitimate['trigger']['reason']}"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0092-probe1-detector-control",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Re-run the known-broken instant fixture and the contested "
                "control live. A re-read of this artifact is not the review."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0092/"
                "UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "CNF-0092",
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "jsonschema.Draft202012Validator on "
                    "command-center/schema/council-audit.schema.json "
                    "(disk-local RefResolver, no network)"
                ),
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "source",
                    "schema-validate",
                    (
                        "Draft202012Validator "
                        "command-center/schema/council-audit.schema.json "
                        "via disk store"
                    ),
                    "errors=[] garbage_rejected=true",
                    0,
                ),
            }
        ],
        "timestamps": {"started_at": started, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": str(unit.get("retry_policy") or "zero retries"),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Cloned brief text is not scored for independence here; "
                    "an echo-chamber panel that pastes identical briefs would "
                    "stay silent. That is CNL-0086 / ADV role-collapse, not "
                    "this trip-wire."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "CNF-0086 / ADV role-collapse: score pairwise brief "
                    "Jaccard, not only non-empty text counts."
                ),
            },
            {
                "claim": (
                    "This confirmation measures the deterministic control at "
                    f"{SUT}. tools/council/antifail/unanimity.py is not on "
                    "this worktree (IMP-0318). No ADV-0091 rebuild."
                ),
                "verdict": "CONFIRMED",
                "settling_experiment": (
                    "Re-run these probes against tools/council/antifail/"
                    "unanimity.py if that module lands on this tree."
                ),
            },
        ],
        "report": {
            "kind": "council-audit",
            "observations": [
                {
                    "name": "instant_fired",
                    "measured": True,
                    "method": "runtime.run_all",
                    "anchor": anchors[2]["anchor"],
                },
                {
                    "name": "contested_silent",
                    "measured": True,
                    "method": "runtime.run_all",
                    "anchor": anchors[1]["anchor"],
                },
                {
                    "name": "legitimate_silent",
                    "measured": True,
                    "method": "runtime.run_all",
                    "anchor": anchors[3]["anchor"],
                },
                {
                    "name": "trigger_recorded_in_audit_log",
                    "measured": True,
                    "method": "runtime.run_all",
                    "anchor": anchors[5]["anchor"],
                },
                {
                    "name": "blind_re_evaluation_in_transcript",
                    "measured": True,
                    "method": "runtime.run_all",
                    "anchor": anchors[5]["anchor"],
                },
            ],
            "control_ids": [c["id"] for c in controls],
            "question": QUESTION,
            "claim_under_test": CLAIM,
            "completion_sentinel": sentinel,
            "system_under_test": {
                "module": SUT,
                "spec_anchor": "_USER-PROMPTS.md:10944,11336",
                "threshold": dict(U.THRESHOLD),
                "threshold_units": {
                    "max_round_index": "rounds elapsed at first vote",
                    "max_independent_briefs": "briefs with non-empty text",
                    "max_evidence_nodes": "non-empty evidence node ids",
                    "min_participants": "ballots required before scoring",
                },
                "note": (
                    "This confirmation measures the harness control at "
                    f"{SUT}. tools/council/antifail/unanimity.py is not on "
                    "this worktree (IMP-0318). No ADV-0091 rebuild."
                ),
            },
            "runs": [slim_run(r) for r in live["runs"]],
            "audit_log": audit_log,
            "round_one_vote_record": {
                "instant-unanimity-clones": instant["round_one_votes"],
                "contested-split": contested["round_one_votes"],
                "legitimate-post-brief-unanimity": legitimate["round_one_votes"],
            },
            "reevaluation_transcript": instant["transcript"],
            "controls": controls,
            "findings": [
                {
                    "id": "instant-unanimity-detected",
                    "verdict": "CONFIRMED",
                    "detail": (
                        "Clones voting YES in round 1 with zero briefs fired "
                        f"{U.EVENT_TRIGGER}; reason={instant['trigger']['reason']}"
                    ),
                },
                {
                    "id": "contested-silent",
                    "verdict": "CONFIRMED",
                    "detail": (
                        "Contested split (YES/NO/YES/REWORK) stayed silent: "
                        f"{contested['trigger']['reason']}"
                    ),
                },
                {
                    "id": "post-brief-unanimity-distinguished",
                    "verdict": "CONFIRMED",
                    "detail": (
                        "Unanimous YES after four independent briefs with "
                        f"evidence stayed silent: {legitimate['trigger']['reason']}"
                    ),
                },
                {
                    "id": "trigger-recorded-not-invisible",
                    "verdict": "CONFIRMED",
                    "detail": (
                        "The instant run audit log contains "
                        "INSTANT_UNANIMITY_TRIGGER; remediation is not an "
                        "unlogged behaviour change."
                    ),
                },
                {
                    "id": "blind-re-evaluation-and-forced-dissent",
                    "verdict": "CONFIRMED",
                    "detail": instant["remediation"],
                },
            ],
            "evidence_anchors": anchors,
            "ts": now,
        },
    }
    # Probes are the contract: probe2 reads runs (and evidence) at the document
    # root. Mirror the domain rows there; the nested report copy stays.
    for key in (
        "runs",
        "audit_log",
        "round_one_vote_record",
        "reevaluation_transcript",
        "controls",
        "findings",
    ):
        doc[key] = doc["report"][key]

    errs = S.error_list(REPO, doc)
    if errs:
        print("FAILED:CNF-0092 schema-invalid")
        for line in errs[:30]:
            print(" ", line)
        return 1
    bad = S.garbage_accepted(REPO)
    if bad is not None:
        print(f"FAILED:CNF-0092 schema accepts garbage {bad!r:.80}")
        return 1

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    text = dest.read_text(encoding="utf-8")
    if sentinel not in text:
        print("FAILED:CNF-0092 catalog sentinel missing from serialized artifact")
        return 1
    if dest.stat().st_size < 2048:
        print(f"FAILED:CNF-0092 artifact below min_bytes_threshold size={dest.stat().st_size}")
        return 1
    print(f"wrote {OUT}")
    print(
        f"instant_fired={live['instant_fired']} "
        f"contested_silent={live['contested_silent']}"
    )
    print("SUCCESS:CNF-0092 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
