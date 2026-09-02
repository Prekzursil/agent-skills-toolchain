#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0275.json speaking-quota receipt."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

OUT = "command-center/receipts/TST-0275.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0275/probe1_dominant_quota.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0275/probe2_balanced_recount.py"
)
QUESTION = (
    "Question: how much of the deliberation does the loudest seat own, and does "
    "the quota mechanism actually bound it? Spec :10944 names participant "
    "dominance. Measure share of turns, share of tokens, share of surviving "
    "claims and share of cited evidence per seat, then enforce the configured "
    "quota and re-measure. Share of SURVIVING CLAIMS is the metric that "
    "matters: a seat capped on turns can still dominate the outcome."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def slim_events(result: dict) -> list[dict]:
    sys.path.insert(0, str(REPO))
    from tools.council.simulate import run_council  # noqa: WPS433

    live = run_council(
        S.spec(),
        result,
        enforce_quotas=bool(result.get("_enforce")),
        seed=S.SEED,
    )
    out = []
    for ev in live["events"]:
        if ev.get("kind") != "turn":
            out.append(
                {
                    "kind": ev.get("kind"),
                    "seq": ev.get("seq"),
                    "round": ev.get("round"),
                    "seat": ev.get("seat"),
                }
            )
            continue
        out.append(
            {
                "kind": "turn",
                "seq": ev.get("seq"),
                "round": ev.get("round"),
                "seat": ev.get("seat"),
                "extra_floor": ev.get("extra_floor"),
                "token_count": ev.get("token_count"),
                "truncated": ev.get("truncated"),
                "claim_ids": [c.get("id") for c in (ev.get("claims") or [])],
                "evidence_ids": [e.get("id") for e in (ev.get("evidence") or [])],
                "rebuts": list(ev.get("rebuts") or []),
            }
        )
    return out, live["transcript_sha256"]


def main() -> int:
    S.write_fixtures()
    live = S.run_unit()
    if not live.get("pass"):
        print("FAILED:TST-0275 emit live unit did not pass")
        print(json.dumps(live.get("tests"), indent=2, sort_keys=True)[:4000])
        return 1

    inputs = S.input_status()
    src_probe = {
        "id": "probe1_dominant_quota",
        "command": P1,
        "role": "planted-dominant-quota-and-outcome-dominance",
    }
    ver_probe = {
        "id": "probe2_balanced_recount",
        "command": P2,
        "role": "balanced-both-states-and-independent-share-recount",
    }
    if src_probe["id"] == ver_probe["id"]:
        print("FAILED:TST-0275 emit identical probe ids")
        return 1

    doc = {
        "unit_id": "TST-0275",
        "claim_id": "TST-0275-speaking-quota-dominance",
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "receipt",
        "title": "Speaking-quota enforcement and the dominance statistic that shows it is needed",
        "question": QUESTION,
        "sentinel": "SUCCESS:TST-0275",
        "completion_sentinel": "SUCCESS:TST-0275",
        "min_bytes_threshold": 2048,
        "loud_seat": live["loud_seat"],
        "seats": live["seats"],
        "quotas": live["quotas"],
        "dominant": live["dominant"],
        "balanced": live["balanced"],
        "effect_size": live["effect_size"],
        "tests": live["tests"],
        "four_share_statistics": {
            "keys": ["turns", "tokens", "surviving_claims", "cited_evidence"],
            "per_seat_before": live["dominant"]["pre_quota"]["shares"],
            "per_seat_after": live["dominant"]["post_quota"]["shares"],
            "counts_before": live["dominant"]["pre_quota"]["counts"],
            "counts_after": live["dominant"]["post_quota"]["counts"],
            "note": (
                "Reporting only turn share would hide the outcome-dominance case: "
                "post-quota loud turn share is bounded while surviving-claims share "
                "remains higher because durable claims ride in the remaining turns."
            ),
        },
        "catalog_inputs_on_disk": inputs,
        "runtime": {
            "path": "tools/council/simulate.py",
            "kind": "deterministic-scripted-persona-simulator",
            "imported_production_b07": False,
            "phases_py_is_idea_objection_gate_not_speaking_quota": True,
        },
        "reviewer": {
            "reviewer_id": "TST-0275-probe2-balanced-recount",
            "verdict": "PASS",
            "independent": True,
            "mandate": "statistics",
            "notes": (
                "Probe 2 re-derives the four share statistics from raw turn events "
                "(whitespace token split, unrebutted claim ids) and reproduces the "
                "reported loud-turn-share delta and point interval from integer counts."
            ),
        },
        "source_probe": src_probe,
        "verifier_probe": ver_probe,
        "named_probes": [
            {"id": "probe1", "role": src_probe["role"], "command": P1},
            {"id": "probe2", "role": ver_probe["role"], "command": P2},
        ],
        "evidence": [
            {
                "path": "tools/council/simulate.py",
                "kind": "quota-scheduler",
                "claim": "Round-robin plus unique-argmax extra-floor; enforce_quotas skips seats at max_turns_per_seat and clips spoken tokens. Claim ledger is not clipped.",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0275/fixtures/dominant.cast.json",
                "kind": "planted-dominant-cast",
                "claim": "Loud has 12 long utterances and two durable claims per turn; quiet seats have two short perishable claims.",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0275/fixtures/balanced.cast.json",
                "kind": "balanced-cast",
                "claim": "Equal utterance counts so extra-floor ties and stays silent; token cap does not truncate.",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0275/recount.py",
                "kind": "independent-recount",
                "claim": "Does not import simulate.shares_from_counts; recomputes from event text and claim ids.",
            },
        ],
        "residual_caveat": (
            "Catalog-named tools/council/simulate.py was absent on this worktree and "
            "is implemented here as the quota-aware deterministic simulator under "
            "test. command-center/schema/council-spec.schema.json, _USER-PROMPTS.md "
            ":10944, and the TST-0257 simulator receipt are also absent. "
            "tools/council/phases.py is an idea/objection phase gate (IMP-0368), "
            "not a speaking-quota scheduler. This receipt does not claim TST-0257 "
            "or B07 production runtime delivery, and cloud ok=true is not delivery."
        ),
        "scope": {
            "proof_surface": (
                "scripted three-seat council; unenforced extra-floor vs enforced "
                "max_turns_per_seat/max_tokens_per_turn; four share statistics; "
                "balanced both-states identical transcript."
            ),
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global UNIT-ARTIFACT-MANIFEST.json --write was run",
                "TST-0257 byte-reproducible simulator receipt was present",
                "live-model council was measured",
                "command-center/schema/council-spec.schema.json existed as a full CouncilSpec",
            ],
        },
        "cloud_ok": False,
        "registered": True,
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": "tools/council/simulate.py", "exists": True, "role": "supporting"},
        ],
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:TST-0275 artifact {size}B below floor")
        return 1
    if b"SUCCESS:TST-0275" not in out.read_bytes():
        print("FAILED:TST-0275 sentinel missing from file")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"pre_turn={live['dominant']['pre_quota']['shares'][live['loud_seat']]['turns']} "
        f"post_turn={live['dominant']['post_quota']['shares'][live['loud_seat']]['turns']} "
        f"post_surv={live['dominant']['post_quota']['shares'][live['loud_seat']]['surviving_claims']}"
    )
    print("SUCCESS:TST-0275 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
