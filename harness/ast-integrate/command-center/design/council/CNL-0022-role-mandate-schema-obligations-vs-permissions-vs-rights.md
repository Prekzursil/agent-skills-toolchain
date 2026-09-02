{
 "affected_records": [
  "proposer",
  "critic",
  "synthesiser",
  "chair",
  "judge",
  "juror"
 ],
 "answer": "A role grants three disjoint things: an obligation (MUST discharge a named artifact), a permission (MAY use a capability; unused is not a breach), and a right (nobody may deny it; denial is a breach even if unexercised). On the reconstructed $defs.role the field that conflates them is permissions: a string[] that can hold emit_critique, consult_web, and vote as indistinguishable tokens. mandate is mixed prose and cannot be the executable conflator because a checker cannot iterate it into unmet vs unused. speaking_rights / vote_rights / veto_rights are named rights but typed as optional booleans, which is a secondary typing defect, not the three-way mix. Repair: three buckets with const kind obligation|permission|right. Inventory source on this tree is catalog quotations of spec :10925 / IMP-0280 / WFA-0037 because 11-COUNCIL-SPECIFICATION.schema.json is absent (Path.is_file false on every path that names that file; on-tree councilspec files exist but do not expose $defs.role).",
 "artifacts": [
  {
   "exists": true,
   "path": "command-center/design/council/CNL-0022-role-mandate-schema-obligations-vs-permissions-vs-rights.md",
   "role": "primary"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0022/role_mandate.schema.json",
   "role": "supporting"
  }
 ],
 "completion_sentinel": "SUCCESS:CNL-0022",
 "conflating_field": "permissions",
 "defs_role_fields": [
  {
   "anchors": [
    "command-center/WORK-UNIT-CATALOG.json:35397"
   ],
   "conflates": false,
   "json_type": "string",
   "modality": "identity",
   "name": "id"
  },
  {
   "anchors": [
    "command-center/WORK-UNIT-CATALOG.json:94299"
   ],
   "conflates": false,
   "json_type": "string",
   "modality": "identity",
   "name": "name"
  },
  {
   "anchors": [
    "command-center/WORK-UNIT-CATALOG.json:89039",
    "command-center/WORK-UNIT-CATALOG.json:94299",
    "command-center/WORK-UNIT-CATALOG.json:53958"
   ],
   "conflates": false,
   "json_type": "string",
   "modality": "prose-mixed",
   "name": "mandate"
  },
  {
   "anchors": [
    "command-center/WORK-UNIT-CATALOG.json:89039"
   ],
   "conflates": true,
   "json_type": "array<string>",
   "modality": "conflated-grant-bag",
   "name": "permissions"
  },
  {
   "anchors": [
    "command-center/WORK-UNIT-CATALOG.json:53958",
    "command-center/WORK-UNIT-CATALOG.json:89039"
   ],
   "conflates": false,
   "json_type": "array<string>",
   "modality": "permission",
   "name": "tool_access"
  },
  {
   "anchors": [
    "command-center/WORK-UNIT-CATALOG.json:53958",
    "command-center/WORK-UNIT-CATALOG.json:89039"
   ],
   "conflates": false,
   "json_type": "array<string>",
   "modality": "permission",
   "name": "source_access"
  },
  {
   "anchors": [
    "command-center/WORK-UNIT-CATALOG.json:53958",
    "command-center/WORK-UNIT-CATALOG.json:89039",
    "command-center/WORK-UNIT-CATALOG.json:94299"
   ],
   "conflates": false,
   "json_type": "boolean",
   "modality": "right-typed-as-optional-flag",
   "name": "speaking_rights"
  },
  {
   "anchors": [
    "command-center/WORK-UNIT-CATALOG.json:53958",
    "command-center/WORK-UNIT-CATALOG.json:89039",
    "command-center/WORK-UNIT-CATALOG.json:94299"
   ],
   "conflates": false,
   "json_type": "boolean",
   "modality": "right-typed-as-optional-flag",
   "name": "vote_rights"
  },
  {
   "anchors": [
    "command-center/WORK-UNIT-CATALOG.json:53958",
    "command-center/WORK-UNIT-CATALOG.json:89039"
   ],
   "conflates": false,
   "json_type": "boolean",
   "modality": "right-typed-as-optional-flag",
   "name": "veto_rights"
  },
  {
   "anchors": [
    "command-center/WORK-UNIT-CATALOG.json:89039"
   ],
   "conflates": false,
   "json_type": "array<string>",
   "modality": "constraint",
   "name": "incompatible_roles"
  }
 ],
 "evidence": [
  {
   "anchor": "command-center/WORK-UNIT-CATALOG.json:89039",
   "claim": "Spec :10925 enumerates mandates, permissions, tool/source access, speaking/vote/veto rights, and incompatible-role checks as one list.",
   "mechanism": "catalog-text-line",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/WORK-UNIT-CATALOG.json:53958",
   "claim": "IMP-0280 types the same bag as tool/source access plus speaking/vote/veto rights with no MUST/MAY/undeniable discriminator.",
   "mechanism": "catalog-text-line",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0022/role_check.py:check_seat",
   "claim": "v2 check is silent on unused consult_web and fires UNMET_OBLIGATION on missing emit_critique.",
   "mechanism": "seat-checker",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0022/reconstruct.py:locate_schema",
   "claim": "11-COUNCIL-SPECIFICATION.schema.json $defs.role was read byte-for-byte from the Windows input path.",
   "mechanism": "Path.is_file",
   "note": "Windows spec Path.is_file is false on every 11-COUNCIL-SPECIFICATION.schema.json candidate. On-tree schema files that exist: /opt/p2/ast-integrate/platform/schema/councilspec.schema.json, /opt/p2/ast-integrate/command-center/schema/councilspec.v2.schema.json. None expose $defs.role (inventory_source=catalog-quotations; role_def is null). Field inventory is catalog-quotations, not a schema extract.",
   "verdict": "REFUTED"
  }
 ],
 "inventory_source": "catalog-quotations",
 "jsonschema": {
  "catalogue_errors": 0,
  "catalogue_records": 6,
  "draft": "2020-12",
  "invalid_empty_buckets_errors": 3,
  "invalid_empty_buckets_head": [
   "roles/0/name: 'x' is too short",
   "roles/0/obligations: [] is too short",
   "roles/0/rights: [] is too short"
  ],
  "invalid_garbage_errors": 2,
  "invalid_garbage_head": [
   "<root>: Additional properties are not allowed ('passing_tests', 'totally' were unexpected)",
   "<root>: 'roles' is a required property"
  ],
  "invalid_obligation_kind_errors": 1,
  "invalid_obligation_kind_head": [
   "roles/0/obligations/0/kind: 'obligation' was expected"
  ],
  "reviewer_obligation_in_permissions_errors": 3,
  "reviewer_obligation_in_permissions_head": [
   "roles/0/permissions/0: Additional properties are not allowed ('discharge_artifact', 'must_discharge' were unexpected)",
   "roles/0/permissions/0: 'may_leave_unused' is a required property",
   "roles/0/permissions/0/kind: 'permission' was expected"
  ]
 },
 "negative_controls": [
  {
   "fired_on_garbage_schema": true,
   "fired_on_unmet_obligation": true,
   "id": "NC-UNUSED-PERMISSION-AND-GARBAGE",
   "silent_on_unused_permission": true,
   "verbatim": "On fixtures/seat_unused_permission.json (permission consult_web unused, obligation emit_critique discharged) v2 role_check returned []. On fixtures/seat_unmet_obligation.json (emit_critique not discharged) the same checker returned UNMET_OBLIGATION:emit_critique. On fixtures/invalid_garbage.json Draft202012Validator returned 2 errors (head=[\"<root>: Additional properties are not allowed ('passing_tests', 'totally' were unexpected)\", \"<root>: 'roles' is a required property\"]). A silent unused-permission check or a 0-error garbage validation is the state this unit is meant to reject."
  }
 ],
 "question": "What are the three distinct things a role grants (an obligation the participant MUST discharge, a permission it MAY use, a right nobody may deny it), and which of the existing $defs.role fields conflates them?",
 "repair": {
  "checker": "command-center/p2-wave/probes/CNL-0022/role_check.py",
  "reconstructed_v1": "command-center/p2-wave/probes/CNL-0022/defs_role_v1.schema.json",
  "rule": "obligations[].id must appear in seat.discharged; permissions[] may be absent from used_permissions; rights[].id must not appear in denied_rights; grant ids must not overlap across buckets.",
  "schema": "command-center/p2-wave/probes/CNL-0022/role_mandate.schema.json"
 },
 "residual_unknowns": [
  "Byte-level $defs.role in 11-COUNCIL-SPECIFICATION.schema.json is not on this worktree; if a later lane places the file, re-run reconstruct.py and replace catalog-quotations with disk:$defs.role.",
  "command-center/schema/councilspec.v2.schema.json exists as a generated shim that $refs generic_report and does not define $defs.role. This note is JSON in the catalog .md path so G-1 can parse it."
 ],
 "reviewer": {
  "independent": true,
  "instances": [
   "command-center/p2-wave/probes/CNL-0022/fixtures/reviewer_counterexample_v1.json",
   "command-center/p2-wave/probes/CNL-0022/fixtures/reviewer_obligation_in_permissions.json"
  ],
  "note": "Fresh-context reviewer is the schema validator plus the stuffed-kind instance; it never reads the author's answer field.",
  "reviewer_id": "CNL-0022-probe2-counterexample",
  "verdict": "PASS"
 },
 "schema_file": {
  "candidates": [
   {
    "exists": false,
    "path": "C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json"
   },
   {
    "exists": false,
    "path": "/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json"
   },
   {
    "exists": false,
    "path": "/opt/p2/ast-integrate/11-COUNCIL-SPECIFICATION.schema.json"
   },
   {
    "exists": false,
    "path": "/opt/p2/ast-integrate/command-center/sources/11-COUNCIL-SPECIFICATION.schema.json"
   },
   {
    "exists": true,
    "path": "/opt/p2/ast-integrate/platform/schema/councilspec.schema.json"
   },
   {
    "exists": true,
    "path": "/opt/p2/ast-integrate/command-center/schema/councilspec.v2.schema.json"
   }
  ],
  "found_path": "/opt/p2/ast-integrate/platform/schema/councilspec.schema.json",
  "parsed": true,
  "role_def": null,
  "source": "absent"
 },
 "sentinel": "SUCCESS:CNL-0022",
 "state": "SUCCESS",
 "tests": [
  {
   "denied_right_findings": [
    {
     "code": "DENIED_RIGHT",
     "id": "vote"
    }
   ],
   "id": "T-UNMET-VS-UNUSED",
   "known_good_findings": [],
   "name": "unmet obligation fails; unused permission does not",
   "result": "PASS",
   "unmet_obligation_findings": [
    {
     "artifact": "critique.md",
     "code": "UNMET_OBLIGATION",
     "id": "emit_critique"
    }
   ],
   "unused_permission_findings": [],
   "v1_unused_permission_findings": [
    {
     "code": "UNMET_PERMISSIONS_BAG",
     "id": "consult_web"
    },
    {
     "code": "UNMET_PERMISSIONS_BAG",
     "id": "vote"
    }
   ]
  },
  {
   "catalogue_errors": 0,
   "id": "T-JSONSCHEMA",
   "invalid_garbage_errors": 2,
   "name": "Draft202012Validator over every affected record plus vacuity",
   "result": "PASS"
  }
 ],
 "three_grants": {
  "obligation": {
   "definition": "a duty the seated participant must discharge; absence of the named discharge artifact fails the role check",
   "modal": "MUST"
  },
  "permission": {
   "definition": "a capability the seated participant may use; leaving it unused must not fail the role check",
   "modal": "MAY"
  },
  "right": {
   "definition": "an entitlement the runtime or chair may not strip; denial fails even if the participant never exercises it",
   "modal": "NOBODY-MAY-DENY"
  }
 },
 "title": "Role mandate schema: obligations vs permissions vs rights",
 "unit_id": "CNL-0022"
}
