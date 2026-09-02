"""REL-bucket defect corpus for the regression-seed generator.

Sibling REL-0001..REL-0023 have not emitted live defect receipts on this
worktree. Each row is therefore a fixture seeded from that unit's primary
failure class, with an executable oracle against a two-commit subject.
Origin is labelled so a live receipt cannot be mistaken for a fixture.
"""
from __future__ import annotations

# Each defect: oracle is ceremony_gates.<fn>(*args) == expected
# Broken subject returns a different value; fixed subject matches expected.

DEFECTS: list[dict] = [
    {
        "defect_id": "DEF-REL-0001-patch-on-required-key-delete",
        "source_unit": "REL-0001",
        "failure_class": "spec-underspecified",
        "fn": "semver_bump",
        "args": [{"deleted_required_key": True}],
        "expected": "MAJOR",
    },
    {
        "defect_id": "DEF-REL-0002-action-without-inverse",
        "source_unit": "REL-0002",
        "failure_class": "contract-gap",
        "fn": "inverse_ok",
        "args": [{"action": "write_file", "inverse": None, "irreversible": False}],
        "expected": False,
    },
    {
        "defect_id": "DEF-REL-0003-second-question-in-packet",
        "source_unit": "REL-0003",
        "failure_class": "unsatisfiable-stop-condition",
        "fn": "packet_question_count_ok",
        "args": [["q1", "q2"]],
        "expected": False,
    },
    {
        "defect_id": "DEF-REL-0004-listing-as-hook-pass",
        "source_unit": "REL-0004",
        "failure_class": "green-not-live",
        "fn": "hook_observed",
        "args": [True, False],
        "expected": False,
    },
    {
        "defect_id": "DEF-REL-0005-migration-double-apply",
        "source_unit": "REL-0005",
        "failure_class": "migration-non-idempotent",
        "fn": "migration_apply_count",
        "args": [1],
        "expected": 1,
    },
    {
        "defect_id": "DEF-REL-0006-files-exist-as-restore",
        "source_unit": "REL-0006",
        "failure_class": "false-restore",
        "fn": "restore_behaviour_match",
        "args": ["old", "new"],
        "expected": False,
    },
    {
        "defect_id": "DEF-REL-0007-dangling-hook-after-uninstall",
        "source_unit": "REL-0007",
        "failure_class": "orphan-residue",
        "fn": "orphan_count",
        "args": [["hook.stale"]],
        "expected": 1,
    },
    {
        "defect_id": "DEF-REL-0008-hostile-name-silent-skip",
        "source_unit": "REL-0008",
        "failure_class": "silent-skip-as-pass",
        "fn": "hostile_walk_ok",
        "args": [["ok.txt", 'x"y.txt']],
        "expected": False,
    },
    {
        "defect_id": "DEF-REL-0009-filesystem-not-archive",
        "source_unit": "REL-0009",
        "failure_class": "wrong-input-surface",
        "fn": "archive_allowlist_ok",
        "args": [["secret.git/config"], ["ok.txt"], ["ok.txt"]],
        "expected": False,
    },
    {
        "defect_id": "DEF-REL-0010-missed-canary-secret",
        "source_unit": "REL-0010",
        "failure_class": "detector-failure",
        "fn": "secret_canary_found",
        "args": ["token=AKIA_CANARY_REL0024", "AKIA_CANARY_REL0024"],
        "expected": True,
    },
    {
        "defect_id": "DEF-REL-0011-sbom-missing-dep",
        "source_unit": "REL-0011",
        "failure_class": "sbom-incomplete",
        "fn": "sbom_matches_closure",
        "args": [["a"], ["a", "b"]],
        "expected": False,
    },
    {
        "defect_id": "DEF-REL-0012-unsigned-without-gap",
        "source_unit": "REL-0012",
        "failure_class": "unsigned-artifact",
        "fn": "tamper_ok",
        "args": [False, False],
        "expected": False,
    },
    {
        "defect_id": "DEF-REL-0013-rider-normalised-away",
        "source_unit": "REL-0013",
        "failure_class": "rider-normalised-away",
        "fn": "rider_blocks",
        "args": [["MIT", "MIT+field-of-use-rider"]],
        "expected": True,
    },
    {
        "defect_id": "DEF-REL-0014-tool-error-as-pass",
        "source_unit": "REL-0014",
        "failure_class": "tool-error-as-pass",
        "fn": "advisory_scan_pass",
        "args": ["ERROR"],
        "expected": False,
    },
    {
        "defect_id": "DEF-REL-0015-unrun-cell-as-pass",
        "source_unit": "REL-0015",
        "failure_class": "unrun-cell-as-pass",
        "fn": "matrix_cell_pass",
        "args": ["UNRUN"],
        "expected": False,
    },
    {
        "defect_id": "DEF-REL-0016-hand-written-ungrounded-claim",
        "source_unit": "REL-0016",
        "failure_class": "ungrounded-claim",
        "fn": "notes_grounded",
        "args": [["we improved latency 40%"], ["claim-1"]],
        "expected": False,
    },
    {
        "defect_id": "DEF-REL-0017-source-unique-destroyed",
        "source_unit": "REL-0017",
        "failure_class": "one-directional-sync",
        "fn": "source_unique_preserved",
        "args": ["abc", "gone"],
        "expected": False,
    },
    {
        "defect_id": "DEF-REL-0018-not-checked-as-true",
        "source_unit": "REL-0018",
        "failure_class": "unprobed-as-pass",
        "fn": "gate_go",
        "args": [["TRUE", "NOT-CHECKED"]],
        "expected": False,
    },
    {
        "defect_id": "DEF-REL-0019-tiny-sample-threshold",
        "source_unit": "REL-0019",
        "failure_class": "default-pass-threshold",
        "fn": "threshold_publishable",
        "args": [2, 30, 0.0],
        "expected": False,
    },
    {
        "defect_id": "DEF-REL-0020-poison-survives-refresh",
        "source_unit": "REL-0020",
        "failure_class": "stale-cache-masking",
        "fn": "cache_refresh_clears_poison",
        "args": ["old-bytes", "old-bytes"],
        "expected": False,
    },
    {
        "defect_id": "DEF-REL-0021-two-way-not-three-way",
        "source_unit": "REL-0021",
        "failure_class": "repo-live-drift",
        "fn": "three_way_parity",
        "args": ["aaa", "aaa", "bbb"],
        "expected": False,
    },
    {
        "defect_id": "DEF-REL-0022-manifest-trusted-not-instrumented",
        "source_unit": "REL-0022",
        "failure_class": "dead-manifest-entry",
        "fn": "rollback_coverage_ok",
        "args": [False, True],
        "expected": False,
    },
    {
        "defect_id": "DEF-REL-0023-revoked-still-resolves",
        "source_unit": "REL-0023",
        "failure_class": "withdrawal-ineffective",
        "fn": "resolve_ok",
        "args": ["revoked", False],
        "expected": False,
    },
]


def sibling_unit_ids() -> list[str]:
    return [f"REL-{i:04d}" for i in range(1, 24)]
