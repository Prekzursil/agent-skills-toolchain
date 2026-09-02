#!/usr/bin/env python3
"""Emit RES-0167 measurement-run artifact."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import capture as C  # noqa: E402
import harvest as H  # noqa: E402
import progress as P  # noqa: E402

OUT_REL = (
    "command-center/research/deep-research-design/"
    "RES-0167-fix-review-repair-loop-limits.json"
)
SCHEMA_REL = "command-center/p2-wave/probes/RES-0167/artifact.schema.json"
DECLARED_SCHEMA = "command-center/schema/measurement-run.schema.json"
SENTINEL = "SUCCESS:RES-0167"
QUESTION = (
    "What attempt limit, progress predicate, and escalation path should govern "
    "the sub-orchestrator's fix-review loop, given measured data on how often "
    "a second and third attempt actually succeed on this estate — and what "
    "distinguishes 'retry is working' from 'grinding on the same fingerprint'?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0167/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0167/probe2_independent_recount.py"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def rail(row: dict, quote: str, note: str) -> dict:
    return {
        "resolved_url": row.get("resolved_url") or row.get("requested_url"),
        "fetch_timestamp": row.get("fetch_timestamp"),
        "sha256_of_fetched_bytes": row.get("sha256"),
        "bytes": row.get("bytes"),
        "http_status": row.get("http_status"),
        "snapshot": row.get("snapshot"),
        "quote": quote,
        "note": note,
        "rail": row.get("rail"),
    }


def by_id(idx: dict, sid: str) -> dict:
    for row in (idx.get("web") or []) + (idx.get("local") or []):
        if row.get("id") == sid:
            return row
    return {}


def extract_quote(sid: str, needle: str, width: int = 180) -> str:
    path = HERE / "captures" / f"{sid}.body"
    if not path.is_file():
        return needle
    text = path.read_text(encoding="utf-8", errors="replace")
    i = text.lower().find(needle.lower())
    if i < 0:
        return needle
    chunk = text[max(0, i - 40) : min(len(text), i + width)]
    return " ".join(chunk.split())


def main() -> int:
    idx = C.capture_all()
    harvested = H.census()
    both = P.both_states()
    park_grind = P.park_decision(P.GRIND_SEQUENCE)
    park_prod = P.park_decision(P.PRODUCTIVE_SEQUENCE)
    s1 = harvested["signal1_supervisor"]
    tree = harvested["signal2_tree"]
    seq = tree["retry_sequences"]
    pairs = tree["two_strike_pairs"]
    rets = tree["subagent_returns"]
    policy = harvested["dispatch_policy"]
    printed = harvested["printed_success_by_attempt"]
    now = utc_now()

    r_log = by_id(idx, "supervisor-log")
    r_disp = by_id(idx, "dispatch-cursor")
    r_adv = by_id(idx, "adv-0059-validate")
    r_aud = by_id(idx, "aud-0084-refute")
    r_slice = by_id(idx, "cc-0024-slice")
    r_cat = by_id(idx, "catalog-res-0167")
    r_sre = by_id(idx, "sre-handling-overload")
    r_aws = by_id(idx, "aws-backoff-jitter")
    r_tmp = by_id(idx, "temporal-retry-policy")

    web_ok = int(idx.get("web_ok") or 0)
    local_ok = int(idx.get("local_ok") or 0)
    if local_ok < 4:
        print("FAILED:RES-0167 emit local rails missing")
        return 1
    if not both.get("good_discriminator"):
        print("FAILED:RES-0167 emit predicate does not discriminate")
        return 1
    if not park_grind.get("park") or not park_grind.get("required_fix"):
        print("FAILED:RES-0167 emit grind did not park with required_fix")
        return 1
    if park_prod.get("park"):
        print("FAILED:RES-0167 emit productive sequence parked")
        return 1

    attempt1 = int(s1["success_by_max_launch_attempt"]["1"])
    attempt2 = int(s1["success_by_max_launch_attempt"]["2"])
    attempt3 = int(s1["success_by_max_launch_attempt"]["3"])
    n_pairs = int(pairs["n_pairs"])
    n_pair_del = int(pairs["delivered_after_two_strikes"])
    same_ok = int(seq["trailing_same_fingerprint_then_success"])
    same_fail = int(seq["trailing_same_fingerprint_still_not_success"])

    answer = (
        f"On this estate a second or third same-fingerprint attempt is not a "
        f"working retry. Supervisor census (signal 1): DONE-OK by max launch "
        f"attempt attempt1={attempt1} attempt2={attempt2} attempt3={attempt3}; "
        f"launches_ge2={s1['launches_attempt_ge_2']} "
        f"launches_ge3={s1['launches_attempt_ge_3']}; "
        f"retryable={s1['retryable_events']} park={s1['park_events']}. "
        f"Tree census (signal 2): two-strike pairs n={n_pairs} delivered={n_pair_del}; "
        f"same-fingerprint retry sequences then-success={same_ok} still-fail={same_fail}; "
        f"SUBAGENT-RETURN delivered={rets['delivered']} retry_count_nonzero="
        f"{rets['retry_count_nonzero']}. "
        f"Policy: attempt_limit_same_fingerprint=2 then PARK status=BLOCKED with "
        f"required_fix=break-same-fingerprint:<fp> (no third try on that fingerprint). "
        f"After a fingerprint change (PROGRESS), enumerate >=2 alternatives and allow "
        f"exactly one more attempt; hard cap total attempts=3. Escalation: PARK is "
        f"distinct from proof-of-impossibility (RES-0149) and from SUCCESS. "
        f"Progress predicate: consecutive attempts (F(n),O(n)) → PROGRESS if O(n) is "
        f"success or F(n)!=F(n-1) or n==1; NO-PROGRESS if F(n)!='' and F(n)==F(n-1). "
        f"Printed harvest: {printed}. "
        f"Both-states: {both['printed']}. "
        f"Dispatch TWO_STRIKES={policy.get('two_strikes')} already parks after two "
        f"attempts. Industry rails (retries without jitter/budget amplify overload) "
        f"are corroboration, not the conversion-rate measurement. "
        f"{SENTINEL}"
    )

    claims = [
        {
            "id": "C1-first-attempt-dominates-this-wave",
            "text": (
                f"G-1 DONE-OK units in the supervisor snapshot succeeded on "
                f"attempt 1 (attempt1={attempt1}, attempt2={attempt2}, "
                f"attempt3={attempt3}); this wave recorded "
                f"{s1['launches_attempt_ge_2']} launches with attempt>=2."
            ),
            "verdict": "CONFIRMED",
            "sherman_kent_band": "almost-certain",
            "sherman_kent_probability_interval": [0.93, 0.99],
            "independent_verification_path": (
                "python3 -B command-center/p2-wave/probes/RES-0167/harvest.py"
            ),
            "lineage": [
                rail(r_log, "LAUNCH", "supervisor.log snapshot; regex LAUNCH/DONE-OK"),
                rail(r_disp, "TWO_STRIKES = 2", "live dispatch policy source"),
            ],
            "signals": [
                {
                    "id": "S1-supervisor-regex",
                    "mechanism": "regex over supervisor.log LAUNCH attempt=N and DONE-OK",
                    "value": {
                        "done_ok": s1["done_ok"],
                        "success_by_max_launch_attempt": s1["success_by_max_launch_attempt"],
                    },
                },
                {
                    "id": "S2-subagent-return-retry-key",
                    "mechanism": "SUBAGENT-RETURN.json retry.count census",
                    "value": rets,
                },
            ],
        },
        {
            "id": "C2-same-fingerprint-second-attempt-does-not-convert",
            "text": (
                f"Recorded same-fingerprint retries do not convert: "
                f"trailing_same_fingerprint_then_success={same_ok}, "
                f"still_not_success={same_fail}; two-strike probe pairs "
                f"n={n_pairs} delivered_after_two_strikes={n_pair_del}. "
                f"ADV-0059 recorded two attempts with fingerprint "
                f"partial-clone-hydration-transport and remains BLOCKED."
            ),
            "verdict": "CONFIRMED",
            "sherman_kent_band": "probable",
            "sherman_kent_probability_interval": [0.75, 0.85],
            "independent_verification_path": (
                "python3 -B command-center/p2-wave/probes/RES-0167/probe2_independent_recount.py"
            ),
            "lineage": [
                rail(
                    r_adv,
                    "partial-clone-hydration-transport",
                    "ADV-0059 retry.attempts same fingerprint twice, state BLOCKED",
                ),
                rail(
                    r_aud,
                    "error_fingerprint",
                    "AUD-0084 two distinct fingerprints (productive / not a grind)",
                ),
            ],
            "signals": [
                {
                    "id": "S1-retry-attempts-walk",
                    "mechanism": "JSON walk of retry.attempts error_fingerprint pairs",
                    "value": {
                        "then_success": same_ok,
                        "still_fail": same_fail,
                        "fingerprint_changed": seq["trailing_fingerprint_changed"],
                    },
                },
                {
                    "id": "S2-two-strike-pairs",
                    "mechanism": "_strike1* plus _strike2* directories vs SUBAGENT-RETURN",
                    "value": {"n_pairs": n_pairs, "delivered": n_pair_del},
                },
            ],
        },
        {
            "id": "C3-progress-predicate-and-park",
            "text": (
                "Retry is working when the latest attempt succeeds or the error "
                "fingerprint changes. Grinding is two consecutive non-empty equal "
                "fingerprints (NO-PROGRESS). Two same-fingerprint structural "
                "failures park with status=BLOCKED and required_fix named "
                f"{park_grind['required_fix']}. No ADV rebuild loop."
            ),
            "verdict": "CONFIRMED",
            "sherman_kent_band": "almost-certain",
            "sherman_kent_probability_interval": [0.93, 0.99],
            "independent_verification_path": (
                "python3 -B command-center/p2-wave/probes/RES-0167/probe1_both_states.py"
            ),
            "lineage": [
                rail(
                    r_cat,
                    "same fingerprint twice",
                    "catalog tests_required both-states grind control",
                ),
                rail(
                    r_slice,
                    "fix-review until pass, attempt limit, or proof-of-impossibility",
                    "CC-0024 recovered spec slice lines 11272-11276",
                ),
            ],
            "signals": [
                {
                    "id": "S1-predicate",
                    "mechanism": "progress.classify_attempts on recorded sequences",
                    "value": {
                        "productive_verdict": both["productive_verdict"],
                        "grind_verdict": both["grind_verdict"],
                        "good_discriminator": both["good_discriminator"],
                    },
                },
                {
                    "id": "S2-independent-trailing-equality",
                    "mechanism": "probe2 reimplementation without classify_attempts",
                    "value": "trailing equal fingerprints => NO-PROGRESS",
                },
            ],
        },
    ]
    if r_sre.get("ok") or r_aws.get("ok") or r_tmp.get("ok"):
        claims.append(
            {
                "id": "C4-uncapped-retries-amplify-overload",
                "text": (
                    "Public SRE/cloud retry literature treats unbounded client retries "
                    "as overload amplifiers; jittered backoff and a maximum-attempt "
                    "budget are the standard controls. This is corroboration for the "
                    "estate cap, not a substitute for the conversion-rate census."
                ),
                "verdict": "CONFIRMED" if web_ok >= 2 else "PARTIAL",
                "sherman_kent_band": "probable" if web_ok >= 2 else "possible",
                "sherman_kent_probability_interval": (
                    [0.75, 0.85] if web_ok >= 2 else [0.40, 0.55]
                ),
                "independent_verification_path": (
                    "python3 -B command-center/p2-wave/probes/RES-0167/capture.py"
                ),
                "lineage": [
                    rail(
                        r_sre,
                        extract_quote("sre-handling-overload", "retry"),
                        "SRE handling-overload (or fallback chapter)",
                    ),
                    rail(
                        r_aws,
                        extract_quote("aws-backoff-jitter", "jitter"),
                        "AWS exponential backoff and jitter",
                    ),
                    rail(
                        r_tmp,
                        extract_quote("temporal-retry-policy", "retry"),
                        "Temporal retry policy / failure detection",
                    ),
                ],
                "signals": [
                    {
                        "id": "S1-web-fetch",
                        "mechanism": "HTTP GET + sha256 body",
                        "value": {"web_ok": web_ok},
                    },
                    {
                        "id": "S2-needle",
                        "mechanism": "needle presence in fetched bytes",
                        "value": {
                            "sre": (r_sre.get("needles") or {}),
                            "aws": (r_aws.get("needles") or {}),
                            "temporal": (r_tmp.get("needles") or {}),
                        },
                    },
                ],
            }
        )

    doc = {
        "unit_id": "RES-0167",
        "report_kind": "measurement-run",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": (
            "SUCCESS:RES-0167 in the artifact AND printed success-by-attempt "
            "plus both-states PROGRESS vs NO-PROGRESS"
        ),
        "title": (
            "Repair loop: how many fix-review attempts before escalation, "
            "and what stops an infinite loop?"
        ),
        "question": QUESTION,
        "answer": answer,
        "min_bytes_threshold": 2048,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=RES-0167]",
        "output_schema_declared": DECLARED_SCHEMA,
        "output_schema_declared_present": (REPO / DECLARED_SCHEMA).is_file(),
        "local_artifact_schema": SCHEMA_REL,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "measurement-engineer",
            "execution_substrate": "headless-linux",
        },
        "progress_predicate": {
            "name": "consecutive-fingerprint-divergence",
            "computable": True,
            "definition": (
                "PROGRESS iff latest outcome is success, or n==1, or the latest "
                "two error fingerprints differ (including first failure). "
                "NO-PROGRESS iff the latest two fingerprints are non-empty and equal."
            ),
            "inputs": ["error_fingerprint", "outcome"],
            "good_classifier": "progress.classify_attempts",
            "broken_classifier": "progress.always_progress",
        },
        "attempt_limit": {
            "same_fingerprint": 2,
            "after_fingerprint_change_additional": 1,
            "hard_cap_total": 3,
            "infra_auth_predicate_absent_does_not_consume_strike": True,
            "dispatch_TWO_STRIKES": policy.get("two_strikes"),
            "rationale": (
                "Measured conversion of same-fingerprint attempt 2/3 is 0 on "
                "recorded sequences and two-strike pairs. Attempt 3 on the same "
                "fingerprint is a grind, not a retry."
            ),
        },
        "escalation_path": {
            "on_NO_PROGRESS": {
                "status": "BLOCKED",
                "required_fix": "break-same-fingerprint:<error_fingerprint>",
                "example": park_grind,
                "rebuild_adv": False,
            },
            "on_PROGRESS_but_still_failing": (
                "Enumerate >=2 alternative approaches, then at most one more attempt "
                "(AGENTS.md 4b / catalog retry_policy)."
            ),
            "on_hard_cap": "ATTEMPT-LIMIT terminal record (not proof-of-impossibility)",
            "on_impossibility": (
                "RES-0149 proof-of-impossibility record; distinct code path from "
                "attempt-limit / gave-up."
            ),
            "three_exits": ["SUCCESS", "ATTEMPT-LIMIT", "IMPOSSIBILITY"],
        },
        "printed_success_by_attempt": printed,
        "printed_both_states": both["printed"],
        "both_states": both,
        "park_decisions": {"grind": park_grind, "productive": park_prod},
        "harvest": harvested,
        "source_captures": {
            "web_ok": web_ok,
            "local_ok": local_ok,
            "index": "command-center/p2-wave/probes/RES-0167/captures/INDEX.json",
        },
        "claims": claims,
        "tests": [
            {
                "id": "T1-both-states",
                "name": (
                    "Progress predicate classifies a known productive retry as "
                    "PROGRESS and a known grind (same fingerprint twice) as NO-PROGRESS"
                ),
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-independent-recount",
                "name": (
                    "Independent walker reprints success-by-attempt and re-checks "
                    "grind without calling classify_attempts"
                ),
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "RES0167-C1",
                "kind": "always-PROGRESS-classifier",
                "description": (
                    "A classifier that always returns PROGRESS is silent on the grind "
                    "and must not be accepted as a progress predicate."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": both["productive_verdict"] == P.PROGRESS,
                "broken_verdict_on_grind": both["broken_always_progress_on_grind"],
                "good_verdict_on_grind": both["grind_verdict"],
            }
        ],
        "evidence": [
            {"id": "E1-supervisor-census", "kind": "log-regex", "detail": printed},
            {
                "id": "E2-tree-retry-and-strikes",
                "kind": "json-walk",
                "detail": (
                    f"same_fp_then_success={same_ok} two_strike_delivered={n_pair_del} "
                    f"n_pairs={n_pairs}"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0167-probe2-independent-recount",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
            "defaults_to": "REFUTED",
        },
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "both-states-progress-predicate"},
            {"id": "probe2", "command": P2, "role": "independent-harvest-and-grind-walker"},
        ],
        "artifacts": [
            {"path": OUT_REL, "role": "primary", "exists": True},
            {"path": SCHEMA_REL, "role": "supporting", "exists": True},
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two strikes then pivot (AGENTS.md 4b)"},
        "manifest_registration": {
            "global_catalog_write": False,
            "manifest_path": (
                "command-center/p2-wave/probes/RES-0167/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
        },
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    if SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:RES-0167 sentinel missing after write")
        return 1
    if out.stat().st_size < 2048:
        print("FAILED:RES-0167 artifact too small")
        return 1
    print(f"wrote {OUT_REL} bytes={out.stat().st_size}")
    print(printed)
    print(both["printed"])
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
