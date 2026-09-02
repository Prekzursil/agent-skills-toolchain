"""Staged A9 hybrid adoption order. Proof obligations are predicates, not intentions."""
from __future__ import annotations

GATES_REL = "command-center/p2-wave/probes/ARC-0063/gates.py"
GATES_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0063/gates.py"
)

AUTHORITY_TABLE = [
    {
        "capability_class": "permission-evaluation",
        "authority": "permission-evaluator",
        "lands_at_stage": "S1",
        "borrowed_from": "A7",
        "not_authority": "per-subsystem ad-hoc allow lists",
    },
    {
        "capability_class": "capability-identity",
        "authority": "generated-ssot-registry",
        "lands_at_stage": "S2",
        "borrowed_from": "A2",
        "not_authority": "A1 static tree (import source only)",
    },
    {
        "capability_class": "activation-resident-set",
        "authority": "gateway-activation",
        "lands_at_stage": "S3",
        "borrowed_from": "A4",
        "not_authority": "always-loaded A1 config tree",
    },
    {
        "capability_class": "package-identity",
        "authority": "package-lockfile",
        "lands_at_stage": "S4",
        "borrowed_from": "A3",
        "not_authority": "public marketplace index (PR-ONLY forbids publish_channel)",
    },
    {
        "capability_class": "vendor-contract",
        "authority": "vendor-adapter",
        "lands_at_stage": "S5",
        "borrowed_from": "A6",
        "not_authority": "raw vendor API as a second work-unit contract",
    },
    {
        "capability_class": "work-unit-delivery",
        "authority": "runtime-ledger",
        "lands_at_stage": "S6",
        "borrowed_from": "A5",
        "not_authority": "ad-hoc rails / per-vendor queues",
    },
    {
        "capability_class": "operator-error-surface",
        "authority": "product-error-surface",
        "lands_at_stage": "S7",
        "borrowed_from": "A8",
        "not_authority": "subsystem-local error strings as a second contract",
    },
]


def _cmds(head_stage: str, gone: str, must_remain: str | None) -> list[str]:
    remain = (
        f'test -e "$CLONE/{must_remain}"'
        if must_remain
        else 'test -f "$CLONE/README.txt"'
    )
    return [
        f'test "$HEAD_STAGE" = "{head_stage}" || '
        f'(echo "revert later stacked PRs first; tip is not {head_stage}" && exit 1)',
        'git -C "$CLONE" revert --no-edit HEAD',
        f'test ! -e "$CLONE/{gone}"',
        remain,
        'test "$(git -C "$CLONE" rev-parse \'HEAD^{tree}\')" = "$PRE_STAGE_TREE"',
    ]


STAGES = [
    {
        "id": "S1",
        "order": 1,
        "subsystem": "permission-evaluator",
        "borrowed_from": "A7",
        "mechanism": (
            "Single permission choke point: every install/activation/dispatch/"
            "workflow-invocation path must cross one evaluator (catalog ARC-0045/ARC-0062)."
        ),
        "lands_via": "pull-request",
        "proof_obligation": (
            "Every enumerated entry path is in evaluator.covered_paths, and the planted "
            "bypass path is reported uncovered. Artifacts: hybrid/permission-evaluator.json, "
            "hybrid/enumerated-paths.json, hybrid/planted-bypass.json."
        ),
        "proof_predicate": (
            "set(enumerated-paths.json.paths) <= set(permission-evaluator.json.covered_paths) "
            "AND planted-bypass.json.path not in covered_paths AND "
            "planted-bypass.json.crosses_evaluator is false AND "
            "len(control-planes.json.rows)==1 AND that row.authority==permission-evaluator"
        ),
        "proof_evaluator": GATES_REL,
        "proof_command": f"{GATES_CMD} --stage S1",
        "proof_test_id": "ARC0063-G-S1",
        "artifacts_at_stage": [
            "hybrid/permission-evaluator.json",
            "hybrid/enumerated-paths.json",
            "hybrid/planted-bypass.json",
            "hybrid/control-planes.json",
        ],
        "rollback_commands": _cmds(
            "S1", "hybrid/permission-evaluator.json", None
        ),
        "pr_title": "A9 S1: land the single permission evaluator before any new entry path",
        "must_not_introduce": "a second permission evaluator or an uncovered live entry path",
    },
    {
        "id": "S2",
        "order": 2,
        "subsystem": "generated-ssot-registry",
        "borrowed_from": "A2",
        "mechanism": (
            "A2 typed registry is the sole capability-identity authority. A1 static trees "
            "are extract sources (ARC-0003 DESIGN, ARC-0007/ARC-0014 migration): live-unique "
            "remainder is queued, never a second catalog and never an opaque passthrough."
        ),
        "lands_via": "pull-request",
        "proof_obligation": (
            "Registry exists; generated projections cite registry_id; load-order does not "
            "treat hybrid/a1-import/ as authority; A1 unique line is on the adjudication queue."
        ),
        "proof_predicate": (
            "registry.json.authority==generated-ssot-registry AND "
            "generated/skill.council.json.provenance.registry_id==skill.council AND "
            "'hybrid/a1-import/' in load-order.json.not_authority AND "
            "LIVE-ONLY-LINE:synthetic-ARC-0063-a1-remainder in adjudication-queue.json AND "
            "permission-evaluator.json byte-identical to S1"
        ),
        "proof_evaluator": GATES_REL,
        "proof_command": f"{GATES_CMD} --stage S2",
        "proof_test_id": "ARC0063-G-S2",
        "artifacts_at_stage": [
            "hybrid/registry.json",
            "hybrid/generated/skill.council.json",
            "hybrid/a1-import/skill.council.skill.json",
            "hybrid/adjudication-queue.json",
            "hybrid/load-order.json",
        ],
        "rollback_commands": _cmds(
            "S2", "hybrid/registry.json", "hybrid/permission-evaluator.json"
        ),
        "pr_title": "A9 S2: land generated SSOT; A1 remains import-only",
        "must_not_introduce": "A1 as a live second catalog or opaque_body passthrough",
    },
    {
        "id": "S3",
        "order": 3,
        "subsystem": "gateway-activation",
        "borrowed_from": "A4",
        "mechanism": (
            "Gateway indexes registry ids but materializes only the selected set; "
            "resident-set floor is evaluator+index; not-selected is distinct from not-installed."
        ),
        "lands_via": "pull-request",
        "proof_obligation": (
            "gateway-index ids are a subset of registry entry ids; every activation event "
            "carries a permission_ticket; nothing-selected resident set excludes generated bodies."
        ),
        "proof_predicate": (
            "set(gateway-index.json.ids) <= set(registry entry ids) AND "
            "all(activation-log events have permission_ticket) AND "
            "skill.council in selection-state.selected AND "
            "wf.catalog-class.discovery-only in selection-state.not_selected AND "
            "mcp.missing.example in selection-state.not_installed"
        ),
        "proof_evaluator": GATES_REL,
        "proof_command": f"{GATES_CMD} --stage S3",
        "proof_test_id": "ARC0063-G-S3",
        "artifacts_at_stage": [
            "hybrid/gateway-index.json",
            "hybrid/activation-log.json",
            "hybrid/resident-set.json",
            "hybrid/selection-state.json",
        ],
        "rollback_commands": _cmds(
            "S3", "hybrid/gateway-index.json", "hybrid/registry.json"
        ),
        "pr_title": "A9 S3: land gateway activation over the registry, not a parallel catalog",
        "must_not_introduce": "a gateway-owned capability catalog",
    },
    {
        "id": "S4",
        "order": 4,
        "subsystem": "package-lockfile",
        "borrowed_from": "A3",
        "mechanism": (
            "Lockfile-pinned local packages under PR-ONLY: publish_channel is null. "
            "Package identity is the lockfile; capability identity stays the registry."
        ),
        "lands_via": "pull-request",
        "proof_obligation": (
            "lockfile.pins sha256-match package bytes; publish_channel is JSON null; "
            "package-map values are registry ids; no public index file is written."
        ),
        "proof_predicate": (
            "lockfile.json.publish_channel is None AND lockfile.json.release_mode==PR-ONLY AND "
            "lockfile.pins[pkg]==sha256(packages/pkg-skill-council.json) AND "
            "package-map.json[pkg-skill-council]==skill.council AND "
            "not exists(hybrid/public-index.json)"
        ),
        "proof_evaluator": GATES_REL,
        "proof_command": f"{GATES_CMD} --stage S4",
        "proof_test_id": "ARC0063-G-S4",
        "artifacts_at_stage": [
            "hybrid/lockfile.json",
            "hybrid/packages/pkg-skill-council.json",
            "hybrid/package-map.json",
        ],
        "rollback_commands": _cmds(
            "S4", "hybrid/lockfile.json", "hybrid/gateway-index.json"
        ),
        "pr_title": "A9 S4: land lockfile packages with publish_channel null (PR-ONLY)",
        "must_not_introduce": "a public marketplace index or a second capability catalog",
    },
    {
        "id": "S5",
        "order": 5,
        "subsystem": "vendor-adapter",
        "borrowed_from": "A6",
        "mechanism": (
            "One work-unit contract with GUARANTEED/BEST-EFFORT/VENDOR-ONLY tiers; "
            "silent downgrade is refused; vendor output is untrusted; evaluator is consulted."
        ),
        "lands_via": "pull-request",
        "proof_obligation": (
            "Every adapter-contract field has exactly one tier; downgrade-refusal is FAIL-LOUD; "
            "canary secret is not in the forward log; permission_ticket is present."
        ),
        "proof_predicate": (
            "set(adapter-contract.json.fields.values()) <= {GUARANTEED,BEST-EFFORT,VENDOR-ONLY} "
            "AND each field has exactly one tier AND "
            "conformance-matrix.json.downgrade_refusal.result==FAIL-LOUD AND "
            "CANARY-SECRET not in untrusted-forward-log.json.forwarded AND "
            "untrusted-forward-log.json.permission_ticket startswith a7-single-choke"
        ),
        "proof_evaluator": GATES_REL,
        "proof_command": f"{GATES_CMD} --stage S5",
        "proof_test_id": "ARC0063-G-S5",
        "artifacts_at_stage": [
            "hybrid/adapter-contract.json",
            "hybrid/conformance-matrix.json",
            "hybrid/untrusted-forward-log.json",
        ],
        "rollback_commands": _cmds(
            "S5", "hybrid/adapter-contract.json", "hybrid/lockfile.json"
        ),
        "pr_title": "A9 S5: land cross-vendor adapter with loud mismatch, no secret forward",
        "must_not_introduce": "a vendor-native work-unit contract that bypasses the adapter",
    },
    {
        "id": "S6",
        "order": 6,
        "subsystem": "runtime-ledger",
        "borrowed_from": "A5",
        "mechanism": (
            "Append-only ledger, at-least-once plus idempotent units, one winner on "
            "duplicate dispatch, in-flight work preserved when folding ad-hoc rails."
        ),
        "lands_via": "pull-request",
        "proof_obligation": (
            "ledger seq is monotone; duplicate-dispatch winners==1; in-flight.dropped is empty; "
            "first ledger record has permission_ticket and via_adapter true."
        ),
        "proof_predicate": (
            "ledger seqs == [1,2] AND duplicate-dispatch.json.winners==1 AND "
            "in-flight.json.dropped==[] AND ledger[0].via_adapter is true AND "
            "ledger[0].permission_ticket startswith a7-single-choke"
        ),
        "proof_evaluator": GATES_REL,
        "proof_command": f"{GATES_CMD} --stage S6",
        "proof_test_id": "ARC0063-G-S6",
        "artifacts_at_stage": [
            "hybrid/ledger.jsonl",
            "hybrid/in-flight.json",
            "hybrid/duplicate-dispatch.json",
        ],
        "rollback_commands": _cmds(
            "S6", "hybrid/ledger.jsonl", "hybrid/adapter-contract.json"
        ),
        "pr_title": "A9 S6: land runtime ledger over adapter+evaluator, keep in-flight work",
        "must_not_introduce": "a second completion reducer or a dispatch path around the adapter",
    },
    {
        "id": "S7",
        "order": 7,
        "subsystem": "product-error-surface",
        "borrowed_from": "A8",
        "mechanism": (
            "One error-message contract (happened / means / next_action) and aliases that "
            "resolve only to registry ids. Does not own capability identity."
        ),
        "lands_via": "pull-request",
        "proof_obligation": (
            "error-contract samples include happened, means, next_action; every alias target "
            "is a registry id; control-planes table still has exactly one authority per row."
        ),
        "proof_predicate": (
            "all(samples have happened,means,next_action) AND "
            "all(aliases.values() in registry ids) AND "
            "all(len(authorities per capability_class)==1)"
        ),
        "proof_evaluator": GATES_REL,
        "proof_command": f"{GATES_CMD} --stage S7",
        "proof_test_id": "ARC0063-G-S7",
        "artifacts_at_stage": [
            "hybrid/error-contract.json",
            "hybrid/aliases.json",
            "hybrid/control-planes.json",
        ],
        "rollback_commands": _cmds(
            "S7", "hybrid/error-contract.json", "hybrid/ledger.jsonl"
        ),
        "pr_title": "A9 S7: land the product error contract last, aliases to registry ids only",
        "must_not_introduce": "a UX-owned second catalog or a second error contract",
    },
]


def stage_by_id(sid: str) -> dict:
    for row in STAGES:
        if row["id"] == sid:
            return row
    raise KeyError(sid)
