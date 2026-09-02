#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0094-participant-dominance-airtime.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common as C  # noqa: E402
import probe1_shares as P1  # noqa: E402
import probe2_loo as P2  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0094 {msg}")
    return 1


def art(rel: str, role: str, exists: bool | None = None) -> dict:
    path = C.REPO / rel
    present = path.is_file() if exists is None else exists
    row = {"path": rel, "exists": present, "role": role}
    if present:
        row["bytes"] = path.stat().st_size
    return row


def verdicts(fx: dict, loo: dict) -> list[dict]:
    off, on, rest, bal = (
        fx["flood_off"],
        fx["flood_on"],
        fx["restate_off"],
        fx["balanced"],
    )
    return [
        {
            "target_id": "volume-token-capture-uncapped",
            "verdict": "CONFIRMED",
            "detail": (
                f"loud token_share={off['token_share']['loud']:.3f} "
                f"(threshold {C.CAPTURE})"
            ),
        },
        {
            "target_id": "volume-token-capture-quota-on",
            "verdict": "REFUTED",
            "detail": (
                f"loud token_share={on['token_share']['loud']:.3f} after "
                f"quota={C.QUOTA_ON}; CNL-0047 throttles loud "
                f"{on['throttles'].get('loud')}"
            ),
        },
        {
            "target_id": "unique-idea-capture-uncapped",
            "verdict": "CONFIRMED",
            "detail": (
                f"loud idea_share={off['idea_share']['loud']:.3f}; "
                f"unique-idea rec={off['recommendation']['idea_id']}"
            ),
        },
        {
            "target_id": "unique-idea-capture-quota-on",
            "verdict": "REFUTED",
            "detail": (
                f"loud idea_share={on['idea_share']['loud']:.3f}; "
                f"rec={on['recommendation']['idea_id']}"
            ),
        },
        {
            "target_id": "speaking-first-framing",
            "verdict": "CONFIRMED",
            "detail": (
                "first SPEAK is loud with quota off and on; CNL-0047 "
                "round-robin does not rotate the opener"
            ),
        },
        {
            "target_id": "loo-influence-uncapped",
            "verdict": "CONFIRMED",
            "detail": (
                f"removing loud changes rec {loo['flood_off']['base_rec']} -> "
                f"{loo['flood_off']['loo_rec']}; outcome_delta="
                f"{loo['flood_off']['outcome_delta']:.3f}"
            ),
        },
        {
            "target_id": "loo-influence-quota-on",
            "verdict": "REFUTED",
            "detail": (
                f"removing loud leaves rec {loo['flood_on']['loo_rec']}; "
                f"quota pins the unique-idea outcome"
            ),
        },
        {
            "target_id": "balanced-council-capture",
            "verdict": "REFUTED",
            "detail": (
                f"balanced max token_share="
                f"{max(bal['token_share'].values()):.3f}; every LOO keeps "
                f"{bal['recommendation']['idea_id']}"
            ),
        },
        {
            "target_id": "restate-token-weighted-vs-unique",
            "verdict": "CONFIRMED",
            "detail": (
                "restatement flood: token-weighted rec="
                f"{rest['token_weighted_recommendation']['idea_id']} while "
                f"unique-idea rec={rest['recommendation']['idea_id']}"
            ),
        },
    ]


def main() -> int:
    p1 = P1.payload()
    p2 = P2.payload()
    if not p1.get("pass"):
        return fail("probe1 invariants " + "; ".join(p1.get("fails") or []))
    if not p2.get("pass") or not p2.get("independent_matches_base"):
        return fail("probe2 invariants " + "; ".join(p2.get("fails") or []))

    loo = C.loo_runs()
    fx = loo["fixtures"]
    p1_raw = (
        json.dumps(p1, sort_keys=True, default=str)
        + "\n"
        + (
            "flood_off loud token={:.3f} idea={:.3f} rec={} first={} | "
            "flood_on loud token={:.3f} idea={:.3f} rec={} throttles={}\n".format(
                p1["flood_off"]["token_share"].get("loud", 0),
                p1["flood_off"]["idea_share"].get("loud", 0),
                p1["flood_off"]["recommendation"].get("idea_id"),
                p1["flood_off"]["first_speaker"],
                p1["flood_on"]["token_share"].get("loud", 0),
                p1["flood_on"]["idea_share"].get("loud", 0),
                p1["flood_on"]["recommendation"].get("idea_id"),
                p1["flood_on"]["throttles"].get("loud"),
            )
        )
        + "SUCCESS:ADV-0094-probe1 shares: uncapped volume capture; "
        "quota redistributes tokens and unique ideas; first speaker unchanged"
    )
    p2_raw = (
        json.dumps(
            {k: v for k, v in p2.items() if k != "fails"},
            sort_keys=True,
            default=str,
        )
        + "\n"
        + (
            "loo_off rec {} -> {} changed={} delta={:.3f} | "
            "loo_on rec {} -> {} changed={} delta={:.3f}\n".format(
                p2["flood_off"]["base_rec"],
                p2["flood_off"]["loo_rec"],
                p2["flood_off"]["rec_changed"],
                p2["flood_off"]["outcome_delta"],
                p2["flood_on"]["base_rec"],
                p2["flood_on"]["loo_rec"],
                p2["flood_on"]["rec_changed"],
                p2["flood_on"]["outcome_delta"],
            )
        )
        + "SUCCESS:ADV-0094-probe2 leave-one-out: uncapped outcome moves; "
        "quota pins recommendation; balanced control is stable"
    )

    targets = verdicts(fx, loo)
    now = datetime.now(timezone.utc).replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    supporting = [
        C.SCHEMA_REL,
        "command-center/p2-wave/probes/CNL-0047/scheduler.py",
        "tools/council/budget/engagement.py",
        "command-center/p2-wave/probes/ADV-0094/common.py",
        "command-center/p2-wave/probes/ADV-0094/probe1_shares.py",
        "command-center/p2-wave/probes/ADV-0094/probe2_loo.py",
    ]
    artifacts = [art(p, "supporting") for p in supporting]
    missing = [a["path"] for a in artifacts if not a["exists"]]
    if missing:
        return fail(f"missing supporting {missing}")

    doc = {
        "unit_id": C.UNIT_ID,
        "id": C.UNIT_ID,
        "state": "SUCCESS",
        "sentinel": C.CATALOG_SENTINEL,
        "completion_sentinel": C.CATALOG_SENTINEL,
        "report_kind": "council-pathology-sim",
        "title": "Participant dominance and airtime capture",
        "question": C.QUESTION,
        "question_or_target": C.QUESTION,
        "spec_anchor": "_USER-PROMPTS.md:10928, 11230",
        "mechanism": (
            "token/idea/attribution share on the live CNL-0047 scheduler plus "
            "IMP-0299 engagement scoring, and a leave-one-out counterfactual "
            "that measures influence by recommendation and unique-set change"
        ),
        "answer": (
            "Without a speaking quota, a verbose first speaker captures token "
            f"share ({fx['flood_off']['token_share']['loud']:.3f}) and unique-idea "
            f"share ({fx['flood_off']['idea_share']['loud']:.3f}); removing that "
            "seat changes the unique-idea recommendation. CNL-0047 quotas bound "
            "token and unique-idea share and pin the leave-one-out outcome. "
            "Quota does not change who speaks first. Restated duplicates capture "
            "token-weighted synthesis but not unique-idea synthesis. Empty acks "
            "are messages with zero content units and fail the engagement floor. "
            "A balanced council is the sensitivity control: no seat dominates "
            "and every single removal leaves the recommendation unchanged."
        ),
        "overall_verdict": "PARTIAL",
        "targets": targets,
        "evidence": [
            {
                "id": "E-PROBE1-SHARES",
                "claim": "uncapped flood: loud owns a majority of tokens and unique ideas",
                "verdict": "CONFIRMED",
                "anchor": "probe1_shares.py:flood_off",
            },
            {
                "id": "E-PROBE1-QUOTA",
                "claim": "quota=40 redistributes token and unique-idea share below 0.50",
                "verdict": "REFUTED",
                "anchor": "probe1_shares.py:flood_on",
            },
            {
                "id": "E-PROBE2-LOO-UNCAPPED",
                "claim": "influence is the uncapped leave-one-out recommendation change",
                "verdict": "CONFIRMED",
                "anchor": "probe2_loo.py:flood_off",
            },
            {
                "id": "E-PROBE2-LOO-QUOTA",
                "claim": "with quota, removing loud does not change the recommendation",
                "verdict": "REFUTED",
                "anchor": "probe2_loo.py:flood_on",
            },
            {
                "id": "E-BALANCED-CONTROL",
                "claim": "even council: low token concentration and zero LOO rec change",
                "verdict": "REFUTED",
                "anchor": "probe2_loo.py:balanced",
            },
            {
                "id": "E-ACK-FLOOR",
                "claim": "three acks are messages and zero content units; floor fails",
                "verdict": "CONFIRMED",
                "anchor": "tools/council/budget/engagement.py:score_text",
            },
        ],
        "tests": [
            {
                "id": "T-PROBE-1-SHARES",
                "name": "token/idea/attribution shares on live scheduler",
                "command": C.P1_CMD,
                "result": "PASS",
            },
            {
                "id": "T-PROBE-2-LOO",
                "name": "leave-one-out outcome delta",
                "command": C.P2_CMD,
                "result": "PASS",
            },
            {
                "id": "T-BALANCED-CONTROL",
                "name": "even council low outcome delta for any single removal",
                "command": C.P2_CMD,
                "result": "PASS",
            },
            {
                "id": "T-ACK-FLOOR",
                "name": "empty acknowledgements fail the engagement floor",
                "command": C.P1_CMD,
                "result": "PASS",
            },
            {
                "id": "T-RESTATE-UNIQUENESS",
                "name": "restatements capture token-weighted rec not unique-idea rec",
                "command": C.P1_CMD,
                "result": "PASS",
            },
            {
                "id": "T-INDEPENDENT-REDERIVE",
                "name": "probe2 re-derives uncapped rec from unique_by_author",
                "command": C.P2_CMD,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-MESSAGE-COUNT-VS-CONTENT",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state": "count quiet acknowledgements as influence",
                "good_state": "IMP-0299 content_units on the same acks",
                "note": "quiet posted 3 messages and 0 content units; meets_floor=False",
            },
            {
                "id": "NC-TOKEN-WEIGHTED-ON-RESTATE",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state": "token-weighted synthesis on restated duplicates",
                "good_state": "unique-idea synthesis on the same restatement flood",
            },
        ],
        "named_probes": [
            {
                "id": "probe1",
                "command": C.P1_CMD,
                "role": "token-idea-attribution-shares",
                "raw_output": p1_raw,
            },
            {
                "id": "probe2",
                "command": C.P2_CMD,
                "role": "leave-one-out-outcome-delta",
                "raw_output": p2_raw,
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0094-probe2-loo-rederive",
            "verdict": "PASS",
            "independent": True,
            "vendor": "mechanical-rederive",
            "note": (
                "Re-derives the uncapped unique-idea recommendation from "
                "unique_by_author / first_idea_by_author. Does not read "
                "targets[].verdict."
            ),
        },
        "produced_by": {
            "role": "groupthink-red-teamer",
            "execution_substrate": "local-parallel-headless-linux",
        },
        "downstream_consumers": [
            "CNL-0088",
            "CNL-0047",
            "IMP-0299",
            "TST-0275",
        ],
        "defects": [],
        "timestamp_utc": now,
        "cloud_ok": False,
        "runs": {
            "flood_off": C.compact_run(fx["flood_off"]),
            "flood_on": C.compact_run(fx["flood_on"]),
            "restate_off": C.compact_run(fx["restate_off"]),
            "restate_on": C.compact_run(fx["restate_on"]),
            "balanced": C.compact_run(fx["balanced"]),
            "loo_flood_off": loo["flood_off"],
            "loo_flood_on": loo["flood_on"],
            "loo_balanced": loo["balanced"],
        },
        "probe1": {k: v for k, v in p1.items() if k != "fails"},
        "probe2": {k: v for k, v in p2.items() if k != "fails"},
        "artifacts": [{"path": C.ART_REL, "exists": True, "role": "primary"}]
        + artifacts,
    }

    schema = json.loads((C.REPO / C.SCHEMA_REL).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        return fail("schema " + "; ".join(e.message for e in errs[:8]))
    garbage_counts = []
    for probe in (
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
    ):
        garbage_counts.append(sum(1 for _ in validator.iter_errors(probe)))
    if min(garbage_counts) < 3:
        return fail(f"schema vacuous {garbage_counts}")
    doc["schema_garbage_error_counts"] = garbage_counts

    C.ART.parent.mkdir(parents=True, exist_ok=True)
    C.ART.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {C.ART_REL} bytes={C.ART.stat().st_size}")
    print("SUCCESS:ADV-0094 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
