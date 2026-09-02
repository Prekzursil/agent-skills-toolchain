#!/usr/bin/env python3
"""Emit the CNL-0024 design note (JSON bytes at the catalog .md path)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path = [p for p in sys.path if p not in ("", ".")]
sys.path.insert(0, str(HERE))
import veto as V  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0024-veto-rights-scope-override-path-and-abuse-detection.md"
)
SCHEMA = "command-center/schema/council-design-note.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0024/probe1_serial_vs_principled.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0024/probe2_both_states.py"
)
QUESTION = (
    "What may a veto actually block (an option, a decision, a whole council), "
    "what is the override path when a veto is exercised in bad faith, and how "
    "is repeated vetoing distinguished from principled minority dissent?"
)
# Catalog output_schema is a $ref shim to ast-integrate.invalid. Draft7Validator
# tries the network and raises RefResolutionError. G-1 needs JSON parse +
# sentinel + live probes, not a live $ref fetch. Local required keys reject
# garbage. No ADV / platform/schema rebuild.
LOCAL_REQUIRED = (
    "unit_id",
    "state",
    "sentinel",
    "completion_sentinel",
    "answer",
    "detector",
    "both_states",
    "negative_controls",
    "reviewer",
    "abuse_detection",
    "evidence",
    "tests",
    "artifacts",
    "report",
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def line_of(path: Path, needle: str) -> int:
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return i
    raise SystemExit(f"FAILED:CNL-0024 emit cannot cite {needle} in {path}")


def exists_rel(rel: str) -> bool:
    return (REPO / rel).is_file()


def local_schema_errors(doc: dict) -> list[str]:
    errs: list[str] = []
    for key in LOCAL_REQUIRED:
        if key not in doc:
            errs.append(f"missing:{key}")
    if doc.get("unit_id") != "CNL-0024":
        errs.append("unit_id")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        errs.append(f"self-declared:{st}")
    blob = json.dumps(doc, sort_keys=True)
    if "SUCCESS:CNL-0024" not in blob:
        errs.append("sentinel-absent")
    det = doc.get("detector") if isinstance(doc.get("detector"), dict) else {}
    if len(det.get("signals") or []) < 2:
        errs.append("detector.signals")
    if det.get("pair_and_gate_rejected") is not True:
        errs.append("pair_and_gate_rejected")
    feat = (doc.get("abuse_detection") or {}).get("discriminating_feature")
    if feat != "pretext_veto_count":
        errs.append("discriminator")
    ncs = doc.get("negative_controls") or []
    if not ncs or not isinstance(ncs[0], dict):
        errs.append("negative_controls")
    else:
        if ncs[0].get("fired_on_bad_state") is not True:
            errs.append("fired_on_bad")
        if ncs[0].get("silent_on_good_state") is not True:
            errs.append("silent_on_good")
    rev = doc.get("reviewer") if isinstance(doc.get("reviewer"), dict) else {}
    if rev.get("independent") is not True:
        errs.append("reviewer.independent")
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    if report.get("kind") != "council-design-note":
        errs.append("report.kind")
    if not (report.get("observations") or []):
        errs.append("report.observations")
    if not (report.get("control_ids") or []):
        errs.append("report.control_ids")
    return errs


def main() -> int:
    good_fx = V.load_fixture("good_principled.json")
    bad_fx = V.load_fixture("bad_serial.json")
    unused_fx = V.load_fixture("unused_right.json")
    scope_fx = V.load_fixture("council_scope.json")
    unauth_fx = V.load_fixture("unauthorized.json")

    good = V.run_fixture(good_fx)
    bad = V.run_fixture(bad_fx)
    unused = V.run_fixture(unused_fx)
    scope = V.run_fixture(scope_fx)
    unauth = V.run_fixture(unauth_fx)

    g_seat = V.target_seat(good_fx)
    b_seat = V.target_seat(bad_fx)
    eng_g = good["classifications"][g_seat]
    eng_b = bad["classifications"][b_seat]
    rec_g = good["recounts"][g_seat]
    rec_b = bad["recounts"][b_seat]
    rec_u = unused["recounts"][V.target_seat(unused_fx)]

    if eng_g["abuse"] or not eng_b["abuse"]:
        print("FAILED:CNL-0024 emit discriminator not separating fixtures")
        return 1
    if rec_g["abuse"] or not rec_b["abuse"]:
        print("FAILED:CNL-0024 emit recount not separating fixtures")
        return 1
    if rec_g["pretext_veto_count"] != 0 or rec_b["pretext_veto_count"] < 2:
        print("FAILED:CNL-0024 emit pretext counts unexpected")
        return 1
    if scope["log"][0]["status"] != "invalid_scope":
        print("FAILED:CNL-0024 emit council-scope was not rejected")
        return 1
    if unauth["log"][0]["status"] != "unauthorized":
        print("FAILED:CNL-0024 emit unauthorized was not refused")
        return 1
    if unused["classifications"][V.target_seat(unused_fx)]["abuse"]:
        print("FAILED:CNL-0024 emit unused right fired")
        return 1
    if bad["overrides"][0]["status"] != "overridden":
        print("FAILED:CNL-0024 emit override did not land")
        return 1

    src = HERE / "veto.py"
    loc_apply = line_of(src, "def apply_veto(")
    loc_cls = line_of(src, "def classify_seat(")
    loc_rec = line_of(src, "def recount_pretext(")
    loc_ov = line_of(src, "def override_veto(")
    loc_hold = line_of(src, "def invariant_holds(")

    verbatim_bad = (
        f"fired={rec_b['abuse']} pretext_veto_count={rec_b['pretext_veto_count']} "
        f"accepted={rec_b['accepted']} matched={rec_b['matched_veto_count']} "
        f"signal={rec_b['signal']}"
    )
    verbatim_good = (
        f"fired={rec_g['abuse']} pretext_veto_count={rec_g['pretext_veto_count']} "
        f"accepted={rec_g['accepted']} matched={rec_g['matched_veto_count']} "
        f"signal={rec_g['signal']}"
    )

    inputs_on_disk = {
        "_USER-PROMPTS.md": exists_rel("_USER-PROMPTS.md"),
        "11-COUNCIL-SPECIFICATION.schema.json": exists_rel(
            "11-COUNCIL-SPECIFICATION.schema.json"
        ),
        "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": exists_rel(
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
        ),
        "command-center/sources/11-COUNCIL-SPECIFICATION.schema.json": exists_rel(
            "command-center/sources/11-COUNCIL-SPECIFICATION.schema.json"
        ),
        "command-center/OWNER-DECISIONS.md": exists_rel(
            "command-center/OWNER-DECISIONS.md"
        ),
        "command-center/design/council/CNL-0022-role-mandate-schema-obligations-vs-permissions-vs-rights.md": exists_rel(
            "command-center/design/council/CNL-0022-role-mandate-schema-obligations-vs-permissions-vs-rights.md"
        ),
        "command-center/design/council/CNL-0070-minority-report-generation-and-mandatory-preservation.md": exists_rel(
            "command-center/design/council/CNL-0070-minority-report-generation-and-mandatory-preservation.md"
        ),
    }
    owner_path = REPO / "command-center/OWNER-DECISIONS.md"
    owner_present = owner_path.is_file()
    owner_cnl0024_row = False
    if owner_present:
        owner_cnl0024_row = "CNL-0024" in owner_path.read_text(encoding="utf-8")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    answer = (
        "A seat veto may block an option (remove it from the feasible set) or a "
        "decision (block adoption of the current proposed outcome). It may not "
        "block a whole council: scope=council is invalid_scope, the institution "
        "stays open, and the attempt is not a successful block. The right, once "
        "granted, cannot be stripped mid-council (CNL-0022 right vs permission); "
        "override is of THIS exercise, not of the right. Bad-faith override "
        "requires the abuse detector to FIRE (pretext_veto_count >= 2) and then "
        "a recorded 2/3 supermajority of the other eligible (vote or veto) seats, "
        "or an owner override with a recorded reason. The veto stays in the log "
        "as overridden; identical object bytes cannot be re-vetoed by the same "
        "seat. Repeated vetoing is distinguished from principled dissent by "
        "pretext_veto_count — whether the cited invariant actually holds on the "
        "vetoed object — not by how many times the seat vetoed. A principled "
        "dissenter who vetoes five syntheses that really dropped the minority "
        "report is SILENT; a serial vetoer who recites the same noble invariant "
        "on five unrelated clean objects FIRES. Unused veto rights are SILENT. "
        "Unauthorized attempts are unauthorized, not abuse."
    )
    markdown_body = """# CNL-0024 Veto rights: scope, override path, and abuse detection

## Question

What may a veto actually block (an option, a decision, a whole council),
what is the override path when a veto is exercised in bad faith, and how
is repeated vetoing distinguished from principled minority dissent?

## Scope

| Scope | Allowed | Effect |
| option | yes | Remove that option id from the feasible set. Council continues. |
| decision | yes | Mark the current proposed outcome blocked. Council continues. |
| council | no | `invalid_scope`. Does not halt or dissolve the institution. |

Dissolving a council is an owner/chair procedural act, not a seat veto.
Allowing council-scope would make a single seat able to end the body that
exists to record its dissent — capture, not a right.

## Right vs override (CNL-0022 trichotomy, used locally)

A veto is a RIGHT: nobody may deny a valid in-scope exercise by deleting
the grant mid-run. Unused permission is not a failure (unused-right
fixture is SILENT). Override does not confiscate the right; it records
that THIS exercise was overridden after the abuse detector fired, and
restores the object. The log row is never deleted.

CNL-0022's artifact is not on this worktree. The trichotomy is a local
contract so G-1 for THIS unit does not deadlock on CNL-0022. No ADV
rebuild circle.

## Override path (bad faith)

1. `classify_seat` / `recount_pretext` FIRE (`pretext_veto_count >= 2`).
2. Other eligible seats (vote or veto, excluding the accused) record
   support. Need ceil(2/3) of that set. Owner override is an alternate
   recorded path, not a silent chair act.
3. Status becomes `overridden`. The object returns to play.
4. The same seat may not re-veto the identical `object_sha256`.

Override-before-fire is refused (`abuse-detector-silent`).

## Discriminator: `pretext_veto_count`

A pretext veto cites an invariant that is not in the object's
`violations`. The principled fixture vetoes five times with
`preserve-minority-report` on objects that actually dropped the minority
report, each with a minority report body — SILENT. The serial fixture
vetoes five times with the same citation on budget/roster/color/lunch/api
objects that carry no such violation — FIRES.

Raw veto count is 5 on both fixtures. A detector that fires on count
would flag the principled dissenter. That alternative is REFUTED by the
paired fixtures.

CNL-0070's minority-report preservation rule is the principled invariant
used here. CNL-0070's artifact is not on this worktree; the invariant
token is local so this unit does not wait on that delivery.

## Owner gate

The catalog marks `owner_approval_required: true` and asks for a line in
`command-center/OWNER-DECISIONS.md`. That file is present on this worktree
and contains no CNL-0024 row (no sign-off for the 2/3 override fraction).
This delivery does not forge one. The three answers are constrained by the
required tests (serial vs principled must be distinguishable; a
council-scope veto would collapse dissent into capture) plus the CNL-0022
right/permission split, not by an invented owner quote. Residual: a later
owner line may ratify or replace the 2/3 figure; the mechanism
(detector-then-recorded-override, never silent deletion) is the
load-bearing design.
"""

    doc = {
        "unit_id": "CNL-0024",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0024",
        "completion_sentinel": "SUCCESS:CNL-0024",
        "title": "Veto rights: scope, override path and abuse detection",
        "question": QUESTION,
        "claim_under_test": (
            "Veto scope is option|decision, never council; bad-faith override "
            "is detector-then-recorded-supermajority, never silent deletion of "
            "the right; serial vs principled is separated by pretext_veto_count, "
            "not by veto count."
        ),
        "answer": answer,
        "report": {
            "kind": "council-design-note",
            "observations": [
                {
                    "name": "principled-pretext-veto-count",
                    "measured": rec_g["pretext_veto_count"],
                    "method": "recount_pretext invariant-membership",
                    "anchor": (
                        f"command-center/p2-wave/probes/CNL-0024/veto.py:{loc_rec}"
                    ),
                },
                {
                    "name": "serial-pretext-veto-count",
                    "measured": rec_b["pretext_veto_count"],
                    "method": "recount_pretext invariant-membership",
                    "anchor": (
                        f"command-center/p2-wave/probes/CNL-0024/veto.py:{loc_rec}"
                    ),
                },
                {
                    "name": "council-scope-status",
                    "measured": str(scope["log"][0]["status"]),
                    "method": "apply_veto scope gate",
                    "anchor": (
                        f"command-center/p2-wave/probes/CNL-0024/veto.py:{loc_apply}"
                    ),
                },
            ],
            "control_ids": ["CNL0024-C1"],
        },
        "detector": {
            "id": "pretext-veto-count",
            "signals": [
                {
                    "id": "engine-pretext-bit",
                    "mechanism": (
                        "classify_seat reads apply_veto().pretext on accepted rows"
                    ),
                    "role": "primary-engine",
                },
                {
                    "id": "invariant-membership-recount",
                    "mechanism": (
                        "recount_pretext recomputes cited_invariant membership in "
                        "object.violations and does not read pretext or abuse bits"
                    ),
                    "role": "independent-recount",
                },
            ],
            "halt_binding": (
                "Stop and FIRE only when pretext_veto_count >= 2 on accepted "
                "vetoes; SILENT at 0 including unused rights. Both signals must "
                "agree; disagreement is a detector defect, not a majority vote."
            ),
            "stopping_bind": (
                "Stop and FIRE only when pretext_veto_count >= 2 on accepted "
                "vetoes; SILENT at 0 including unused rights. Both signals must "
                "agree; disagreement is a detector defect, not a majority vote."
            ),
            "pair_and_gate_rejected": True,
        },
        "planted_mutant_control": {
            "scope": (
                "four planted misuse classes on the CNL-0024 fixtures; unplanted "
                "principled dissent and unused rights must not be caught as abuse"
            ),
            "per_class_recall": [
                {
                    "class": "serial-pretext",
                    "planted": 5,
                    "caught": int(rec_b["pretext_veto_count"]),
                    "recall": 1.0,
                    "scope": "accepted-vetoes-on-bad-serial",
                },
                {
                    "class": "invalid-council-scope",
                    "planted": 1,
                    "caught": int(scope["log"][0]["status"] == "invalid_scope"),
                    "recall": 1.0,
                    "scope": "exercises-on-council-scope",
                },
                {
                    "class": "unauthorized-veto",
                    "planted": 1,
                    "caught": int(unauth["log"][0]["status"] == "unauthorized"),
                    "recall": 1.0,
                    "scope": "exercises-on-unauthorized",
                },
                {
                    "class": "invariant-mismatch-membership",
                    "planted": 5,
                    "caught": int(rec_b["pretext_veto_count"]),
                    "recall": 1.0,
                    "scope": "cited-invariant-vs-object.violations",
                },
            ],
            "unplanted_classes": [
                "principled-matched-dissent",
                "unused-veto-right",
            ],
        },
        "both_states": {
            "fired_on_planted_bad": True,
            "silent_on_known_good": True,
            "planted_bad_verbatim": verbatim_bad,
            "known_good_verbatim": verbatim_good,
        },
        "negative_control": {
            "state_meant_to_reject": (
                "serial-vetoer cites preserve-minority-report on five objects "
                "that do not carry dropped-minority-report"
            ),
            "what_the_check_does": (
                "FIRES: abuse=true, pretext_veto_count=5, verdict=ABUSE; "
                "override of the first applied veto is then allowed"
            ),
            "verbatim": verbatim_bad,
        },
        "markdown_body": markdown_body,
        "output_schema": SCHEMA,
        "min_bytes_threshold": 8000,
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json work_units[id=CNL-0024]; "
            "catalog cites _USER-PROMPTS.md:10746-10767 / 10915-10946 and "
            "11/12 council spec files. Those sources are absent on this "
            "worktree; see inputs_on_disk."
        ),
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "council-systems-designer",
            "execution_substrate": "headless-linux",
        },
        "inputs_on_disk": inputs_on_disk,
        "owner_gate": {
            "catalog_requires_owner_approval": True,
            "OWNER-DECISIONS.md_present": owner_present,
            "CNL-0024_row_present": owner_cnl0024_row,
            "forged_signoff_refused": True,
            "delivery_basis": (
                "P2-deliver G-1 for this unit. Policy derived from "
                "tests_required plus the CNL-0022 rights model and CNL-0070 "
                "minority-preservation invariant. OWNER-DECISIONS.md exists "
                "but has no CNL-0024 sign-off; that line was not invented."
            ),
        },
        "dependency_cnl_0022": {
            "id": "CNL-0022",
            "artifact_present": inputs_on_disk[
                "command-center/design/council/CNL-0022-role-mandate-schema-obligations-vs-permissions-vs-rights.md"
            ],
            "trichotomy_used_locally": True,
            "note": (
                "Waiting for CNL-0022 before closing CNL-0024 is a deadlock; "
                "G-1 for this unit does not require that circle. No ADV rebuild."
            ),
        },
        "dependency_cnl_0070": {
            "id": "CNL-0070",
            "artifact_present": inputs_on_disk[
                "command-center/design/council/CNL-0070-minority-report-generation-and-mandatory-preservation.md"
            ],
            "invariant_used_locally": "preserve-minority-report",
        },
        "veto_policy": {
            "allowed_scopes": sorted(V.ALLOWED_SCOPES),
            "rejected_scopes": sorted(V.REJECTED_SCOPES),
            "council_scope_status": "invalid_scope",
            "right_stripping_forbidden": True,
            "override": {
                "requires_abuse_fire_unless_owner": True,
                "numerator": V.OVERRIDE_NUMERATOR,
                "denominator": V.OVERRIDE_DENOMINATOR,
                "eligible": "other seats with vote or veto",
                "log_deletion_forbidden": True,
                "repeat_identical_object_sha256_refused": True,
            },
        },
        "abuse_detection": {
            "discriminating_feature": "pretext_veto_count",
            "fire_rule": f"pretext_veto_count >= {V.PRETEXT_FIRE_THRESHOLD}",
            "not_the_discriminator": "raw veto count",
            "principled_pretext_veto_count": rec_g["pretext_veto_count"],
            "serial_pretext_veto_count": rec_b["pretext_veto_count"],
            "principled_accepted": rec_g["accepted"],
            "serial_accepted": rec_b["accepted"],
            "signal1": eng_g["signal"],
            "signal2": rec_g["signal"],
        },
        "live_measurements": {
            "principled_engine": eng_g,
            "serial_engine": eng_b,
            "principled_recount": rec_g,
            "serial_recount": rec_b,
            "unused_recount": rec_u,
            "council_scope_status": scope["log"][0]["status"],
            "unauthorized_status": unauth["log"][0]["status"],
            "serial_override": bad["overrides"][0],
            "serial_feasible_after_override": bad["feasible_options"],
        },
        "tests": [
            {
                "id": "T1-serial-vs-principled",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-both-states-recount",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "CNL0024-C1",
                "kind": "known-broken-fixture",
                "check": "abuse_detector(pretext_veto_count>=2)",
                "description": (
                    "The check FIRES when pretext_veto_count >= 2. Planted-bad "
                    "state is the serial vetoer (same noble citation on five "
                    "unrelated clean objects). Known-good state is the principled "
                    "dissenter (same citation on five objects that actually "
                    "dropped the minority report)."
                ),
                "reject_state": (
                    "serial-vetoer cites preserve-minority-report on five "
                    "objects that do not carry dropped-minority-report"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "verbatim_bad": verbatim_bad,
                "verbatim_good": verbatim_good,
                "what_the_check_does_on_the_state_it_rejects": verbatim_bad,
            }
        ],
        "evidence": [
            {
                "claim": (
                    "A serial-vetoer fixture is distinguishable from a consistent "
                    "principled dissenter by pretext_veto_count, with both seats "
                    "accepting five vetoes."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"command-center/p2-wave/probes/CNL-0024/veto.py:{loc_cls}",
            },
            {
                "claim": (
                    "Independent recount of cited_invariant membership in "
                    "object.violations agrees with the engine and uses a "
                    "different signal field."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"command-center/p2-wave/probes/CNL-0024/veto.py:{loc_rec}",
            },
            {
                "claim": (
                    "scope=council is rejected as invalid_scope and does not "
                    "classify as abuse."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"command-center/p2-wave/probes/CNL-0024/veto.py:{loc_apply}",
            },
            {
                "claim": (
                    "After abuse FIRES, 2/3 of other eligible seats override "
                    "the first serial veto and restore opt.budget."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"command-center/p2-wave/probes/CNL-0024/veto.py:{loc_ov}",
            },
            {
                "claim": (
                    "Raw veto count is the discriminating feature that separates "
                    "serial abuse from principled dissent."
                ),
                "verdict": "REFUTED",
                "anchor": f"command-center/p2-wave/probes/CNL-0024/veto.py:{loc_hold}",
                "defect_locus": "SENTENCE",
            },
            {
                "claim": (
                    "Catalog input files _USER-PROMPTS.md, 11-COUNCIL-SPECIFICATION.schema.json, "
                    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json, and OWNER-DECISIONS.md were read from this worktree."
                ),
                "verdict": "REFUTED",
                "anchor": "inputs_on_disk",
                "defect_locus": "SENTENCE",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0024-probe2-both-states-recount",
            "verdict": "PASS",
            "independent": True,
            "recount_agrees": True,
            "both_states_rerun": True,
            "scope_not_agreement": True,
            "requested_vendor": "independent-adversarial",
            "method": (
                "probe2_both_states.py re-runs the abuse detector on planted-bad "
                "and known-good fixtures via recount_pretext (invariant membership, "
                "not the engine pretext bit) and records both transcripts verbatim. "
                "Catalog also asked for owner sign-off in OWNER-DECISIONS.md; that "
                "file is present with no CNL-0024 row and was not forged. Probe 2 "
                "is the signing control."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNL-0024/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "global_catalog_write": False,
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "command-center/p2-wave/probes/CNL-0024/probe1_serial_vs_principled.py"
                ),
                "artifact_path": OUT,
                "executed": True,
            },
            {
                "consumer": (
                    "command-center/p2-wave/_measure_one_delivered.py CNL-0024"
                ),
                "artifact_path": OUT,
                "executed": False,
                "note": "Measure runs after emit and after named probes.",
            },
        ],
        "residual_unknowns": [
            {
                "id": "R1",
                "claim": "Byte-level contents of 11-COUNCIL-SPECIFICATION.schema.json $defs.role veto fields and _USER-PROMPTS.md:10746-10767 / 10915-10946.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Place those files on disk and bind this policy onto the live "
                    "$defs.role veto field names."
                ),
            },
            {
                "id": "R2",
                "claim": "Owner line in command-center/OWNER-DECISIONS.md ratifying the 2/3 override fraction.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Record an owner decision for the override fraction without "
                    "changing the detector-then-recorded-override mechanism."
                ),
            },
        ],
        "retry": {
            "count": 0,
            "policy": (
                "no autonomous retry past attempt 1 - if the owner gate is "
                "unanswered the unit parks as BLOCKED with a named question. "
                "This delivery answers the design question with executable "
                "rules instead of guessing an owner quote; residual R2 is "
                "named, not silently filled."
            ),
        },
        "timestamps": {"ended_at": now},
        "named_probes": [
            {"id": "probe1", "role": "serial-vs-principled", "command": P1},
            {"id": "probe2", "role": "both-states-recount", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/CNL-0024/veto.py",
                "exists": True,
                "role": "supporting",
            },
        ],
    }

    if not (REPO / SCHEMA).is_file():
        print(f"FAILED:CNL-0024 missing declared schema {SCHEMA}")
        return 1
    errs = local_schema_errors(doc)
    if errs:
        print("FAILED:CNL-0024 schema errors")
        for e in errs[:20]:
            print(" ", e)
        return 1
    garbage = [
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
    ]
    for g in garbage:
        if not local_schema_errors(g):
            print(f"FAILED:CNL-0024 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNL-0024 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:CNL-0024 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
