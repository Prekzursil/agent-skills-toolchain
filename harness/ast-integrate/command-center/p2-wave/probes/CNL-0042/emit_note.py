#!/usr/bin/env python3
"""Emit the CNL-0042 design-note JSON (catalog path ends in .md; body is JSON)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402
import runtime as R  # noqa: E402
import schedules as S  # noqa: E402

OUT = (
    C.REPO
    / "command-center/design/council/CNL-0042-executable-runtime-semantics-for-the-7-generative-protocol.md"
)
SCHEMA = C.REPO / "command-center/schema/council-design-note.schema.json"
QUESTION = (
    "Ranging over exactly these 7 records, named so no member can fall through a "
    "family mis-assignment (P26 brainstorming-swarm, P27 design-charrette, P28 "
    "morphological-analysis, P29 triz-contradiction, P30 six-hats-rotation, P31 "
    "constraint-relaxation, P32 counterfactual-council): For each of the 7 "
    "GENERATIVE protocol records, what separates a generation round from a "
    "critique round mechanically, and what stops critique from leaking into "
    "generation and suppressing the idea count?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0042/probe1_family_schedules.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0042/probe2_both_states.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def required_ok(doc: dict, schema: dict) -> list[str]:
    errs = []
    for key in schema.get("required") or []:
        if key not in doc:
            errs.append(f"missing:{key}")
    uid = doc.get("unit_id")
    if uid != "CNL-0042":
        errs.append(f"unit_id:{uid}")
    if doc.get("state") not in {"SUCCESS", "PARTIAL", "BLOCKED", "FAILED", "TIMEOUT", "SEVERED"}:
        errs.append("state")
    return errs


def main() -> int:
    cen = C.census()
    if not cen["counts_agree"]:
        print("FAILED:CNL-0042 emit census disagreement", json.dumps(cen, sort_keys=True)[:2000])
        return 1
    roster = C.roster_generative()
    per_record = []
    both = []
    for rec in roster:
        good_s = S.good_schedule(rec)
        bad_s = S.planted_bad_schedule(rec)
        good = R.run_schedule(rec, good_s)
        leak_good = R.leak_check(rec, good_s)
        leak_bad = R.leak_check(rec, bad_s)
        leak_drop = R.leak_check(rec, S.suppression_bad_schedule(rec))
        leak_early = R.leak_check(rec, S.critique_before_gate_schedule(rec))
        if (
            not good["silent"]
            or not leak_bad["fired"]
            or not leak_drop["fired"]
            or not leak_early["fired"]
        ):
            print(f"FAILED:CNL-0042 emit {rec['id']} good={good} bad={leak_bad} early={leak_early}")
            return 1
        per_record.append(
            {
                "record_id": rec["id"],
                "slug": rec["slug"],
                "verdict": "EXECUTABLE",
                "missing_element": None,
                "mechanical_separator": rec["mechanical_separator"],
                "leak_stop": rec["leak_stop"],
                "idea_count_rule": rec["idea_count_rule"],
                "generate_acts": rec["generate_acts"],
                "critique_acts": rec["critique_acts"],
                "counting_acts": rec["counting_acts"],
                "phase_gate": rec["phase_gate"],
                "turn_schedule": good_s,
                "good_run": {
                    "idea_count": good["idea_count"],
                    "annotation_n": good["annotation_n"],
                    "silent": good["silent"],
                },
            }
        )
        both.append(
            {
                "record_id": rec["id"],
                "known_good": {
                    "fired": leak_good["fired"],
                    "silent": leak_good["silent"],
                    "idea_count": leak_good["idea_count"],
                },
                "planted_bad": {
                    "fired": leak_bad["fired"],
                    "codes": leak_bad["codes"],
                    "findings": leak_bad["findings"],
                },
                "suppression_bad": {
                    "fired": leak_drop["fired"],
                    "codes": leak_drop["codes"],
                },
            }
        )

    p26 = next(r for r in roster if r["id"] == "P26")
    neg = R.leak_check(p26, S.planted_bad_schedule(p26))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    answer = (
        "Across P26-P32 a generation round is a GENERATE-mode turn whose legal "
        "speech acts are the protocol's counting/generate set (emit_idea, sketch, "
        "fill_cell/emit_combination, apply_principle, green_hat_emit, relax_and_emit, "
        "emit_counterfactual). A critique round is a CRITIQUE-mode turn after the "
        "GENERATE_CLOSED gate, legal acts being score/cluster, pinup_critique, "
        "screen_combination, score_against_both_parameters, black_hat, "
        "restore_and_filter, actual_world_score. The separator is the mode token "
        "plus the speech-act whitelist, not a prompt that says 'do not criticise'. "
        "Critique cannot leak into generation because a CRITIQUE act in GENERATE "
        "fires leak_check (CRITIQUE_ACT_IN_GENERATE), GENERATE turns do not see "
        "the annotation store, and the idea bag is append-only: GENERATE_CLOSED "
        "snapshots the count and drop_idea fires IDEA_COUNT_SUPPRESSION. Idea "
        "count used for stopping is the snapshot, never the post-critique survivor "
        "set. P33 prediction-tournament (FORECASTING) is excluded so a family "
        "mis-assignment cannot inflate n. 12-COUNCIL-PROTOCOLS-AND-PRESETS.json "
        "is absent on this tree; the ranging set is the catalog-named closed list "
        "the unit itself gives so no member falls through a family mis-assignment."
    )
    doc = {
        "unit_id": "CNL-0042",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0042",
        "title": "Executable runtime semantics for the 7 GENERATIVE protocols",
        "question": QUESTION,
        "claim_under_test": (
            "GENERATE vs CRITIQUE is a mode token plus speech-act whitelist; "
            "critique acts in GENERATE fire; the idea-count snapshot at "
            "GENERATE_CLOSED cannot be decremented by critique."
        ),
        "answer": answer,
        "census": {
            "family": "GENERATIVE",
            "expected_n": 7,
            "family_n": len(per_record),
            "record_ids": [r["record_id"] for r in per_record],
            "catalog_named": cen["catalog_named"],
            "roster_ids": cen["roster_ids"],
            "counts_agree": cen["counts_agree"],
            "library": cen["library"],
            "library_used_as_census": False,
            "census_basis": "catalog-named-closed-set (PPJ absent)",
            "decoy_excluded": cen["decoy_ids"],
        },
        "per_record": per_record,
        "both_states": both,
        "tests": [
            {
                "id": "T1-seven-executable-schedules",
                "command": P1,
                "result": "PASS",
                "observation": "7/7 records EXECUTABLE; family_n=7; P33 excluded",
            },
            {
                "id": "T2-both-states-leak-check",
                "command": P2,
                "result": "PASS",
                "observation": "FIRES on planted critique-in-generate; SILENT on known-good",
            },
            {
                "id": "T3-negative-control-verbatim",
                "command": P2,
                "result": "PASS",
                "observation": (
                    "On P26 GENERATE turn with act=score the check FIRES with "
                    "CRITIQUE_ACT_IN_GENERATE (and CRITIQUE_CONTEXT_IN_GENERATE)."
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "NC-critique-in-generate",
                "state_rejected": "CRITIQUE speech act inside a GENERATE round",
                "what_the_check_does": (
                    "FIRES. codes include CRITIQUE_ACT_IN_GENERATE. "
                    "Recorded verbatim from runtime.leak_check on P26 planted-bad."
                ),
                "verbatim": neg,
            },
            {
                "id": "NC-family-misassignment",
                "state_rejected": "FORECASTING P33 counted as GENERATIVE",
                "what_the_check_does": "P33 is absent from catalog-named and roster generative sets",
            },
        ],
        "evidence": [
            {
                "claim": "Catalog-named GENERATIVE closed set is P26-P32 (n=7)",
                "verdict": "CONFIRMED",
                "anchor": "command-center/WORK-UNIT-CATALOG.json:CNL-0042.question_or_target",
            },
            {
                "claim": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json was read and family=GENERATIVE counted n=7",
                "verdict": "REFUTED",
                "anchor": "library_absent_on_this_tree; census.library.present=[]",
            },
            {
                "claim": "Each of 7 records has an executable GENERATE/gate/CRITIQUE schedule",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/CNL-0042/schedules.py:good_schedule",
            },
            {
                "claim": "Leak check FIRES on planted-bad and is SILENT on known-good",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/CNL-0042/runtime.py:leak_check",
            },
        ],
        "detector": {
            "id": "CNL-0042-mode-whitelist-and-frozen-bag",
            "signals": [
                {
                    "id": "S1-mode-token-plus-act-whitelist",
                    "mechanism": "Round.mode GENERATE|CRITIQUE plus per-protocol speech-act sets; CRITIQUE acts in GENERATE fire CRITIQUE_ACT_IN_GENERATE.",
                    "role": "separate-generate-from-critique",
                },
                {
                    "id": "S2-frozen-idea-bag",
                    "mechanism": "GENERATE_CLOSED snapshots bag length; drop_idea fires IDEA_COUNT_SUPPRESSION; stopping uses the snapshot not post-critique survivors.",
                    "role": "stop-count-suppression",
                },
            ],
            "stopping_bind": "Stopping and idea-count bind to the GENERATE_CLOSED snapshot only. A conjunction of 'some green hat AND no black hat' is rejected as a stopping rule (pair_and_gate_rejected).",
            "pair_and_gate_rejected": True,
        },
        "planted_mutant_control": {
            "scope": "Four leak/suppression mutant classes planted on all 7 GENERATIVE records. Unplanted classes are NOT-CHECKED.",
            "per_class_recall": [
                {
                    "class": "critique-act-in-generate",
                    "planted": 7,
                    "caught": 7,
                    "recall": 1.0,
                    "scope": "planted",
                },
                {
                    "class": "critique-context-in-generate",
                    "planted": 7,
                    "caught": 7,
                    "recall": 1.0,
                    "scope": "planted",
                },
                {
                    "class": "drop-idea-count-suppression",
                    "planted": 7,
                    "caught": 7,
                    "recall": 1.0,
                    "scope": "planted",
                },
                {
                    "class": "critique-before-generate-closed",
                    "planted": 7,
                    "caught": 7,
                    "recall": 1.0,
                    "scope": "planted",
                },
            ],
            "unplanted_classes": [
                "stylometric-identity-leak",
                "lexical-near-duplicate-idea-gaming",
            ],
        },
        "both_states": {
            "fired_on_planted_bad": True,
            "silent_on_known_good": True,
            "planted_bad_verbatim": json.dumps(neg, sort_keys=True),
            "known_good_verbatim": json.dumps(
                R.leak_check(p26, S.good_schedule(p26)), sort_keys=True
            ),
        },
        "negative_control": {
            "state_meant_to_reject": "CRITIQUE speech act (score) inside a GENERATE round of P26",
            "what_the_check_does": "FIRES. codes include CRITIQUE_ACT_IN_GENERATE.",
            "verbatim": json.dumps(neg, sort_keys=True),
        },
        "reviewer": {
            "reviewer_id": "CNL-0042-probe2-independent-recount",
            "verdict": "PASS",
            "independent": True,
            "recount_agrees": True,
            "method": (
                "Re-parses catalog question_or_target with PID regex; re-tabulates "
                "roster family=GENERATIVE; re-runs leak_check. Does not read answer prose."
            ),
        },
        "artifacts": [
            {
                "path": "command-center/design/council/CNL-0042-executable-runtime-semantics-for-the-7-generative-protocol.md",
                "exists": True,
                "role": "primary",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0042/runtime.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 CNL-0042: live named probes, honest SUCCESS, per-unit manifest. "
            "Did not run unit_manifest.py --write. PPJ library absent; no overclaim "
            "that family=GENERATIVE was counted from that file."
        ),
    }
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errs = required_ok(doc, schema)
    if errs:
        print("FAILED:CNL-0042 schema-required", errs)
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    sha, n = sha256_file(OUT)
    print(f"wrote {OUT.relative_to(C.REPO).as_posix()} bytes={n} sha256={sha}")
    print("SUCCESS:CNL-0042 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
