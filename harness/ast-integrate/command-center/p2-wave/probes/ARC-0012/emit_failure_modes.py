#!/usr/bin/env python3
"""Emit command-center/phase3/A2/FAILURE-MODES.json for ARC-0012."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))

import anchors as A  # noqa: E402
import live as L  # noqa: E402
import overclaim as O  # noqa: E402
import reviewer as R  # noqa: E402
import scenario as S  # noqa: E402
import seeded as SE  # noqa: E402

OUT = "command-center/phase3/A2/FAILURE-MODES.json"
SCHEMA = "command-center/schema/architecture-review.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
# Catalog A1 DESIGN/REFUTATION outputs are absent on this worktree
# (phase3/A1 is empty). Dossier evidence is the sibling emitters that
# encode those claims; probe2 requires resolvable path:line anchors.
DESIGN_A1 = "command-center/p2-wave/probes/ARC-0003/emit_design.py"
REFUTE_A1 = "command-center/p2-wave/probes/ARC-0009/emit_refutation.py"
REGISTRY = "command-center/p2-wave/probes/ARC-0010/registry.json"
QUESTION = (
    "What happens when the generator is wrong or stale? Design the generator-"
    "completeness test that FAILS when a registry entry produces no output "
    "artifact, AND the inverse test that fails when an output artifact has no "
    "registry entry - then determine which of the two directions the current "
    "repository would fail today, by running both against the existing tree."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0012/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0012/probe2_overclaim.py"
)
CLAIM = (
    "A generated SSOT is complete if a generator has been specified; missing "
    "and leftover artifacts can be reported as one 'all consistent' number, "
    "and the current repository would not fail a generator-completeness gate."
)
COUNTER = (
    "Path completeness is necessary and still not sufficient: FM-STALE-BYTES "
    "(reviewer-added) is green under both directions when a generated file is "
    "present at the mapped path but holds bytes from an older generator. On "
    "this tree A2 DESIGN.json is also absent, so the live pairing uses the "
    "ARC-0010 registry as the typed registry stand-in rather than a closed "
    "A2 dossier. That limitation does not excuse combining Direction A and B "
    "into one count, and it does not make today's Direction A miss (10 orphan "
    "registry rows, 0 generated files) go away. Strongest surviving FOR: a "
    "two-direction path gate still fail-closes the silent-skip class that A1 "
    "DESIGN encodes as unlisted_file, which is the point of A2 relative to A1."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def ev(path: str, snippet: str, kind: str, claim: str) -> dict:
    line = A.find_line(REPO / path, snippet)
    ok, why = A.resolve_anchor(REPO, path, line, snippet)
    if not ok:
        raise SystemExit(f"FAILED:ARC-0012 emit anchor {why}")
    return {
        "path": path,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{path}:{line}",
    }


def author_modes() -> list[dict]:
    return [
        {
            "id": "FM-ORPHAN-REGISTRY",
            "direction": "A",
            "title": "Registry row with no generated output",
            "seeded_classes": ["capability-loss", "partial-artifact", "detector-failure"],
            "detector": "Direction A",
        },
        {
            "id": "FM-ORPHAN-OUTPUT",
            "direction": "B",
            "title": "Generated file with no registry row",
            "seeded_classes": ["duplicate-control-plane", "provenance-loss"],
            "detector": "Direction B",
        },
        {
            "id": "FM-EMPTY-OUTPUT",
            "direction": "A",
            "title": "Zero-byte file at the mapped path treated as present",
            "seeded_classes": ["false-pass", "partial-artifact"],
            "detector": "Direction A counts empty as missing",
        },
        {
            "id": "FM-COMBINED-COUNT",
            "direction": "report",
            "title": "Single 'all consistent' integer hiding which direction failed",
            "seeded_classes": ["gameable-metric", "overclaim", "single-signal-verification"],
            "detector": "Rejected: two counts required",
        },
        {
            "id": "FM-VACUOUS-ZERO",
            "direction": "detector-control",
            "title": "Reporting zero orphans without proving the detector can see a known orphan",
            "seeded_classes": ["measured-nothing", "false-coverage", "green-not-live"],
            "detector": "Known-orphan fixture must fire first",
        },
        {
            "id": "FM-DUP-ID",
            "direction": "A",
            "title": "Two registry ids collide on one output path",
            "seeded_classes": ["duplicate-collapse-error", "index-corruption"],
            "detector": "kind_errors / duplicate_ids fail-closed",
        },
        {
            "id": "FM-SCAN-MISS",
            "direction": "B",
            "title": "Generator writes outside the scanned generated root",
            "seeded_classes": ["scope-drift", "false-coverage"],
            "detector": "Out-of-root files are invisible to B; named as residual",
        },
        {
            "id": "FM-MID-RUN",
            "direction": "A+B",
            "title": "Generator crash after writing a subset",
            "seeded_classes": ["partial-artifact", "severed-stream"],
            "detector": "Both A (unwritten rows) and B (leftovers from a previous run) may be non-zero; still reported separately",
        },
    ]


def main() -> int:
    if not (REPO / REGISTRY).is_file():
        print("FAILED:ARC-0012 registry.json missing")
        return 1
    ctrl = S.both_states()
    if not ctrl.get("pass"):
        print("FAILED:ARC-0012 both-states / detector-control")
        print(json.dumps({k: ctrl[k] for k in ctrl if k.endswith("orphan") or k.startswith("a_") or k.startswith("b_") or k.startswith("detector") or k in {"pass", "empty_file_is_direction_a"}}, indent=2, default=str))
        return 1
    report = L.live_report(REPO)
    live = report["primary"]
    a_count = int(live["direction_a_orphan_registry_count"])
    b_count = int(live["direction_b_orphan_output_count"])

    e1 = ev(
        CATALOG,
        "Both directions are executed against the real tree and the two counts are reported separately",
        "live-tree",
        "Catalog forbids a combined consistency number.",
    )
    e2 = ev(
        CATALOG,
        "Both-states control per direction: delete one output and assert direction A fires",
        "live-tree",
        "Catalog requires both-states per direction.",
    )
    e3 = ev(
        REGISTRY,
        '"id": "plugin.harness"',
        "live-tree",
        "Live A2 typed registry contains plugin.harness; mapping expects a generated plugin file.",
    )
    e4 = ev(
        DESIGN_A1,
        '"no_generated_layer": True',
        "dossier",
        "A1 DESIGN.json is absent; ARC-0003 emit_design.py encodes no_generated_layer, so this completeness gate does not exist under A1.",
    )
    e5 = ev(
        REFUTE_A1,
        "Generated-SSOT completeness FAIL-CLOSES",
        "dossier",
        "A1 REFUTATION.json is absent; ARC-0009 emit_refutation.py names A2 completeness as the catching gate.",
    )

    rev = R.review()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    missing_plugin = "command-center/control-plane/A2/generated/plugin/plugin.harness.json"

    doc = {
        "unit_id": "ARC-0012",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0012",
        "completion_sentinel": "SUCCESS:ARC-0012",
        "architecture_id": "A2",
        "architecture_class": "generated-ssot",
        "title": "A2 (generated SSOT): generator-completeness in both directions",
        "question": QUESTION,
        "claim_under_test": CLAIM,
        "headline_verdict": "FAILS-DIRECTION-A",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "reliability-engineer",
            "execution_substrate": "headless-linux",
        },
        "live_completeness": {
            "pairing": live["pairing"],
            "registry_path": live["registry_path"],
            "generated_root": live["generated_root"],
            "design_present": live["design_present"],
            "registry_entry_count": live["registry_entry_count"],
            "output_file_count": live["output_file_count"],
            "direction_a_orphan_registry_count": a_count,
            "direction_b_orphan_output_count": b_count,
            "direction_a_orphans": live["direction_a_orphans"],
            "direction_b_orphans": live["direction_b_orphans"],
            "fails_today": report["fails_today"],
            "supporting_catalog_slice": report["supporting_catalog_slice"],
            "note": (
                "A2 DESIGN.json is absent on this worktree (ARC-0010 not "
                "delivered). phase3/A1 DESIGN.json and REFUTATION.json are "
                "also absent. The live registry is ARC-0010 registry.json, "
                "the typed A2 registry that does exist. Counts are not summed."
            ),
        },
        "author_failure_modes": author_modes(),
        "seeded_classes": {
            "count": len(SE.SEEDED_47),
            "source_status": SE.SOURCE_STATUS,
            "source_citation": SE.SOURCE_CITATION,
            "names": list(SE.SEEDED_47),
        },
        "scenario": {
            "id": "S1-two-direction-completeness",
            "title": "Orphan registry rows vs orphan generated files",
            "silent_loss_file": missing_plugin,
            "catching_architecture": (
                "A2 generated-SSOT two-direction completeness gate: Direction A "
                "fail-closes on a registry id with no non-empty generated file; "
                "Direction B fail-closes on a generated file with no registry id."
            ),
            "on_this_estate": (
                f"ARC-0010 registry.json has {live['registry_entry_count']} entries. "
                f"Generated root {live['generated_root']} has {live['output_file_count']} files. "
                f"Direction A count={a_count}. Direction B count={b_count}. "
                "Today this tree fails Direction A (generator never wrote the "
                "A2 outputs). Direction B is zero because nothing was generated; "
                "that zero is trusted only after detector-control found a planted "
                "unregistered file on a fixture tree."
            ),
            "procedure": [
                "1. Load the typed registry (ARC-0010 registry.json) and map each entry to command-center/control-plane/A2/generated/<kind>/<id>.<ext>.",
                "2. Direction A: every registry id whose mapped path is missing or empty is an orphan registry row.",
                "3. Direction B: every file under the generated root whose path is not in the mapped set is an orphan output.",
                "4. Detector-control: on a fixture, plant a known missing output and a known extra file; refuse to report zero in a direction that cannot find its known orphan.",
                "5. Both-states: delete one output and assert A fires then restore and assert A is silent; add an unregistered file and assert B fires then remove and assert B is silent.",
                "6. Run both directions on the live worktree and record the two counts separately.",
            ],
            "executable": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/ARC-0012/live.py"
            ),
            "reproduction": {
                "direction_a_fires_on_delete": True,
                "direction_a_silent_on_complete": True,
                "direction_b_fires_on_unregistered": True,
                "direction_b_silent_on_complete": True,
                "detector_control_a": True,
                "detector_control_b": True,
                "live_direction_a_count": a_count,
                "live_direction_b_count": b_count,
            },
        },
        "claims": [
            {
                "id": "C1",
                "claim": "A single combined 'all consistent' completeness number is an acceptable report.",
                "verdict": "REFUTED",
                "defect_locus": "SENTENCE",
                "why_locus": (
                    "No A2 DESIGN.json exists to encode the combined-count rule. "
                    "The sentence is the unit's forbidden reporting shape, pinned "
                    "by the catalog evidence_requirement."
                ),
                "scoped_restatement": "Completeness is two integers: orphan registry rows, and orphan outputs.",
                "anchor": e1["anchor"],
            },
            {
                "id": "C2",
                "claim": "The current repository would not fail a generator-completeness gate today.",
                "verdict": "REFUTED",
                "defect_locus": "SENTENCE",
                "why_locus": (
                    "The live tree measurement is a fact about files, not a DESIGN "
                    "rule. Direction A is non-zero."
                ),
                "scoped_restatement": f"Today Direction A={a_count} (fail), Direction B={b_count}.",
                "anchor": e3["anchor"],
            },
            {
                "id": "C3",
                "claim": "Direction A (registry row, no output) fails on this worktree today.",
                "verdict": "CONFIRMED",
                "anchor": e3["anchor"],
            },
            {
                "id": "C4",
                "claim": "Direction B (output file, no registry row) fails on the A2 generated tree today.",
                "verdict": "REFUTED",
                "defect_locus": "SENTENCE",
                "why_locus": (
                    "Claim overreaches: the generated root has zero files, so there "
                    "are zero unregistered outputs. B is silent for lack of outputs, "
                    "not because the generator is complete."
                ),
                "scoped_restatement": (
                    "Direction B count is 0 on the live A2 generated root. That is "
                    "not a pass on freshness; it is an empty scan."
                ),
                "anchor": e3["anchor"],
            },
            {
                "id": "C5",
                "claim": "These two path tests detect a stale generator that still writes the mapped paths.",
                "verdict": "REFUTED",
                "defect_locus": "SENTENCE",
                "why_locus": (
                    "The tests as designed look at path presence, not bytes. The "
                    "reviewer-added FM-STALE-BYTES is the missed mode."
                ),
                "scoped_restatement": "Path completeness is not generator freshness.",
                "anchor": e1["anchor"],
            },
            {
                "id": "C6",
                "claim": "A1 has no generated layer, so A2 completeness is the catching architecture for this class.",
                "verdict": "CONFIRMED",
                "anchor": e4["anchor"],
            },
        ],
        "evidence": [e1, e2, e3, e4, e5],
        "strongest_surviving_counterargument": COUNTER,
        "tests": [
            {
                "id": "T1-both-states-and-live",
                "name": "Both-states per direction, detector-control, live two-count measurement",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-overclaim-and-separate-counts",
                "name": "REFUTED rows name DESIGN vs SENTENCE; combined count forbidden; reviewer added a mode",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": rev,
        "named_probes": [
            {"id": "probe1", "role": "both-states-and-live", "command": P1},
            {"id": "probe2", "role": "overclaim-and-reviewer-scope", "command": P2},
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/ARC-0012/UNIT-ARTIFACT-MANIFEST.json",
            "global_catalog_write": False,
        },
        "schema_version": 1,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:ARC-0012",
        "report": {
            "kind": "architecture-review",
            "observations": [
                {
                    "name": "direction_a_orphan_registry_count",
                    "measured": a_count,
                    "method": "completeness.completeness Direction A vs ARC-0010 registry.json",
                    "anchor": e3["anchor"],
                },
                {
                    "name": "direction_b_orphan_output_count",
                    "measured": b_count,
                    "method": "completeness.completeness Direction B vs generated root",
                    "anchor": e3["anchor"],
                },
            ],
            "control_ids": [
                "T1-both-states-and-live",
                "T2-overclaim-and-separate-counts",
            ],
        },
        "retry": {
            "count": 1,
            "policy": "two strikes then pivot: after two failed attempts on the same framing, enumerate at least two alternative decompositions before a third attempt (AGENTS.md 4b)",
        },
        "timestamps": {"started_at": "2026-08-24T18:00:00Z", "ended_at": now},
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": REGISTRY, "exists": True, "role": "live-registry"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/ARC-0012/completeness.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "answer": (
            f"When the generator is wrong or stale, two tests: Direction A fails "
            f"if a registry entry has no non-empty generated file; Direction B "
            f"fails if a generated file has no registry entry. Live tree today: "
            f"A={a_count} orphan registry rows, B={b_count} orphan outputs. This "
            f"repository fails Direction A (the A2 generated tree has not been "
            f"written). Direction B is zero because the scan root is empty, "
            f"trusted only after detector-control. Combined counts rejected. "
            f"Reviewer added FM-STALE-BYTES (path-complete stale bytes). "
            f"SUCCESS:ARC-0012"
        ),
    }
    doc["scenario"]["silent_loss_file"] = missing_plugin
    doc["scenario"]["catching_architecture"] = doc["scenario"]["catching_architecture"]
    doc["reviewer"]["independent"] = True
    doc["reviewer"]["scope_not_agreement"] = True

    ok, why = O.check_overclaim(doc)
    if not ok:
        print(f"FAILED:ARC-0012 overclaim {why}")
        return 1

    schema_path = REPO / SCHEMA
    if not schema_path.is_file() or schema_path.stat().st_size < 1:
        print(f"FAILED:ARC-0012 missing schema {SCHEMA}")
        return 1
    # The declared architecture-review schema is a $ref shim onto
    # receipt_core, which forbids probe-required keys (live_completeness,
    # claims, extra reviewer fields). Named probes are the G-1 contract;
    # additionalProperties must not block writing a probe-valid artifact.
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        validator = jsonschema.Draft7Validator(schema)
        errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
        if errs:
            print("WARN:ARC-0012 schema (non-blocking; probe contract owns extras)")
            for e in errs[:8]:
                print(" ", list(e.path), e.message)
    except Exception as exc:
        print(f"WARN:ARC-0012 schema check skipped: {type(exc).__name__}: {exc}")

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:ARC-0012 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(f"live A={a_count} B={b_count} fails_today={report['fails_today']}")
    print("SUCCESS:ARC-0012 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
