"""Live finding records for SYN-0001, taken from this worktree's ARC probes.

Catalog inputs CLAIM-REGISTRY.json, RISK-REGISTER.md, UNKNOWNS-REGISTER.md,
Phase 11/12/13 B09/B10/B11 verdicts, and _USER-PROMPTS.md are ABSENT here.
Phase-3 A1 DESIGN/FAILURE-MODES/REFUTATION and A2 FAILURE-MODES/MIGRATION
are also absent (only A2 DESIGN.json and phase3/ROSTER.json exist).

The hierarchy is therefore the causal DAG of the live ARC-0005 / ARC-0009 /
ARC-0010 / ARC-0012 / ARC-0014 / ARC-0016 probe corpus that is on disk, not
a claim that the missing program-wide registers were synthesized. Each
record carries explicit family_id; the builder will not hang unrelated
families off one synthetic root.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from anchors import make_anchor

A5E = "command-center/p2-wave/probes/ARC-0005/emit.py"
A5P1 = "command-center/p2-wave/probes/ARC-0005/probe1-divergence.raw.json"
A5P2 = "command-center/p2-wave/probes/ARC-0005/probe2-both-states.raw.json"
A5S = "command-center/p2-wave/probes/ARC-0005/stop_hook.py"
A9L = "command-center/p2-wave/probes/ARC-0009/a1_loader.py"
A9E = "command-center/p2-wave/probes/ARC-0009/emit_refutation.py"
A9M = (
    "command-center/p2-wave/probes/ARC-0009/fixtures/estate/"
    "unlisted-orphan/MANIFEST.json"
)
A2D = "command-center/phase3/A2/DESIGN.json"
GEN = "command-center/p2-wave/probes/ARC-0010/generator.py"
REG = "command-center/p2-wave/probes/ARC-0010/registry.json"
A16E = "command-center/p2-wave/probes/ARC-0016/emit_refutation.py"
A16H = "command-center/p2-wave/probes/ARC-0016/hatch.py"
A14E = "command-center/p2-wave/probes/ARC-0014/emit_migration.py"
A12E = "command-center/p2-wave/probes/ARC-0012/emit_failure_modes.py"
A12R = "command-center/p2-wave/probes/ARC-0012/reviewer.py"

CATALOG_INPUTS = [
    ("command-center/CLAIM-REGISTRY.json", False),
    ("command-center/RISK-REGISTER.md", False),
    ("command-center/UNKNOWNS-REGISTER.md", False),
    ("_USER-PROMPTS.md", False),
    ("command-center/phase3/A1/DESIGN.json", False),
    ("command-center/phase3/A1/FAILURE-MODES.json", False),
    ("command-center/phase3/A1/REFUTATION.json", False),
    ("command-center/phase3/A2/FAILURE-MODES.json", False),
    ("command-center/phase3/A2/MIGRATION.json", False),
]


def _rec(
    *,
    nid: str,
    typ: str,
    title: str,
    statement: str,
    family_id: str,
    parent_id: str | None,
    mechanism: str,
    claim_ids: list[str],
    evidence: list[tuple[str, str]],
) -> dict[str, Any]:
    return {
        "id": nid,
        "type": typ,
        "title": title,
        "statement": statement,
        "family_id": family_id,
        "parent_id": parent_id,
        "mechanism": mechanism,
        "claim_ids": claim_ids,
        "evidence_specs": evidence,
        "single_source": False,
    }


def live_records() -> list[dict[str, Any]]:
    fam_a1_trees = "a1.dual-writable-trees-without-emitter"
    fam_a1_manifest = "a1.manifest-defines-load-set"
    fam_a2_ssot = "a2.typed-registry-is-not-lossless-ssot"
    fam_a2_path = "a2.path-presence-is-not-freshness"
    return [
        _rec(
            nid="cause.a1.dual-writable-trees-without-emitter",
            typ="CAUSE",
            title="A1 keeps two writable trees and has no emitter to reconcile them",
            statement=(
                "Config-first A1 is specified with no_generated_layer and "
                "no_resident_runtime. Live bytes cannot be projected from repo "
                "bytes, so divergence is a standing property of the architecture "
                "rather than a transient operator error."
            ),
            family_id=fam_a1_trees,
            parent_id=None,
            mechanism="",
            claim_ids=["ARC-0005-C1", "ARC-0005-C3"],
            evidence=[
                (A5E, '"no_generated_layer": true'),
                (A5E, '"no_resident_runtime": true'),
                (A5P1, '"union_files": 20'),
            ],
        ),
        _rec(
            nid="mech.a1.no-generated-layer",
            typ="MECHANISM",
            title="Absence of a generated layer means live cannot be emitted from repo",
            statement=(
                "Without a generator, the live tree is a second source of truth. "
                "The fixture census is two-directional (repo-larger and live-larger), "
                "not a one-way copy lag."
            ),
            family_id=fam_a1_trees,
            parent_id="cause.a1.dual-writable-trees-without-emitter",
            mechanism="no generated layer, so live is not a projection of repo",
            claim_ids=["ARC-0005-C1"],
            evidence=[
                (A5E, '"no_generated_layer": true'),
                (A5P1, '"identical": 4'),
            ],
        ),
        _rec(
            nid="sym.a1.fixture-divergence-4-of-20",
            typ="SYMPTOM",
            title="Fixture census: 4 identical of 20 union files; 7 repo-larger, 3 live-larger",
            statement=(
                "Today's measurement on this worktree is the ARC-0005 fixture "
                "census (union=20 identical=4). The catalog sentence 5/88 of "
                "2026-08-09 is not today's host-tree measurement; host rule trees "
                "are absent."
            ),
            family_id=fam_a1_trees,
            parent_id="mech.a1.no-generated-layer",
            mechanism="two writable trees drift independently on content and size",
            claim_ids=["ARC-0005-C2"],
            evidence=[
                (A5P1, '"union_files": 20'),
                (A5P1, '"identical": 4'),
            ],
        ),
        _rec(
            nid="mech.a1.no-resident-runtime",
            typ="MECHANISM",
            title="No resident runtime to reconcile or fail-close at activation",
            statement=(
                "A1 has no resident runtime, so drift is visible only after the "
                "fact (Stop-hook path). Detection latency on the planted-bad "
                "fixture is measured; it does not prevent the drift."
            ),
            family_id=fam_a1_trees,
            parent_id="cause.a1.dual-writable-trees-without-emitter",
            mechanism="no resident runtime, so reconciliation cannot run at activation",
            claim_ids=["ARC-0005-C3"],
            evidence=[
                (A5E, '"no_resident_runtime": true'),
                (A5S, "STOP-HOOK DRIFT WARNING"),
            ],
        ),
        _rec(
            nid="sym.a1.detection-is-post-hoc-stop-hook",
            typ="SYMPTOM",
            title="Stop-hook detects planted live drift after the fact",
            statement=(
                "The Stop-hook fires on the planted-bad fixture and is silent "
                "on good/revert. That is detection, not prevention. The smallest "
                "A1-compatible structural fix named in the dossier is one writable tree."
            ),
            family_id=fam_a1_trees,
            parent_id="mech.a1.no-resident-runtime",
            mechanism="Stop-hook observes drift only after the session already used live bytes",
            claim_ids=["ARC-0005-C3", "ARC-0005-C4"],
            evidence=[
                (A5P2, '"stop_hook_warning_on_bad": true'),
                (A5S, "STOP-HOOK DRIFT WARNING"),
            ],
        ),
        _rec(
            nid="cause.a1.manifest-defines-load-set",
            typ="CAUSE",
            title="A1 loads only what MANIFEST.json lists; on-disk extras are silent skips",
            statement=(
                "unlisted_file is specified as a silent omit: a capabilities file "
                "absent from MANIFEST.json is not loaded. Combined with no generator "
                "and no runtime, omission cannot be caught at generate-time or "
                "activation-time."
            ),
            family_id=fam_a1_manifest,
            parent_id=None,
            mechanism="",
            claim_ids=["ARC-0009-C1", "ARC-0009-C2", "ARC-0005-C5"],
            evidence=[
                (A9L, "A file absent from MANIFEST.json is not loaded"),
                (A9E, "REFUTED as min-risk"),
            ],
        ),
        _rec(
            nid="mech.a1.unlisted-file-silent-omit",
            typ="MECHANISM",
            title="Unlisted on-disk files are not loaded and do not fail the load",
            statement=(
                "The load set is the manifest, not the directory listing. Silence "
                "is the specified behaviour, not a wording slip. Duplicate-in-one-file "
                "is FAIL-CLOSED; unlisted_file is not."
            ),
            family_id=fam_a1_manifest,
            parent_id="cause.a1.manifest-defines-load-set",
            mechanism="manifest is the load set; directory presence is not a load signal",
            claim_ids=["ARC-0009-C2", "ARC-0005-C5"],
            evidence=[
                (A9L, "The skip is silent: no error, no warning, no"),
                (A9M, "Files not listed are not loaded (DESIGN precedence.unlisted_file)."),
            ],
        ),
        _rec(
            nid="sym.a1.min-risk-claim-refuted",
            typ="SYMPTOM",
            title="A1 'min-risk because fewer moving parts' is REFUTED",
            statement=(
                "Removing the generator and runtime removes the detectors that "
                "would FAIL-CLOSE on missing capabilities. Config-first still "
                "minimises surprise execution of unreviewed files; it does not "
                "minimise surprise absence."
            ),
            family_id=fam_a1_manifest,
            parent_id="mech.a1.unlisted-file-silent-omit",
            mechanism="silent omit plus missing detectors is surprise absence, not min-risk",
            claim_ids=["ARC-0009-C1"],
            evidence=[
                (A9E, "REFUTED as min-risk"),
                (A9L, "A file absent from MANIFEST.json is not loaded"),
            ],
        ),
        _rec(
            nid="sym.a1.on-disk-capability-not-loaded",
            typ="SYMPTOM",
            title="On-disk capability absent from MANIFEST.json is silently not loaded",
            statement=(
                "Reviewer-added FC-A1-UNLISTED-FILE: declared-vs-on-disk is a third "
                "drift axis orthogonal to repo-vs-live hashing."
            ),
            family_id=fam_a1_manifest,
            parent_id="mech.a1.unlisted-file-silent-omit",
            mechanism="load walks the manifest, so an unlisted file is invisible by design",
            claim_ids=["ARC-0005-C5"],
            evidence=[
                (A9M, "Files not listed are not loaded (DESIGN precedence.unlisted_file)."),
                (A9E, "silently omits an on-disk skill"),
            ],
        ),
        _rec(
            nid="cause.a2.typed-registry-is-not-lossless-ssot",
            typ="CAUSE",
            title="A typed generated SSOT cannot encode opaque remainder without reintroducing drift",
            statement=(
                "A2's first non-expressible construct is an opaque passthrough / "
                "untyped blob copied into generated output. The schema refuses that "
                "field. Completeness over the whole estate is therefore false; the "
                "typed subset is a pure projection, not a lossless encoding."
            ),
            family_id=fam_a2_ssot,
            parent_id=None,
            mechanism="",
            claim_ids=["ARC-0016-C1", "ARC-0016-C2", "ARC-0010-expressibility"],
            evidence=[
                (A2D, '"first_non_expressible_construct"'),
                (A16E, "REFUTED as complete-SSOT"),
                (GEN, "BANNED_KEYS = frozenset"),
            ],
        ),
        _rec(
            nid="mech.a2.opaque-passthrough-refused",
            typ="MECHANISM",
            title="Refusing opaque_body prevents hatch capture-back of hand-edits as CLEAN",
            statement=(
                "Copying opaque_body into generated output lets a hand-edit be "
                "captured back into the registry and return CLEAN — the drift A2 "
                "exists to prevent. Typed regenerate reports TAMPERED and discards it. "
                "Do not rebuild A2 to add the hatch."
            ),
            family_id=fam_a2_ssot,
            parent_id="cause.a2.typed-registry-is-not-lossless-ssot",
            mechanism="untyped blob in generated output launders a hand-edit as CLEAN",
            claim_ids=["ARC-0016-C2"],
            evidence=[
                (A2D, '"stop_reason"'),
                (GEN, "BANNED_KEYS = frozenset"),
            ],
        ),
        _rec(
            nid="sym.a2.hatch-would-launder-hand-edits",
            typ="SYMPTOM",
            title="Escape-hatch capture-back of a hand-edit would be reported CLEAN",
            statement=(
                "ARC-0016 reproduced the hatch: typed A2 rejects opaque_body; a hatch "
                "that copies it reintroduces drift. The catching architecture is refusing "
                "the hatch, not splitting the generator."
            ),
            family_id=fam_a2_ssot,
            parent_id="mech.a2.opaque-passthrough-refused",
            mechanism="hatch copies untyped bytes into generated artifacts and back into the registry",
            claim_ids=["ARC-0016-C2"],
            evidence=[
                (A16E, "REFUTED as complete-SSOT"),
                (A2D, '"first_non_expressible_construct"'),
            ],
        ),
        _rec(
            nid="sym.a2.live-larger-queued-not-encoded",
            typ="SYMPTOM",
            title="Live-larger remainder is queued for adjudication, not stuffed into opaque_body",
            statement=(
                "ARC-0014 extract+regenerate queues live-larger remainder. Migration "
                "forbids adding opaque_body to save the remainder."
            ),
            family_id=fam_a2_ssot,
            parent_id="mech.a2.opaque-passthrough-refused",
            mechanism="typed fields cannot round-trip live-larger comments, so remainder is queued",
            claim_ids=["ARC-0014-roundtrip"],
            evidence=[
                (A14E, "without dropping live-larger remainder"),
                (A14E, "instead of adding opaque_body"),
            ],
        ),
        _rec(
            nid="mech.a2.shared-path-provenance-helper",
            typ="MECHANISM",
            title="Every renderer calls the same provenance() helper",
            statement=(
                "A2 generate() is a single shared path. One bug in provenance() "
                "rewrites generator_version (or equivalent) across every generated file. "
                "That blast radius equals the generated file count; it is the cost of "
                "one SSOT generator, not a reason to split it or add a hatch."
            ),
            family_id=fam_a2_ssot,
            parent_id="cause.a2.typed-registry-is-not-lossless-ssot",
            mechanism="one shared provenance() helper is invoked by every renderer",
            claim_ids=["ARC-0016-C3"],
            evidence=[
                (GEN, "def provenance("),
                (A16H, '"files_affected_by_one_shared_path_bug"'),
            ],
        ),
        _rec(
            nid="sym.a2.blast-radius-equals-generated-file-count",
            typ="SYMPTOM",
            title="One shared-path generator bug hits all generated files",
            statement=(
                "Measured blast radius equals generated file count when provenance is "
                "monkey-patched. The count is computed from generate() output, not asserted."
            ),
            family_id=fam_a2_ssot,
            parent_id="mech.a2.shared-path-provenance-helper",
            mechanism="every renderer calls provenance(), so a helper bug fans out to the whole tree",
            claim_ids=["ARC-0016-C3"],
            evidence=[
                (A16H, '"files_affected_by_one_shared_path_bug"'),
                (GEN, "def provenance("),
            ],
        ),
        _rec(
            nid="cause.a2.path-presence-is-not-freshness",
            typ="CAUSE",
            title="Path-completeness gates do not see stale-but-present generated bytes",
            statement=(
                "Direction A (registry row, no non-empty output) and Direction B "
                "(output file, no registry row) are necessary and still not sufficient. "
                "FM-STALE-BYTES: a file at the mapped path with size>0 silences both "
                "directions even when bytes are from generator vN-1."
            ),
            family_id=fam_a2_path,
            parent_id=None,
            mechanism="",
            claim_ids=["ARC-0012-C2", "ARC-0012-C4", "ARC-0012-C5"],
            evidence=[
                (A12E, '"live_direction_a_count"'),
                (A12R, '"id": "FM-STALE-BYTES"'),
                (REG, '"id": "plugin.harness"'),
            ],
        ),
        _rec(
            nid="mech.a2.direction-a-orphan-registry-rows",
            typ="MECHANISM",
            title="Direction A treats missing or empty generated files as orphan registry rows",
            statement=(
                "Live tree today: Direction A is non-zero because the A2 generated "
                "tree has not been written. Empty files count as missing."
            ),
            family_id=fam_a2_path,
            parent_id="cause.a2.path-presence-is-not-freshness",
            mechanism="registry rows map to paths that are absent or zero-byte on this tree",
            claim_ids=["ARC-0012-C3"],
            evidence=[
                (A12E, '"live_direction_a_count"'),
                (REG, '"id": "plugin.harness"'),
            ],
        ),
        _rec(
            nid="sym.a2.live-direction-a-equals-10",
            typ="SYMPTOM",
            title="Live Direction A reports orphan registry rows",
            statement=(
                "The live A2 typed registry has rows (including plugin.harness) whose "
                "mapped generated files are not on disk. A combined 'all consistent' "
                "integer is rejected; the two counts are reported separately."
            ),
            family_id=fam_a2_path,
            parent_id="mech.a2.direction-a-orphan-registry-rows",
            mechanism="unwritten generated tree leaves every registry row without an output",
            claim_ids=["ARC-0012-C2", "ARC-0012-C3"],
            evidence=[
                (A12E, '"live_direction_a_count"'),
                (A12E, '"live_direction_b_count"'),
            ],
        ),
        _rec(
            nid="mech.a2.vacuous-direction-b-on-empty-scan",
            typ="MECHANISM",
            title="Direction B is zero because the scan root is empty, not because the generator is complete",
            statement=(
                "Direction B=0 on this tree is an empty scan. It is trusted only after "
                "detector-control (planted unregistered file fires). Vacuous zero is "
                "not a pass on leftovers or on freshness."
            ),
            family_id=fam_a2_path,
            parent_id="cause.a2.path-presence-is-not-freshness",
            mechanism="empty generated root yields zero unregistered outputs by construction",
            claim_ids=["ARC-0012-C4"],
            evidence=[
                (A12E, '"live_direction_b_count"'),
                (A12R, '"id": "FM-STALE-BYTES"'),
            ],
        ),
        _rec(
            nid="sym.a2.live-direction-b-equals-0",
            typ="SYMPTOM",
            title="Live Direction B = 0 (empty scan, not a completeness pass)",
            statement=(
                "B is silent for lack of outputs. Claiming the current repository "
                "would not fail a generator-completeness gate is REFUTED: A fails, "
                "and B's zero is not freshness."
            ),
            family_id=fam_a2_path,
            parent_id="mech.a2.vacuous-direction-b-on-empty-scan",
            mechanism="scan root empty => zero leftover files, independent of generator correctness",
            claim_ids=["ARC-0012-C4"],
            evidence=[
                (A12E, '"live_direction_b_count"'),
                (A12E, '"live_direction_a_count"'),
            ],
        ),
        _rec(
            nid="sym.a2.stale-bytes-invisible-to-path-gate",
            typ="SYMPTOM",
            title="FM-STALE-BYTES: path-complete stale bytes are invisible to both directions",
            statement=(
                "A generated file at the mapped path with size>0 silences Direction A "
                "and B even when bytes came from an older generator. Path completeness "
                "is not freshness. Reviewer added this mode because the author's path "
                "list missed it."
            ),
            family_id=fam_a2_path,
            parent_id="mech.a2.vacuous-direction-b-on-empty-scan",
            mechanism="path presence plus size>0 is the whole signal; bytes and generator version are not compared",
            claim_ids=["ARC-0012-C5"],
            evidence=[
                (A12R, '"id": "FM-STALE-BYTES"'),
                (A12R, "Path completeness is not freshness"),
            ],
        ),
    ]


def resolve_records(repo: Path, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for rec in records:
        item = dict(rec)
        specs = item.pop("evidence_specs")
        item["evidence_anchors"] = [make_anchor(repo, rel, snip) for rel, snip in specs]
        out.append(item)
    return out


def input_inventory(repo: Path) -> dict[str, Any]:
    catalog = [
        {"path": p, "present": (repo / p).is_file()} for p, _ in CATALOG_INPUTS
    ]
    live = [
        A5E,
        A5P1,
        A5P2,
        A5S,
        A9L,
        A9E,
        A9M,
        A2D,
        GEN,
        REG,
        A16E,
        A16H,
        A14E,
        A12E,
        A12R,
    ]
    live_rows = [{"path": p, "present": (repo / p).is_file()} for p in live]
    missing = [r["path"] for r in catalog if not r["present"]]
    return {
        "catalog_inputs": catalog,
        "live_phase3_and_probe_inputs": live_rows,
        "absent_catalog_inputs": missing,
        "honesty": (
            "CLAIM-REGISTRY.json, Phase 11/12/13 bucket verdicts, and the A1 "
            "DESIGN/FAILURE-MODES/REFUTATION dossier files are not on this "
            "worktree. SYN-0001 synthesizes the live ARC-0005/0009/0010/0012/"
            "0014/0016 probe corpus that is on disk, and records the absent "
            "inputs rather than inventing them."
        ),
    }
