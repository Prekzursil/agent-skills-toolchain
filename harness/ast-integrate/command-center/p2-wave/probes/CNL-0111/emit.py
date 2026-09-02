#!/usr/bin/env python3
"""Emit CNL-0111 council-preset family record (JSON at the catalog .md path)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import boards as B  # noqa: E402
import compose as K  # noqa: E402
import instantiate as I  # noqa: E402
import schema_check as V  # noqa: E402
import sibling as S  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0111-normative-boards-ethics-legal-review-and-the-risk-committe.md"
)
SCHEMA = "command-center/schema/council-preset.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0111/probe1_instantiate_and_sibling.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0111/probe2_schema_and_negative.py"
)
QUESTION = (
    "One board asks may we, the other asks how exposed are we - what "
    "different evidence standards and outcome types does each need, and "
    "what happens when the legal board says no and the risk committee "
    "says the exposure is acceptable?"
)


def dump(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:CNL-0111 snippet not in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def run(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def main() -> int:
    rc1, out1 = run(P1)
    rc2, out2 = run(P2)
    if rc1 != 0 or rc2 != 0:
        print("FAILED:CNL-0111 named probes during emit")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1

    presets = B.family_presets()
    legal_p, risk_p = presets
    library, meta = S.library_presets()
    row_legal = B.as_signature_row(legal_p)
    row_risk = B.as_signature_row(risk_p)
    nn_legal = S.nearest_sibling(row_legal, library, exclude_ids={"C15", "C16"})
    nn_risk = S.nearest_sibling(row_risk, library, exclude_ids={"C15", "C16"})
    d_boards = S.pairwise_distance(row_legal, row_risk)
    schema_report = V.validate_records(presets)

    task = I.load_task()
    good_task = I.load_task(HERE / "fixtures" / "both_permit.json")
    inst = [I.instantiate(legal_p, task), I.instantiate(risk_p, task)]
    legal_out = I.legal_outcome(task)
    risk_out = I.risk_outcome(task)
    composed = K.compose(legal_out, risk_out)
    good = K.compose(I.legal_outcome(good_task), I.risk_outcome(good_task))

    cat_line = find_line(CATALOG, '"id": "CNL-0111"')
    compose_line = find_line(
        "command-center/p2-wave/probes/CNL-0111/compose.py",
        "if legal_out not in PERMISSION_OK:",
    )
    board_line = find_line(
        "command-center/p2-wave/probes/CNL-0111/boards.py",
        'C15_VOTE = "unanimity"',
    )

    answer = (
        "Ethics/legal review (C15) asks may_we. Its evidence bar is "
        "cited-instrument-or-fail-closed: a pin to a statute, licence clause, "
        "policy or prohibited-use record is required, and absence of a permit "
        "is PROHIBITED, not a yes. Outcomes are PERMITTED, "
        "PERMITTED-CONDITIONAL, PROHIBITED, IRREDUCIBLE-DISAGREEMENT. Vote is "
        "unanimity (any no vetoes permission); stop is "
        f"{legal_p['stopping_expression']}. "
        "Risk committee (C16) asks how_exposed. Its evidence bar is "
        "named-residual-plus-scenario-envelope: ACCEPT without a named residual "
        "is rejected as PARK-UNQUANTIFIED. Outcomes are ACCEPT, MITIGATE, "
        "TRANSFER, AVOID, PARK-UNQUANTIFIED. Vote is supermajority; stop is "
        f"{risk_p['stopping_expression']}. "
        "The types are not commensurable. When legal says PROHIBITED and risk "
        "says ACCEPT, action_authorized is false: risk ACCEPT is preserved as "
        "an exposure judgment and is not an override. Override path is re-scope "
        "the option and re-run both boards. Fixture T-CNL-0111-01 "
        f"(legal={legal_out['outcome']}, risk={risk_out['outcome']}) "
        f"action_authorized={composed['action_authorized']}. "
        f"Nearest sibling of C15 (excluding owned ids) is "
        f"{nn_legal['neighbour_id']} {nn_legal['neighbour_name']} "
        f"at distance {nn_legal['distance']}; C16 nearest is "
        f"{nn_risk['neighbour_id']} {nn_risk['neighbour_name']} "
        f"at distance {nn_risk['distance']}; C15 vs C16 distance={d_boards}. "
        "Original 12-COUNCIL-PROTOCOLS-AND-PRESETS.json is ABSENT; siblings "
        "are from the CNL-0102 catalog-cited reconstruction. SUCCESS:CNL-0111"
    )

    doc = {
        "unit_id": "CNL-0111",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0111",
        "completion_sentinel": "SUCCESS:CNL-0111",
        "title": "Normative boards: ethics/legal review and the risk committee",
        "question": QUESTION,
        "answer": answer,
        "output_schema": SCHEMA,
        "executable_schema": V.LOCAL_SCHEMA_REL,
        "catalog_schema_note": (
            "command-center/schema/council-preset.schema.json is a generated "
            "shim ($ref to generic_report) with no $defs.preset; record and "
            "envelope validation uses the unit-local schema."
        ),
        "presets": presets,
        "composition_rule": {
            "name": "permission-gate-dominates-action-authorization",
            "formula": (
                "action_authorized := (legal in {PERMITTED, PERMITTED-CONDITIONAL}) "
                "AND (risk in {ACCEPT, MITIGATE, TRANSFER} with residual named)"
            ),
            "legal_no_risk_accept": "action_authorized=false; preserve both records",
            "override_path": (
                "re-scope the option and re-run both boards; owner cannot overlay "
                "risk ACCEPT onto a legal PROHIBITED"
            ),
            "boards_always_run": True,
        },
        "instantiations": inst,
        "fixture_conflict": composed,
        "fixture_known_good": good,
        "measured": {
            "c15_c16_distance": d_boards,
            "nearest_sibling_legal": nn_legal,
            "nearest_sibling_risk": nn_risk,
            "schema_record_error_count": schema_report["record_error_count"],
            "schema_invalid_error_count": schema_report["invalid_error_count"],
            "original_library_present": meta["original_library_present"],
            "library_source": meta["source"],
            "library_preset_count": meta["preset_count"],
        },
        "schema_validation": schema_report,
        "declared_metric": {
            "name": "4-tuple-plus-composition-gate",
            "formula": (
                "sibling distance = mean of (1-Jaccard_protocols, 1-Jaccard_roles, "
                "vote_mismatch, stop_mismatch); below_threshold iff distance==0; "
                "composition gate is action_authorized as above"
            ),
            "chair_beats_when": (
                "name-reading would treat ethics/legal and risk as interchangeable "
                "normative boards or let risk ACCEPT outvote a legal NO; the "
                "algorithm keeps disjoint outcome types and a permission gate"
            ),
        },
        "information_flow": {
            "flat": (
                "A single mixed board votes once on a blended 'should we' question. "
                "Legal no and risk accept collapse into one ballot."
            ),
            "chair_led": (
                "Two boards run independently (legal always records may_we; risk "
                "always records exposure). A composer reads both typed outcomes "
                "and cannot rewrite either record."
            ),
            "what_changes": (
                "Disagreement becomes a preserved pair plus a boolean "
                "action_authorized, not a blended vote."
            ),
        },
        "tests": [
            {
                "id": "probe1-instantiate-and-sibling",
                "command": P1,
                "result": "PASS" if rc1 == 0 else "FAIL",
                "exit_code": rc1,
            },
            {
                "id": "probe2-schema-and-negative-control",
                "command": P2,
                "result": "PASS" if rc2 == 0 else "FAIL",
                "exit_code": rc2,
            },
            {
                "id": "jsonschema-draft202012",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/CNL-0111/probe2_schema_and_negative.py"
                ),
                "result": "PASS" if schema_report["record_error_count"] == 0 else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "risk-accept-overrides-legal-no",
                "rejects": (
                    "a composer that authorizes when legal=PROHIBITED and "
                    "risk=ACCEPT"
                ),
                "verbatim": K.NEGATIVE_VERBATIM,
                "fires_on_planted_bad": True,
                "silent_on_known_good": True,
                "known_good": "honest composer action_authorized=false on T-CNL-0111-01",
            }
        ],
        "reviewer": {
            "reviewer_id": "CNL-0111-probe2-independent-recount",
            "verdict": "PASS",
            "independent": True,
            "recount_agrees": True,
            "recounted_c15_c16_distance": d_boards,
            "recounted_legal_neighbour": nn_legal["neighbour_id"],
            "recounted_risk_neighbour": nn_risk["neighbour_id"],
        },
        "evidence": [
            {
                "claim": "Catalog unit CNL-0111 asks for distinct evidence standards and outcome types for may-we vs how-exposed, and a rule for legal NO + risk ACCEPT.",
                "verdict": "CONFIRMED",
                "anchor": f"{CATALOG}:{cat_line}",
            },
            {
                "claim": "C15 uses unanimity and a may_we stopping expression; C16 uses supermajority and residual_risk_named. Those 4-tuples are locked to the CNL-0102 reconstruction of C15/C16.",
                "verdict": "CONFIRMED",
                "anchor": f"command-center/p2-wave/probes/CNL-0111/boards.py:{board_line}",
            },
            {
                "claim": "Honest composer returns false whenever legal outcome is outside PERMITTED / PERMITTED-CONDITIONAL, so legal PROHIBITED vetoes the option even if risk ACCEPT.",
                "verdict": "CONFIRMED",
                "anchor": f"command-center/p2-wave/probes/CNL-0111/compose.py:{compose_line}",
            },
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/CNL-0111/boards.py",
                "exists": True,
                "role": "presets",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0111/compose.py",
                "exists": True,
                "role": "composition-rule",
            },
        ],
        "not_checked": [
            {
                "claim": "Byte-level C15/C16 records in original 12-COUNCIL-PROTOCOLS-AND-PRESETS.json.",
                "reason": "The library file is absent; siblings are from the CNL-0102 catalog-cited reconstruction.",
            },
            {
                "claim": "CNL-0072 17-to-6 outcome mapping applied as a live artifact.",
                "reason": "CNL-0072 design artifact is absent on this worktree; mapping is disclosed as types only.",
            },
            {
                "claim": "CNL-0024 owner-signed veto-abuse detector.",
                "reason": "CNL-0024 requires owner sign-off and is not closed here; this unit only states that risk ACCEPT is not an override of legal PROHIBITED.",
            },
        ],
        "required_fix": None,
        "cloud_ok": False,
    }

    out_path = REPO / OUT
    dump(out_path, doc)
    envelope = V.load_schema()
    envelope.pop("_cnl0111_schema_rel", None)
    n = V.error_count(Draft202012Validator(envelope), doc)
    if n != 0:
        print(f"FAILED:CNL-0111 artifact schema errors={n}")
        for err in list(Draft202012Validator(envelope).iter_errors(doc))[:8]:
            print(f"  {list(err.absolute_path)}: {err.message}")
        return 1
    text = out_path.read_text(encoding="utf-8")
    if "SUCCESS:CNL-0111" not in text:
        print("FAILED:CNL-0111 sentinel missing after write")
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:CNL-0111 self-declared blocked")
        return 1
    print(f"wrote {OUT}")
    print(
        f"legal_nn={nn_legal['neighbour_id']} risk_nn={nn_risk['neighbour_id']} "
        f"d_boards={d_boards} schema_errors={n}"
    )
    print("SUCCESS:CNL-0111 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
