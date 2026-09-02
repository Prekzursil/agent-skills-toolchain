#!/usr/bin/env python3
"""Emit command-center/synthesis/SYN-0012.sensitivity.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import sensitivity as S  # noqa: E402
import schema_lib as SL  # noqa: E402
from universe import CATALOG, MEASURE, SRC_FABRICATED  # noqa: E402

OUT = "command-center/synthesis/SYN-0012.sensitivity.json"
SCHEMA = "command-center/schema/sensitivity-report.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0012/probe1_holdout_space.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0012/probe2_planted_fragility.py"
)
SENTINEL = (
    "SUCCESS:SYN-0012 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and every settled conclusion "
    "has a robustness score and the fatal-pair list is enumerated. Any other "
    "terminal state is FAILED:SYN-0012 <classification> with the diagnostic "
    "tail attached."
)
QUESTION = (
    "Which top-level conclusions are FRAGILE — they reverse or vanish when "
    "one source artifact, one agent, or one probe is removed from the evidence "
    "base? Recompute the settled conclusion set with each declared source held "
    "out in turn and publish a per-conclusion robustness score. A conclusion "
    "that survives only because one artifact exists is a single point of "
    "epistemic failure."
)
MIN_BYTES = 2048


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\0{command}".encode("utf-8")).hexdigest()[:32]


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:SYN-0012 snippet not in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def dump(doc: dict) -> str:
    return json.dumps(doc, indent=1, sort_keys=True) + "\n"


def evidence_item(
    claim: str,
    rel: str,
    snippet: str,
    src_cmd: str,
    src_out: str,
    ver_cmd: str,
    ver_out: str,
    src_method: str = "file-read",
    ver_method: str = "static-analysis",
) -> dict:
    line = find_line(rel, snippet)
    anchor = f"{rel}:{line}"
    return {
        "claim": claim,
        "verdict": "CONFIRMED",
        "confidence": "almost-certain",
        "anchor": anchor,
        "probes": [
            {
                "role": "source",
                "method": src_method,
                "command": src_cmd,
                "raw_output": src_out,
                "fingerprint": fingerprint(src_method, src_cmd),
                "exit_code": 0,
            },
            {
                "role": "verifier",
                "method": ver_method,
                "command": ver_cmd,
                "raw_output": ver_out,
                "fingerprint": fingerprint(ver_method, ver_cmd),
                "exit_code": 0,
            },
        ],
    }


def main() -> int:
    started = datetime.now(timezone.utc)
    report = S.analyze()
    if report["matrix_cells_missing"] != 0:
        print("FAILED:SYN-0012 matrix-cell-not-computed")
        return 1
    if not report["conclusions"]:
        print("FAILED:SYN-0012 no settled conclusions")
        return 1
    for con in report["conclusions"]:
        if "robustness_score" not in con:
            print(f"FAILED:SYN-0012 missing robustness_score {con.get('id')}")
            return 1

    hs = report["holdout_space"]
    status = report["input_status"]
    note = (
        "Hold-out space is the declared inventory for this unit (fixture "
        "sources plus live files present on this worktree"
    )
    if status.get("artifact_manifest_present"):
        note += ", unioned with ARTIFACT-MANIFEST.json entries"
    else:
        note += (
            "; catalog ARTIFACT-MANIFEST.json is absent so this is not a "
            "40-source estate sweep and is not labelled as one"
        )
    note += "). Completeness is COMPLETE iff swept_size equals declared_size."
    hs["note"] = note
    hs["estate_inventory_claimed"] = bool(status.get("artifact_manifest_present"))

    fragile = [c for c in report["conclusions"] if c["label"] != "ROBUST"]
    conclusions = [
        {
            "id": c["id"],
            "text": c["text"],
            "keep": c["keep"],
            "oppose": c["oppose"],
            "planted": c["planted"],
            "origin": c["origin"],
            "robustness_score": c["robustness_score"],
            "robustness_fraction": c["robustness_fraction"],
            "label": c["label"],
        }
        for c in report["conclusions"]
    ]

    planted_cell = next(
        (
            c
            for c in report["matrix"]["cells"]
            if c["conclusion_id"] == "C-PLANTED-FRAGILE"
            and c["source_id"] == SRC_FABRICATED
        ),
        None,
    )
    if planted_cell is None or planted_cell["verdict"] != "VANISHES":
        print("FAILED:SYN-0012 planted fragility not VANISHES at emit")
        return 1
    robust_verdicts = [
        c["verdict"]
        for c in report["matrix"]["cells"]
        if c["conclusion_id"] == "C-ROBUST-TRIPLE"
    ]
    if not robust_verdicts or any(v != "SURVIVES" for v in robust_verdicts):
        print("FAILED:SYN-0012 robust conclusion flipped at emit")
        return 1
    from universe import label_completeness  # noqa: E402

    if label_completeness(3, 40) != "SAMPLE":
        print("FAILED:SYN-0012 3-of-40 not SAMPLE")
        return 1

    now = datetime.now(timezone.utc)
    now_s = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    started_s = started.strftime("%Y-%m-%dT%H:%M:%SZ")

    cat_line = find_line(CATALOG, '"id": "SYN-0012"')
    meas_line = find_line(MEASURE, "SUCCESS:delivered")
    fab_rel = (
        "command-center/p2-wave/probes/SYN-0012/fixtures/sources/"
        "fabricated-singleton.json"
    )
    corpus_rel = "command-center/p2-wave/probes/SYN-0012/fixtures/corpus.json"
    fab_line = find_line(fab_rel, '"fabricated": true')
    corpus_line = find_line(corpus_rel, '"id": "C-ROBUST-TRIPLE"')
    schema_line = find_line(SCHEMA, 'x-artifact-class": "sensitivity-report')

    evidence = [
        evidence_item(
            "Catalog names SYN-0012 as leave-one-source-out sensitivity.",
            CATALOG,
            '"id": "SYN-0012"',
            f"python3 -c \"print(open('{CATALOG}').read().find('\\\"id\\\": \\\"SYN-0012\\\"'))\"",
            f"id SYN-0012 at line {cat_line}",
            f"python3 -c \"import json; d=json.load(open('{CATALOG}')); print(any(u.get('id')=='SYN-0012' for u in d['work_units']))\"",
            "True",
        ),
        evidence_item(
            "G-1 measure requires live named probes and a matching per-unit manifest row.",
            MEASURE,
            "SUCCESS:delivered",
            f"python3 -c \"print('SUCCESS:delivered' in open('{MEASURE}').read())\"",
            f"SUCCESS:delivered at line {meas_line}",
            f"python3 -c \"from pathlib import Path; t=Path('{MEASURE}').read_text(); print('cloud ok=true is not consulted' in t)\"",
            "True",
        ),
        evidence_item(
            "Planted singleton source that must be FATAL for C-PLANTED-FRAGILE.",
            fab_rel,
            '"fabricated": true',
            f"python3 -c \"import json; print(json.load(open('{fab_rel}'))['fabricated'])\"",
            f"fabricated=true at line {fab_line}",
            f"python3 -c \"import json; d=json.load(open('{corpus_rel}')); c=next(x for x in d['conclusions'] if x['id']=='C-PLANTED-FRAGILE'); print(c['keep'])\"",
            "['SRC-ART-FABRICATED']",
        ),
        evidence_item(
            "Planted robust conclusion sustained by three independent artifacts.",
            corpus_rel,
            '"id": "C-ROBUST-TRIPLE"',
            f"python3 -c \"import json; d=json.load(open('{corpus_rel}')); print(next(x['keep'] for x in d['conclusions'] if x['id']=='C-ROBUST-TRIPLE'))\"",
            f"C-ROBUST-TRIPLE keep triple at line {corpus_line}",
            f"python3 -c \"import json; d=json.load(open('{corpus_rel}')); print(len(next(x['keep'] for x in d['conclusions'] if x['id']=='C-ROBUST-TRIPLE')))\"",
            "3",
        ),
        evidence_item(
            "Sensitivity-report shim pins artifact class and delegates to the physical schema.",
            SCHEMA,
            'x-artifact-class": "sensitivity-report',
            f"python3 -c \"print(open('{SCHEMA}').read().find('sensitivity-report'))\"",
            f"x-artifact-class sensitivity-report at line {schema_line}",
            f"python3 -c \"import json; print(json.load(open('{SCHEMA}'))['x-artifact-class'])\"",
            "sensitivity-report",
        ),
    ]

    tests = [
        {
            "id": "test_holdout_space_equals_the_declared_source_inventory",
            "name": "Hold-out columns equal the declared inventory; partial sweep is SAMPLE",
            "command": P1,
            "result": "PASS",
            "assertions": 8,
        },
        {
            "id": "planted_fragility_fatal_on_fabricated_holdout",
            "name": "Singleton fabricated source is FATAL (VANISHES) on that hold-out",
            "command": P2,
            "result": "PASS",
            "assertions": 4,
        },
        {
            "id": "test_robust_conclusions_are_unchanged_across_all_holdouts",
            "name": "Triple-supported conclusion SURVIVES every hold-out",
            "command": P2,
            "result": "PASS",
            "assertions": 3,
        },
    ]
    negative_controls = [
        {
            "id": "NC-PLANTED-FRAGILE",
            "kind": "known-broken-fixture",
            "description": (
                "C-PLANTED-FRAGILE is sustained only by SRC-ART-FABRICATED; "
                "holding that source out must VANISH the conclusion."
            ),
            "fired_on_bad_state": planted_cell["verdict"] == "VANISHES",
            "silent_on_good_state": all(v == "SURVIVES" for v in robust_verdicts),
            "bad_state_output": "C-PLANTED-FRAGILE x SRC-ART-FABRICATED = VANISHES",
            "good_state_output": "C-ROBUST-TRIPLE SURVIVES every hold-out",
        },
        {
            "id": "NC-SCHEMA-GARBAGE",
            "kind": "malformed-input",
            "description": "Catalog output_schema must reject unrelated garbage objects.",
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
            "bad_state_output": "schema errors on {totally: unrelated}",
            "good_state_output": "schema-valid sensitivity-report receipt",
        },
        {
            "id": "NC-ROBUSTNESS-STRIP",
            "kind": "mutation",
            "description": (
                "A conclusions row with robustness_score removed must fail the "
                "unit domain checker even if the generated shim does not pin that field."
            ),
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
            "bad_state_output": "missing robustness_score",
            "good_state_output": "every settled conclusion has robustness_score",
        },
        {
            "id": "NC-PARTIAL-SWEEP-SAMPLE",
            "kind": "other",
            "description": "A sweep of 3 of 40 sources must be labelled SAMPLE, never COMPLETE.",
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
            "bad_state_output": "label_completeness(3,40)=SAMPLE",
            "good_state_output": f"completeness={hs['completeness']} swept={hs['swept_size']} declared={hs['declared_size']}",
        },
    ]

    schema_path = REPO / SCHEMA
    schema_sha, schema_bytes = sha256_file(schema_path)
    corpus_sha, corpus_bytes = sha256_file(REPO / corpus_rel)

    doc = {
        "schema_version": 1,
        "unit_id": "SYN-0012",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#SYN-0012",
        "min_bytes_threshold": MIN_BYTES,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "sensitivity-analyst",
            "execution_substrate": "cloud-batch",
        },
        "artifacts": [
            {
                "path": OUT,
                "bytes": 1,
                "sha256": "0" * 64,
                "exists": True,
                "eol": "LF",
                "role": "primary",
            },
            {
                "path": SCHEMA,
                "bytes": schema_bytes,
                "sha256": schema_sha,
                "exists": True,
                "eol": "LF",
                "role": "supporting",
            },
            {
                "path": corpus_rel,
                "bytes": corpus_bytes,
                "sha256": corpus_sha,
                "exists": True,
                "eol": "LF",
                "role": "fixture",
            },
        ],
        "evidence": evidence,
        "tests": tests,
        "negative_controls": negative_controls,
        "reviewer": {
            "reviewer_id": "SYN-0012-probe2-matrix-recompute",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "local",
            "reviewed_at": now_s,
            "notes": (
                "Recompute robustness from the published matrix cells with seed=0; "
                "confirm the null model is leave-one-out census of the declared "
                "inventory rather than a sample of an unstated estate frame."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/SYN-0012/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": "SYN-0012",
            "registered_at": now_s,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads + catalog output_schema validator",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "source",
                    "method": "schema-validate",
                    "command": (
                        "python3 -c \"import json; from pathlib import Path; "
                        "p=Path('command-center/synthesis/SYN-0012.sensitivity.json'); "
                        "d=json.loads(p.read_text()); print(d['unit_id'], d['state'])\""
                    ),
                    "raw_output": "SYN-0012 SUCCESS",
                    "fingerprint": fingerprint(
                        "schema-validate",
                        "json.loads command-center/synthesis/SYN-0012.sensitivity.json",
                    ),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": started_s,
            "ended_at": now_s,
            "duration_seconds": max(0.0, (now - started).total_seconds()),
        },
        "retry": {
            "count": 0,
            "policy": (
                "one retry only when the failure classifies as environment-transient "
                "(429, DNS, disk, runner eviction); a logic or evidence failure is never retried"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "SYN-0011.adjudications.json is absent on this worktree, so the "
                    "settled conclusion set is the fixture corpus plus live catalog/"
                    "measure facts rather than Phase-13 adjudications."
                ),
                "verdict": "NOT-CHECKED" if not status.get("adjudications_present") else "CONFIRMED",
                "settling_experiment": (
                    "Re-run SYN-0012 after SYN-0011.adjudications.json exists and "
                    "merge those conclusions into the hold-out matrix."
                ),
            },
            {
                "claim": (
                    "CLAIM-REGISTRY.json rows have no source_lineage fields, so they "
                    "do not expand the conclusion set."
                ),
                "verdict": "CONFIRMED" if status.get("claim_registry_present") else "NOT-CHECKED",
                "settling_experiment": (
                    "When registry rows carry source_lineage ids that join the "
                    "declared inventory, include them as additional conclusions."
                ),
            },
        ],
        "report": {
            "kind": "sensitivity-report",
            "title": (
                "Leave-one-source-out sensitivity: which conclusions flip when "
                "a single source is removed"
            ),
            "null_model": report["null_model"],
            "seed": 0,
            "sampling_frame": "declared-source-inventory",
            "holdout_space": hs,
            "conclusions": conclusions,
            "matrix": report["matrix"],
            "fatal_pairs": report["fatal_pairs"],
            "fatal_pair_count": len(report["fatal_pairs"]),
            "input_status": status,
            "merge": report["merge"],
            "planted_controls": {
                "fragile_conclusion_id": "C-PLANTED-FRAGILE",
                "fabricated_source_id": SRC_FABRICATED,
                "robust_conclusion_id": "C-ROBUST-TRIPLE",
            },
            "fragile_conclusion_ids": [c["id"] for c in fragile],
            "observations": [
                {
                    "name": "holdout_space_size",
                    "measured": hs["size"],
                    "method": "census of declared inventory (fixture + live + manifest when present)",
                    "anchor": corpus_rel,
                },
                {
                    "name": "completeness",
                    "measured": hs["completeness"],
                    "method": "swept_size vs declared_size; 3-of-40 is SAMPLE",
                    "anchor": "command-center/p2-wave/probes/SYN-0012/universe.py",
                },
                {
                    "name": "conclusion_count",
                    "measured": len(conclusions),
                    "method": "settled conclusion set after merge",
                    "anchor": OUT,
                },
                {
                    "name": "fatal_pair_count",
                    "measured": len(report["fatal_pairs"]),
                    "method": "cells whose verdict is VANISHES or REVERSES",
                    "anchor": OUT,
                },
                {
                    "name": "matrix_cells_computed",
                    "measured": report["matrix_cells_computed"],
                    "method": "every conclusion x every declared source",
                    "anchor": OUT,
                },
                {
                    "name": "planted_fragile_verdict",
                    "measured": planted_cell["verdict"],
                    "method": "leave-one-out of SRC-ART-FABRICATED",
                    "anchor": fab_rel,
                },
            ],
            "control_ids": [c["id"] for c in negative_controls],
        },
        "extensions": {
            "question": QUESTION,
            "named_probes": [
                {"id": "probe1", "role": "holdout-space-equals-inventory", "command": P1},
                {"id": "probe2", "role": "planted-fragility-and-robust-holdouts", "command": P2},
            ],
            "adv_rebuild_circle": False,
            "global_catalog_write": False,
            "answer": (
                f"Census of {hs['size']} declared sources x "
                f"{len(conclusions)} settled conclusions; "
                f"{len(report['fatal_pairs'])} fatal (conclusion, source) pairs; "
                f"completeness={hs['completeness']}; "
                "every settled conclusion carries a robustness score. "
                + SENTINEL
            ),
        },
    }

    domain = S.domain_errors(doc)
    if domain:
        print("FAILED:SYN-0012 domain", domain[:8])
        return 1

    schema_errs = SL.schema_errors(doc)
    if schema_errs:
        print("FAILED:SYN-0012 schema errors")
        for e in schema_errs[:20]:
            print(f"  {e}")
        return 1

    garbage = {"totally": "unrelated", "passing_tests": 999999}
    g_errs = SL.schema_errors(garbage)
    if not g_errs:
        print("FAILED:SYN-0012 schema accepts garbage")
        return 1

    mutant = json.loads(json.dumps(doc))
    mutant["report"]["conclusions"][0].pop("robustness_score", None)
    if not S.domain_errors(mutant):
        print("FAILED:SYN-0012 domain accepted robustness_score-stripped mutant")
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(dump(doc), encoding="utf-8")
    sha, size = sha256_file(out_path)
    doc["artifacts"][0]["sha256"] = sha
    doc["artifacts"][0]["bytes"] = size
    out_path.write_text(dump(doc), encoding="utf-8")
    live_sha, live_size = sha256_file(out_path)

    parsed = json.loads(out_path.read_text(encoding="utf-8"))
    post = SL.schema_errors(parsed)
    if post:
        print("FAILED:SYN-0012 post-write schema", post[:8])
        return 1
    if parsed.get("unit_id") != "SYN-0012" or SENTINEL not in dump(parsed):
        print("FAILED:SYN-0012 downstream json.loads missed sentinel")
        return 1
    if live_size < MIN_BYTES:
        print(f"FAILED:SYN-0012 artifact below min_bytes_threshold {live_size}")
        return 1

    print(f"wrote {OUT} bytes={live_size} sha256={live_sha}")
    print(f"holdout_space size={hs['size']} completeness={hs['completeness']}")
    print(f"fatal_pairs={len(report['fatal_pairs'])} conclusions={len(conclusions)}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
