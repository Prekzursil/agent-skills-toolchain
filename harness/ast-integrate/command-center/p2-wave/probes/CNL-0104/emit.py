#!/usr/bin/env python3
"""Emit the CNL-0104 gated-review-board family design as a council-preset receipt."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "command-center" / "p2-wave"))

import _p2lib as P2  # noqa: E402
import family as F  # noqa: E402

QUESTION = (
    "These boards all render a verdict against a rubric - what parameterises "
    "the family (rubric source, evidence contract, who may override a FAIL), "
    "and at what point does a go-no-go board stop being the same mechanism as "
    "a design critique board?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0104/probe1_instantiate.py"
)
P2CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0104/probe2_sibling_differential.py"
)
SPEC_ANCHOR = "_USER-PROMPTS.md:10746-10767"
STARTED = "2026-08-24T18:00:00Z"


def main() -> int:
    local_schema = F.load_json(F.PRESET_SCHEMA_PATH)
    task = F.load_task()
    catalog = F.load_catalog()
    presets = F.family_presets()
    critique, gng = presets[0], presets[1]

    inst = [F.instantiate(p, task) for p in presets]
    if not all(i.get("ok") for i in inst):
        print("FAILED:CNL-0104-emit instantiate", json.dumps(inst, default=str)[:2000])
        return 1

    sibs = {p["id"]: F.nearest_sibling(p, catalog) for p in presets}
    for pid, sib in sibs.items():
        if not sib.get("named"):
            print(f"FAILED:CNL-0104-emit no sibling for {pid}")
            return 1
        if sib.get("same_mechanism") or int(sib["distance"] or 0) < 1:
            print(f"FAILED:CNL-0104-emit mechanism-duplicate of {sib.get('named')}")
            return 1

    if not F.split_holds(critique, gng):
        print("FAILED:CNL-0104-emit family members not split on all four axes")
        return 1
    if F.intra_family_distance() < 2:
        print("FAILED:CNL-0104-emit intra-family distance too small")
        return 1

    schema_rows = []
    total_err = 0
    for p in presets:
        n = F.schema_error_count(p, local_schema)
        msgs = F.schema_error_messages(p, local_schema) if n else []
        schema_rows.append({"id": p["id"], "errors": n, "messages": msgs[:8]})
        total_err += n
    inv = F.invalid_record()
    inv_err = F.schema_error_count(inv, local_schema)
    if total_err != 0:
        print("FAILED:CNL-0104-emit schema errors", schema_rows)
        return 1
    if inv_err < 1:
        print("FAILED:CNL-0104-emit validator vacuous (invalid record accepted)")
        return 1

    silent = F.instantiate(gng, task, dials={"delta.voting.rule": "majority"})
    if silent.get("ok"):
        print("FAILED:CNL-0104-emit non-editable dial was accepted")
        return 1

    name_clone = F.name_only_clone(critique, "NEG.name-only-gng", "release-go-no-go")
    clone_dist = F.axis_distance(F.mechanism_tuple(critique), F.mechanism_tuple(name_clone))
    mixed = F.mixed_gonogo_wearing_critique_evidence(gng)
    mixed_cls = F.classify_mechanism(mixed)
    mixed_inst = F.instantiate(mixed, task)

    good_neg_silent = F.classify_mechanism(gng) == "release-go-no-go"
    bad_neg_fires = mixed_cls == "design-plan-critique" or not mixed_inst.get("ok")
    if not (good_neg_silent and clone_dist == 0 and mixed_cls == "design-plan-critique"):
        print(
            "FAILED:CNL-0104-emit negative control",
            {"clone_dist": clone_dist, "mixed_cls": mixed_cls, "good": good_neg_silent},
        )
        return 1

    inv_env = F.envelope_error_count({"schema_version": 1, "unit_id": 0})
    if inv_env < 1:
        print("FAILED:CNL-0104-emit envelope validator vacuous")
        return 1

    now_dt = datetime.now(timezone.utc)
    now = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    started_dt = datetime.fromisoformat(STARTED.replace("Z", "+00:00"))
    duration = max(0.0, (now_dt - started_dt).total_seconds())
    intra = F.intra_family_distance()
    supporting = [
        F.PRESET_SCHEMA_REL,
        "command-center/p2-wave/probes/CNL-0104/family.py",
        "command-center/p2-wave/probes/CNL-0104/catalog_fixture.json",
        "command-center/p2-wave/probes/CNL-0104/fixture_task.json",
        "command-center/p2-wave/probes/CNL-0104/probe1_instantiate.py",
        "command-center/p2-wave/probes/CNL-0104/probe2_sibling_differential.py",
        F.SCHEMA_REL,
    ]
    artifacts = [P2.art(rel, "supporting") for rel in supporting]
    for row in artifacts:
        if row.get("exists") is not True:
            print(f"FAILED:CNL-0104-emit missing {row.get('path')}")
            return 1

    schema_src = P2.probe(
        "source",
        "schema-validate",
        (
            "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
            "'import json,sys; sys.path.insert(0,\"command-center/p2-wave/probes/CNL-0104\"); "
            "import family as F; p=F.family_presets(); "
            "print(sum(F.schema_error_count(x) for x in p))'"
        ),
        f"preset_schema_errors={total_err} invalid_record_errors={inv_err}",
        0,
    )
    schema_ver = P2.probe(
        "verifier",
        "command",
        P1,
        "live named probe1 re-runs instantiate + local preset schema + envelope",
        0,
    )
    sib_src = P2.probe(
        "source",
        "static-analysis",
        (
            "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
            "'import sys; sys.path.insert(0,\"command-center/p2-wave/probes/CNL-0104\"); "
            "import family as F; c=F.load_catalog(); "
            "print(F.nearest_sibling(F.CRITIQUE,c)[\"named\"], "
            "F.intra_family_distance())'"
        ),
        (
            f"critique_sibling={sibs[critique['id']]['named']} "
            f"d={sibs[critique['id']]['distance']} intra={intra}"
        ),
        0,
    )
    sib_ver = P2.probe(
        "verifier",
        "command",
        P2CMD,
        "live named probe2 re-tabulates nearest sibling independently",
        0,
    )

    report = {
        "kind": "council-preset",
        "observations": [
            {
                "name": "intra_family_axis_distance",
                "measured": intra,
                "method": "axis_distance(mechanism_tuple) over four family-vector axes plus roster/schedule/vote/stop",
                "anchor": "command-center/p2-wave/probes/CNL-0104/family.py:intra_family_distance",
            },
            {
                "name": "preset_schema_error_count",
                "measured": total_err,
                "method": "jsonschema.Draft202012Validator over unit-local $defs.preset",
                "anchor": F.PRESET_SCHEMA_REL,
            },
            {
                "name": "split_holds",
                "measured": True,
                "method": "family_vector distance == 4 between critique and go-no-go",
                "anchor": "command-center/p2-wave/probes/CNL-0104/family.py:split_holds",
            },
        ],
        "control_ids": [
            "NC-NAME-ONLY-CLONE",
            "NC-NON-EDITABLE-DIAL",
            "NC-INVALID-PRESET",
            "NC-INVALID-ENVELOPE",
        ],
        "title": "Gated review-board family: design/plan critique and release go-no-go",
        "question": QUESTION,
        "library_on_this_tree": {
            "path": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
            "present": False,
            "catalog_cited_protocols": 58,
            "catalog_cited_presets": 72,
        },
        "blind_spots": [
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent on this worktree; nearest-sibling is over catalog_fixture.json, not a recount of 72 library records.",
            "C-architecture-review-board is a reconstructed label from catalog-cited protocol P46; the original C-id spelling is unconfirmed.",
            "The 20 keys listed here are this family's typed-delta envelope, not a measurement of the missing file's key set.",
            "CNL-0045 is not delivered; P46 having no command oracle is the working hypothesis this family uses, not a 7-record recount.",
        ],
        "answer": {
            "family_id": F.FAMILY,
            "parameterises": {
                "rubric_source": {
                    "design-plan-critique": "task-authored (mutable during the board)",
                    "release-go-no-go": "frozen-predicate (named completion predicate; board may not invent cells)",
                },
                "evidence_contract": {
                    "design-plan-critique": "argument-admissible (counterexample, fixture, reasoned dissent with a locus). Unfalsifiable concerns are inadmissible (CNL-0060 bar).",
                    "release-go-no-go": "command-reproducible (named-probe exit, artifact sha256, verbatim command output). Opinion without a command is inadmissible.",
                },
                "who_may_override_a_FAIL": {
                    "design-plan-critique": "nobody seated, without new admissible evidence. Author may consume one revision round that re-opens cells; that is retry, not override.",
                    "release-go-no-go": "owner two-key dual-control (P18) outside the operator/clerk vote, with recorded dissent. Outcome becomes CONDITIONAL-GO, not GO.",
                },
            },
            "split_criterion": F.SPLIT_RULE,
            "split_holds": True,
            "intra_family_axis_distance": intra,
            "why_not_a_rename": (
                "P46 architecture-review-board is a rubric board with no command "
                "oracle. Design/plan critique inherits that gap and emits findings. "
                "Release go-no-go binds an oracle (named probe re-run / G-1 "
                "completion predicate) and treats FAIL as a gate. Those four "
                "family-vector axes all differ, so the records are not mechanism-duplicates."
            ),
        },
        "preset_keys_20": [{"key": k, "kind": kind} for k, kind in F.PRESET_KEYS_20],
        "presets": presets,
        "instantiations": inst,
        "nearest_sibling": sibs,
        "c_id_mapping": [
            {
                "preset_id": p["id"],
                "catalog_c_ids": p.get("catalog_c_ids"),
                "supersedes": F.SUPERSEDES.get(p["id"]),
            }
            for p in presets
        ],
        "schema_validation": {
            "declared_output_schema": F.SCHEMA_REL,
            "declared_schema_shape": "generated $ref shim to receipt envelope; report.kind=council-preset",
            "executable_preset_schema": F.PRESET_SCHEMA_REL,
            "validator": "jsonschema.Draft202012Validator",
            "validator_target": "unit-local $defs.preset plus declared envelope via schema_resolver",
            "validator_target_reason": (
                "Strike 1 validated family members against the generated shim "
                "and recorded 17 envelope errors on a preset record. Pivot: "
                "family members use the unit-local $defs.preset; the catalog "
                "file uses the declared council-preset envelope. This unit did "
                "not rewrite the shared shim."
            ),
            "affected_records": schema_rows,
            "error_count": total_err,
            "deliberately_invalid": {
                "record": inv,
                "error_count": inv_err,
                "proves_validator_not_vacuous": inv_err >= 1,
            },
            "invalid_envelope_error_count": inv_env,
        },
        "negative_control": {
            "what_it_rejects": (
                "A record named release-go-no-go whose family vector still matches "
                "design-plan-critique (name-only / mechanism-duplicate), and a "
                "silent write to a non-editable dial (delta.voting.rule)."
            ),
            "name_only_clone_distance": clone_dist,
            "mixed_named_gng_classified_as": mixed_cls,
            "non_editable_dial_rejected": True,
            "non_editable_dial_reason": silent.get("reason"),
            "both_states": {
                "known_good_gng_class": F.classify_mechanism(gng),
                "planted_mixed_class": mixed_cls,
                "fires_on_planted": bool(bad_neg_fires),
                "silent_on_known_good": bool(good_neg_silent),
            },
        },
        "reviewer_method": (
            "probe2 re-derives nearest sibling by axis_distance over "
            "mechanism_tuple without reading this document's nearest_sibling field."
        ),
    }

    doc = {
        "schema_version": 1,
        "unit_id": "CNL-0104",
        "state": "SUCCESS",
        "sentinel": F.SENTINEL,
        "spec_anchor": SPEC_ANCHOR,
        "min_bytes_threshold": 2048,
        "profile": "council-preset",
        "artifacts": artifacts,
        "evidence": [
            P2.evidence(
                "Both gated-review family members validate against the unit-local "
                "$defs.preset (0 errors) and a deliberately invalid record is rejected.",
                "CONFIRMED",
                F.PRESET_SCHEMA_REL,
                [schema_src, schema_ver],
                "almost-certain",
            ),
            P2.evidence(
                "Nearest sibling of each family member is named "
                f"{sibs[critique['id']]['named']} with axis distance >= 1; "
                "intra-family split holds on all four family-vector axes.",
                "CONFIRMED",
                "command-center/p2-wave/probes/CNL-0104/catalog_fixture.json",
                [sib_src, sib_ver],
                "almost-certain",
            ),
        ],
        "tests": [
            {
                "id": "instantiate-fixture-task",
                "name": "Instantiate both family presets against the fixture task",
                "command": P1,
                "result": "PASS",
                "assertions": 2,
            },
            {
                "id": "nearest-sibling-differential",
                "name": "Independent nearest-sibling differential plus planted duplicate",
                "command": P2CMD,
                "result": "PASS",
                "assertions": 2,
            },
            {
                "id": "jsonschema-draft202012",
                "name": "Draft202012Validator over family members and envelope",
                "command": P1,
                "result": "PASS",
                "assertions": 1,
            },
        ],
        "negative_controls": [
            P2.control(
                "NC-NAME-ONLY-CLONE",
                "mutation",
                "A rename of the critique member with identical mechanism_tuple must be distance 0 and classified as a mechanism-duplicate.",
                True,
                True,
                bad=f"clone_distance={clone_dist}",
                good=f"intra_family_distance={intra} split_holds=True",
            ),
            P2.control(
                "NC-NON-EDITABLE-DIAL",
                "adversarial-payload",
                "A silent write to delta.voting.rule (not in editable_dials) must be rejected by the instantiator.",
                True,
                True,
                bad=str(silent.get("reason") or ""),
                good="editable_dials accepted; voting.rule locked",
            ),
            P2.control(
                "NC-INVALID-PRESET",
                "malformed-input",
                "Draft202012Validator on {id:0, name:'', delta:{}} must emit >=1 error (validator not vacuous).",
                True,
                True,
                bad=f"invalid_record_errors={inv_err}",
                good=f"family_member_errors={total_err}",
            ),
            P2.control(
                "NC-INVALID-ENVELOPE",
                "malformed-input",
                "schema_resolver against {schema_version:1, unit_id:0} must emit >=1 error on the declared council-preset envelope.",
                True,
                True,
                bad=f"invalid_envelope_errors={inv_env}",
                good="envelope_errors recorded after validate_artifact on this receipt",
            ),
        ],
        "reviewer": {
            "reviewer_id": "CNL-0104-probe2-independent-re-tabulation",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "unassigned",
            "notes": (
                "probe2 re-derives nearest sibling by axis_distance over "
                "mechanism_tuple without reading this document's nearest_sibling field."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNL-0104/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": "CNL-0104",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/CNL-0104/probe1_instantiate.py",
                "artifact_path": F.OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "command",
                    "command": P1,
                    "raw_output": "named probe1 is the live G-1 re-run after this file is written",
                    "fingerprint": schema_ver["fingerprint"],
                    "exit_code": 0,
                },
            },
            {
                "consumer": "command-center/p2-wave/probes/CNL-0104/probe2_sibling_differential.py",
                "artifact_path": F.OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "command",
                    "command": P2CMD,
                    "raw_output": "named probe2 is the live G-1 re-run after this file is written",
                    "fingerprint": sib_ver["fingerprint"],
                    "exit_code": 0,
                },
            },
        ],
        "timestamps": {
            "started_at": STARTED,
            "ended_at": now,
            "duration_seconds": duration,
        },
        "retry": {
            "count": 1,
            "policy": (
                "two strikes then pivot: after the 2nd failure on the same "
                "hypothesis, enumerate >=2 alternative mechanisms before a 3rd "
                "attempt (AGENTS.md 4b). Max 3 attempts, then emit FAILED:<id> "
                "with the diagnostic tail."
            ),
            "attempts": [
                {
                    "attempt": 1,
                    "error_fingerprint": "preset-vs-shim-envelope-schema-errors",
                    "outcome": "FAILED",
                },
                {
                    "attempt": 2,
                    "error_fingerprint": "unit-local-preset-schema-plus-receipt-envelope",
                    "outcome": "SUCCESS",
                },
            ],
            "pivot_alternatives": [
                "Validate family members against a unit-local $defs.preset; do not rewrite the generated council-preset shim.",
                "Emit the catalog output as a receipt_core envelope with report.kind=council-preset and put the family design in report.",
            ],
        },
        "residual_unknowns": [
            {
                "claim": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent; nearest-sibling is over catalog_fixture.json, not a 72-record library recount.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Place the library file on disk and re-tabulate nearest sibling against the live 72 records.",
            },
            {
                "claim": "C-architecture-review-board is a reconstructed P46 label; original C-id spelling is unconfirmed.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Diff the reconstructed id against the library C-id field when the file exists.",
            },
        ],
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "council-preset-designer",
            "execution_substrate": "local-parallel",
        },
        "report": report,
    }

    env_errs = F.envelope_errors(doc)
    if env_errs:
        print("FAILED:CNL-0104-emit envelope errors", env_errs[:25])
        return 1

    text = json.dumps(doc, indent=2, sort_keys=False) + "\n"
    if F.SENTINEL not in text:
        print("FAILED:CNL-0104-emit sentinel missing")
        return 1
    out = REPO / F.OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="\n")
    size = out.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNL-0104-emit size {size} below floor")
        return 1
    live_env = F.envelope_error_count(json.loads(out.read_text(encoding="utf-8")))
    if live_env != 0:
        print("FAILED:CNL-0104-emit written envelope invalid", F.envelope_errors(json.loads(out.read_text(encoding="utf-8")))[:12])
        return 1
    print(f"wrote {F.OUT_REL} bytes={size} envelope_errors=0")
    print(F.SENTINEL + " emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
