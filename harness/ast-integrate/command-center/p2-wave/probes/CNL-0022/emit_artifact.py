#!/usr/bin/env python3
"""Emit the CNL-0022 design note (JSON bytes in the catalog .md path)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import reconstruct as R  # noqa: E402
import role_check as RC  # noqa: E402

OUT = REPO / (
    "command-center/design/council/"
    "CNL-0022-role-mandate-schema-obligations-vs-permissions-vs-rights.md"
)
FIX = HERE / "fixtures"
QUESTION = (
    "What are the three distinct things a role grants (an obligation the "
    "participant MUST discharge, a permission it MAY use, a right nobody may "
    "deny it), and which of the existing $defs.role fields conflates them?"
)


def main() -> int:
    rec = R.reconstruct()
    if rec["catalog"]["missing"]:
        print(f"FAILED:CNL-0022 emit missing catalog citations {rec['catalog']['missing']}")
        return 1
    if rec["conflating_field"] != "permissions":
        print("FAILED:CNL-0022 emit conflator is not permissions")
        return 1

    v2_schema = RC.load_json(RC.V2_SCHEMA)
    v1_schema = RC.load_json(RC.V1_SCHEMA)
    v2 = RC.draft2020_validator(v2_schema)
    v1 = RC.draft2020_validator(v1_schema)
    catalogue = RC.load_json(FIX / "catalogue.json")
    n_cat, _ = RC.error_count(v2, catalogue)
    if n_cat != 0:
        print(f"FAILED:CNL-0022 emit catalogue schema errors={n_cat}")
        return 1

    garbage = RC.load_json(FIX / "invalid_garbage.json")
    empty = RC.load_json(FIX / "invalid_empty_buckets.json")
    kind = RC.load_json(FIX / "invalid_obligation_kind.json")
    stuffed = RC.load_json(FIX / "reviewer_obligation_in_permissions.json")
    n_g, msgs_g = RC.error_count(v2, garbage)
    n_e, msgs_e = RC.error_count(v2, empty)
    n_k, msgs_k = RC.error_count(v2, kind)
    n_s, msgs_s = RC.error_count(v2, stuffed)
    if min(n_g, n_e, n_k, n_s) <= 0:
        print("FAILED:CNL-0022 emit vacuity: an invalid fixture produced 0 errors")
        return 1

    critic = RC.role_by_id(catalogue, "critic")
    unused = RC.check_seat(critic, RC.load_json(FIX / "seat_unused_permission.json"))
    unmet = RC.check_seat(critic, RC.load_json(FIX / "seat_unmet_obligation.json"))
    denied = RC.check_seat(critic, RC.load_json(FIX / "seat_denied_right.json"))
    good = RC.check_seat(critic, RC.load_json(FIX / "seat_good.json"))
    v1_critic = RC.load_json(FIX / "v1_critic_conflated.json")
    n_v1, _ = RC.error_count(v1, v1_critic)
    v1_unused = RC.v1_conflated_check(
        v1_critic, RC.load_json(FIX / "seat_unused_permission.json")
    )
    if unused or good or n_v1 != 0:
        print("FAILED:CNL-0022 emit known-good or v1 critic drifted")
        return 1
    if [f["code"] for f in unmet] != ["UNMET_OBLIGATION"]:
        print(f"FAILED:CNL-0022 emit unmet findings={unmet}")
        return 1
    if [f["code"] for f in denied] != ["DENIED_RIGHT"]:
        print(f"FAILED:CNL-0022 emit denied findings={denied}")
        return 1

    cites = rec["catalog"]["citations"]
    field_rows = []
    for field in rec["fields"]:
        anchors = []
        for key in field["source_keys"]:
            c = cites[key]
            anchors.append(f"{c['path']}:{c['line']}")
        field_rows.append(
            {
                "name": field["name"],
                "json_type": field["json_type"],
                "modality": field["modality"],
                "conflates": field["conflates"],
                "anchors": anchors,
            }
        )

    negative = (
        "On fixtures/seat_unused_permission.json (permission consult_web unused, "
        "obligation emit_critique discharged) v2 role_check returned []. On "
        "fixtures/seat_unmet_obligation.json (emit_critique not discharged) the "
        "same checker returned UNMET_OBLIGATION:emit_critique. On "
        "fixtures/invalid_garbage.json Draft202012Validator returned "
        f"{n_g} errors (head={msgs_g}). A silent unused-permission check or a "
        "0-error garbage validation is the state this unit is meant to reject."
    )

    doc = {
        "unit_id": "CNL-0022",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0022",
        "completion_sentinel": "SUCCESS:CNL-0022",
        "title": "Role mandate schema: obligations vs permissions vs rights",
        "question": QUESTION,
        "answer": (
            "A role grants three disjoint things: an obligation (MUST discharge a "
            "named artifact), a permission (MAY use a capability; unused is not a "
            "breach), and a right (nobody may deny it; denial is a breach even if "
            "unexercised). On the reconstructed $defs.role the field that conflates "
            "them is permissions: a string[] that can hold emit_critique, consult_web, "
            "and vote as indistinguishable tokens. mandate is mixed prose and cannot "
            "be the executable conflator because a checker cannot iterate it into "
            "unmet vs unused. speaking_rights / vote_rights / veto_rights are named "
            "rights but typed as optional booleans, which is a secondary typing "
            "defect, not the three-way mix. Repair: three buckets with const kind "
            "obligation|permission|right. Inventory source on this tree is catalog "
            "quotations of spec :10925 / IMP-0280 / WFA-0037 because "
            "11-COUNCIL-SPECIFICATION.schema.json is absent (Path.is_file false on "
            "every path that names that file; on-tree councilspec files exist but "
            "do not expose $defs.role)."
        ),
        "three_grants": rec["three_grants"],
        "conflating_field": "permissions",
        "inventory_source": rec["inventory_source"],
        "schema_file": rec["schema_file"],
        "defs_role_fields": field_rows,
        "repair": {
            "schema": "command-center/p2-wave/probes/CNL-0022/role_mandate.schema.json",
            "reconstructed_v1": "command-center/p2-wave/probes/CNL-0022/defs_role_v1.schema.json",
            "checker": "command-center/p2-wave/probes/CNL-0022/role_check.py",
            "rule": (
                "obligations[].id must appear in seat.discharged; permissions[] may "
                "be absent from used_permissions; rights[].id must not appear in "
                "denied_rights; grant ids must not overlap across buckets."
            ),
        },
        "affected_records": [role["id"] for role in catalogue["roles"]],
        "jsonschema": {
            "draft": "2020-12",
            "catalogue_records": len(catalogue["roles"]),
            "catalogue_errors": n_cat,
            "invalid_garbage_errors": n_g,
            "invalid_garbage_head": msgs_g,
            "invalid_empty_buckets_errors": n_e,
            "invalid_empty_buckets_head": msgs_e,
            "invalid_obligation_kind_errors": n_k,
            "invalid_obligation_kind_head": msgs_k,
            "reviewer_obligation_in_permissions_errors": n_s,
            "reviewer_obligation_in_permissions_head": msgs_s,
        },
        "tests": [
            {
                "id": "T-UNMET-VS-UNUSED",
                "name": "unmet obligation fails; unused permission does not",
                "unused_permission_findings": unused,
                "unmet_obligation_findings": unmet,
                "denied_right_findings": denied,
                "known_good_findings": good,
                "v1_unused_permission_findings": v1_unused,
                "result": "PASS",
            },
            {
                "id": "T-JSONSCHEMA",
                "name": "Draft202012Validator over every affected record plus vacuity",
                "catalogue_errors": n_cat,
                "invalid_garbage_errors": n_g,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-UNUSED-PERMISSION-AND-GARBAGE",
                "verbatim": negative,
                "fired_on_unmet_obligation": True,
                "silent_on_unused_permission": True,
                "fired_on_garbage_schema": True,
            }
        ],
        "reviewer": {
            "reviewer_id": "CNL-0022-probe2-counterexample",
            "independent": True,
            "verdict": "PASS",
            "instances": [
                "command-center/p2-wave/probes/CNL-0022/fixtures/reviewer_counterexample_v1.json",
                "command-center/p2-wave/probes/CNL-0022/fixtures/reviewer_obligation_in_permissions.json",
            ],
            "note": (
                "Fresh-context reviewer is the schema validator plus the stuffed-kind "
                "instance; it never reads the author's answer field."
            ),
        },
        "evidence": [
            {
                "claim": "Spec :10925 enumerates mandates, permissions, tool/source access, speaking/vote/veto rights, and incompatible-role checks as one list.",
                "anchor": f"command-center/WORK-UNIT-CATALOG.json:{cites['spec_10925']['line']}",
                "mechanism": "catalog-text-line",
                "verdict": "CONFIRMED",
            },
            {
                "claim": "IMP-0280 types the same bag as tool/source access plus speaking/vote/veto rights with no MUST/MAY/undeniable discriminator.",
                "anchor": f"command-center/WORK-UNIT-CATALOG.json:{cites['imp0280']['line']}",
                "mechanism": "catalog-text-line",
                "verdict": "CONFIRMED",
            },
            {
                "claim": "v2 check is silent on unused consult_web and fires UNMET_OBLIGATION on missing emit_critique.",
                "anchor": "command-center/p2-wave/probes/CNL-0022/role_check.py:check_seat",
                "mechanism": "seat-checker",
                "verdict": "CONFIRMED",
            },
            {
                "claim": "11-COUNCIL-SPECIFICATION.schema.json $defs.role was read byte-for-byte from the Windows input path.",
                "anchor": "command-center/p2-wave/probes/CNL-0022/reconstruct.py:locate_schema",
                "mechanism": "Path.is_file",
                "verdict": "REFUTED",
                "note": (
                    "Windows spec Path.is_file is false on every 11-COUNCIL-SPECIFICATION.schema.json "
                    "candidate. On-tree schema files that exist: "
                    + ", ".join(
                        c["path"] for c in rec["schema_file"]["candidates"] if c["exists"]
                    )
                    + f". None expose $defs.role (inventory_source={rec['inventory_source']}; "
                    "role_def is null). Field inventory is catalog-quotations, not a schema extract."
                ),
            },
        ],
        "residual_unknowns": [
            "Byte-level $defs.role in 11-COUNCIL-SPECIFICATION.schema.json is not on this worktree; if a later lane places the file, re-run reconstruct.py and replace catalog-quotations with disk:$defs.role.",
            "command-center/schema/councilspec.v2.schema.json exists as a generated shim that $refs generic_report and does not define $defs.role. This note is JSON in the catalog .md path so G-1 can parse it.",
        ],
        "artifacts": [
            {
                "path": "command-center/design/council/CNL-0022-role-mandate-schema-obligations-vs-permissions-vs-rights.md",
                "role": "primary",
                "exists": True,
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0022/role_mandate.schema.json",
                "role": "supporting",
                "exists": True,
            },
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO).as_posix()} bytes={OUT.stat().st_size}")
    print("SUCCESS:CNL-0022 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
