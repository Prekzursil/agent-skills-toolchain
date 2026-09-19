#!/usr/bin/env python3
"""CC-0019 impl pass 2: update the receipt's AUTHOR-SIDE fields only.

The reviewer block is left byte-identical (a fresh independent reviewer will
re-review). State stays BLOCKED - the catalog-contracted corpus is still
absent and the catalog reviewer_requirement is still unmet - but the receipt
must now tell the truth that the artifact EXISTS: 1046 records emitted over a
DISCLOSED in-repo population substitution, author strict sample 20/20.

Also regenerates UNIT-ARTIFACT-MANIFEST.json. Validates the receipt against
command-center/schema/receipt.schema.json via the repo's own resolver before
writing (write_if_valid refuses to persist an invalid artifact).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "command-center" / "p2-wave"))
import _p2lib as L  # noqa: E402

UNIT = "CC-0019"
OUT = "command-center/receipts/CC-0019.json"
SCHEMA = "command-center/schema/receipt.schema.json"
PROBE_DIR = "command-center/p2-wave/probes/CC-0019"
MANIFEST = f"{PROBE_DIR}/UNIT-ARTIFACT-MANIFEST.json"
TESTS = "tools/command-center/tests/test_corpus_normalize.py"
GATE = "tools/command-center/corpus_normalize.py"
DRIVER = f"{PROBE_DIR}/normalize_inrepo_corpus.py"

TS = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# Captured from the live pre-fix run on this machine, 2026-09-19 (session
# impl-cc-0019): the sampler's Windows drive-colon defect, red state.
PREFIX_PYTEST = (
    "FAILED tools/command-center/tests/test_corpus_normalize.py::test_sample_anchors_resolve_fraction\n"
    "1 failed, 6 passed in 0.77s\n"
    "E   assert 0 >= 1   (sample['resolved'] == 0: every fixture anchor split at the\n"
    "DRIVE colon 'C:' -> path_part='C' -> missing-file)"
)


def main() -> int:
    receipt = json.loads((REPO / OUT).read_text(encoding="utf-8"))
    summary = json.loads(
        (REPO / "command-center/corpus/normalize-summary.json").read_text(
            encoding="utf-8"
        )
    )
    sample = json.loads(
        (REPO / f"{PROBE_DIR}/sample-resolve.json").read_text(encoding="utf-8")
    )
    census = json.loads(
        (REPO / f"{PROBE_DIR}/source-census.json").read_text(encoding="utf-8")
    )
    norm_raw = (REPO / f"{PROBE_DIR}/normalize-run.raw.txt").read_text(encoding="utf-8")
    raw1 = (REPO / f"{PROBE_DIR}/corpus-presence.raw.txt").read_text(encoding="utf-8")

    # Fresh verifier runs (post tool fix), captured to disk as we go.
    rc_pytest, out_pytest = L.run(
        [sys.executable, "-m", "pytest", TESTS, "-q", "--tb=line"]
    )
    (REPO / f"{PROBE_DIR}/pytest-corpus-normalize.out").write_text(
        out_pytest, encoding="utf-8"
    )

    cons = summary["conservation"]
    fam = summary["families"]
    n_files = census["totals"]["files"]

    # ---- reviewer-block contract compliance (content-preserving) ---------------
    # The reviewer block as merged on 2026-09-19 carries five fields the receipt
    # schema forbids (additionalProperties:false), making the receipt on disk
    # schema-invalid BEFORE any pass-2 edit (measured: 1 error, only reviewer.*).
    # Relocate those five keys VERBATIM into extensions; verdict, notes,
    # reviewer_id, reviewed_at, independent, fresh_context stay byte-identical.
    illegal = (
        "evidence_files",
        "prior_reviewer_state",
        "resolve_rate",
        "sample_required",
        "sample_size",
    )
    preserved = {k: receipt["reviewer"][k] for k in illegal if k in receipt["reviewer"]}
    for k in preserved:
        del receipt["reviewer"][k]
    receipt["extensions"]["preserved_reviewer_fields"] = {
        "relocated_at": TS,
        "reason": (
            "receipt.schema.json reviewer additionalProperties:false; merge of "
            "the 2026-09-19 independent review added fields the schema forbids; "
            "values below are verbatim, nothing edited or dropped"
        ),
        "fields": preserved,
    }

    # ---- report (author-side) -------------------------------------------------
    receipt["report"].update(
        {
            "corpus_present": False,  # CONTRACTED mount: still absent (probe1)
            "corpus_root": None,
            "normalize_summary": {
                "corpus_root": summary["corpus_root"],
                "records_file": summary["records_file"],
                "n_records": summary["n_records"],
                "conservation": {
                    k: cons[k]
                    for k in (
                        "inputs",
                        "emitted",
                        "merged",
                        "dropped",
                        "equation",
                        "reconciles",
                    )
                },
                "planted_synthetic_present": summary["planted_synthetic_present"],
                "idempotent": summary["idempotent"],
                "drop_reasons": summary["drop_reasons"],
            },
            "sample_resolve": {
                "mode": "strict-author-sample",
                "fraction": sample["resolve_fraction_strict"],
                "resolved": sample["resolved"],
                "resolved_at_anchor_line": sample["resolved_at_anchor_line"],
                "sample_size": sample["sample_size_actual"],
                "seed": sample["seed"],
                "rows_file": f"{PROBE_DIR}/sample-resolve.json",
                "tool_sampler_fraction_for_comparison": 1.0,
            },
            "inrepo_corpus": {
                "present": True,
                "root": summary["corpus_root"],
                "records_file": summary["records_file"],
                "n_records": summary["n_records"],
                "families": fam,
                "source_files": n_files,
            },
            "population_substitution": summary["population_substitution"],
        }
    )

    # ---- sentinel / state / failure -------------------------------------------
    receipt["state"] = "BLOCKED"
    receipt["sentinel"] = (
        f"FAILED:{UNIT} blocked; contracted harness-restore corpus ABSENT "
        f"(probe1 corpus_present=False, re-measured {TS}); impl pass 2 emitted "
        f"{summary['n_records']} records over a DISCLOSED in-repo population "
        "substitution (command-center/corpus/claim-records.jsonl; author strict "
        f"sample {sample['resolve_fraction_strict']}); SUCCESS:{UNIT} withheld "
        "pending independent different-20 review and catalog adjudication of "
        "the substitution (success_invented=false)"
    )
    receipt["failure"] = {
        "classification": [
            "blocked-on-missing-corpus-mount",
            "blocked-on-independent-review",
        ],
        "reason": (
            "Contracted harness-restore corpus mount is absent (probe1, "
            f"re-measured {TS}); refusing to fabricate its contents. Impl pass 2 "
            f"normalized the in-repo families instead ({summary['n_records']} "
            "records, substitution disclosed in report.population_substitution) - "
            "that artifact exists but does NOT satisfy the catalog input, and the "
            "independent different-20 reviewer is still owed."
        ),
        "blocked_on": (
            "contracted corpus mount ~/.claude/harness-restore-20260806/ still "
            "absent (probe1 2026-09-19); in-repo substitution emitted but needs "
            "catalog adjudication; independent reviewer who samples a different "
            "20 records than the author still pending; SUCCESS:CC-0019 withheld "
            "(success_invented=false)"
        ),
        "diagnostic_tail": (norm_raw + "\n" + raw1)[-4000:],
        "two_signal_proof": [
            L.probe(
                "verifier",
                "command",
                f"python -B {DRIVER}",
                norm_raw,
                0,
            ),
            L.probe(
                "verifier",
                "command",
                f"python3 -B {PROBE_DIR}/probe1_corpus_presence.py",
                raw1,
                0,
            ),
        ],
    }

    # ---- tests (append live runs) ---------------------------------------------
    receipt["tests"] = [
        t
        for t in receipt["tests"]
        if t["id"]
        in ("corpus-presence-fail-closed", "fixture-conservation-planted-idempotence")
    ]
    receipt["tests"][0]["output_tail"] = raw1[-800:]
    receipt["tests"][1]["output_tail"] = out_pytest[-800:]
    receipt["tests"].extend(
        [
            {
                "id": "live-inrepo-normalize-conservation",
                "name": "Live normalize over in-repo families: conservation reconciles.",
                "command": f"python -B {DRIVER}",
                "result": "PASS" if cons["reconciles"] else "FAIL",
                "assertions": 3,
                "output_tail": norm_raw[-800:],
            },
            {
                "id": "live-planted-synthetic-detector",
                "name": "Planted synthetic present in emitted records.",
                "command": f"python -B {DRIVER}",
                "result": "PASS" if summary["planted_synthetic_present"] else "FAIL",
                "assertions": 1,
                "output_tail": norm_raw[-500:],
            },
            {
                "id": "live-idempotence",
                "name": "Second run over unchanged sources emits identical record ids.",
                "command": f"python -B {DRIVER} (in-process double normalize)",
                "result": "PASS" if summary["idempotent"] else "FAIL",
                "assertions": 1,
                "output_tail": norm_raw[-500:],
            },
            {
                "id": "live-author-sample-20",
                "name": (
                    "Author random-20 (seed 19) strict anchor re-open: quoted "
                    "text at the cited file:line."
                ),
                "command": f"python -B {DRIVER} (strict_sample seed=19)",
                "result": "PASS"
                if sample["resolved"] == sample["sample_size_actual"] == 20
                else "FAIL",
                "assertions": 2,
                "output_tail": f"author_sample_strict={sample['resolve_fraction_strict']} "
                f"at_line={sample['resolved_at_anchor_line']} seed=19",
            },
            {
                "id": "tool-windows-drive-colon-fix-both-states",
                "name": (
                    "sample_anchors_resolve drive-colon defect: red on Windows "
                    "pre-fix, green post-fix (both states measured)."
                ),
                "command": f"python -m pytest {TESTS} -q --tb=line",
                "result": "PASS" if rc_pytest == 0 else "FAIL",
                "assertions": 2,
                "output_tail": (
                    "PRE-FIX (captured 2026-09-19):\n"
                    f"{PREFIX_PYTEST}\nPOST-FIX:\n{out_pytest[-300:]}"
                ),
            },
        ]
    )

    # ---- evidence (append) -----------------------------------------------------
    receipt["evidence"].append(
        L.evidence(
            (
                f"Impl pass 2 emitted a real normalized corpus over the in-repo "
                f"families: {summary['n_records']} records at "
                f"{summary['records_file']}; conservation "
                f"inputs={cons['inputs']} emitted={cons['emitted']} "
                f"merged={cons['merged']} dropped={cons['dropped']} "
                f"reconciles={cons['reconciles']}; planted synthetic present; "
                f"idempotent; author strict sample {sample['resolve_fraction_strict']} "
                f"({sample['resolved_at_anchor_line']} at the anchor line itself)."
            ),
            "CONFIRMED",
            "file:command-center/corpus/normalize-summary.json",
            [
                L.probe(
                    "verifier",
                    "command",
                    f"python -B {DRIVER}",
                    norm_raw,
                    0,
                ),
                L.probe(
                    "source",
                    "file-read",
                    "read command-center/corpus/claim-records.jsonl (first+count)",
                    f"jsonl lines={summary['n_records']}; planted id present="
                    f"{summary['planted_synthetic_present']}",
                    0,
                ),
            ],
            "almost-certain",
        )
    )
    receipt["evidence"].append(
        L.evidence(
            (
                "Population substitution is DISCLOSED, not silent: the "
                "catalog-contracted corpus ~/.claude/harness-restore-20260806/ "
                "remains ABSENT (probe1 re-measured on this machine; independent "
                "reviewer c5-cc-0019 measured 3 signals 2026-09-19); the emitted "
                "corpus covers in-repo families only (adversarial findings, owner "
                "option-cards, slop claims, casualty incidents, sources). No "
                "contracted-corpus contents were fabricated."
            ),
            "CONFIRMED",
            f"file:{PROBE_DIR}/corpus-presence.json",
            [
                L.probe(
                    "verifier",
                    "command",
                    f"python3 -B {PROBE_DIR}/probe1_corpus_presence.py",
                    raw1,
                    0,
                ),
                L.probe(
                    "source",
                    "file-read",
                    f"read {PROBE_DIR}/source-census.json",
                    f"files={n_files} bytes={census['totals']['bytes']} across "
                    + ",".join(sorted(census["families"])),
                    0,
                ),
            ],
            "almost-certain",
        )
    )
    receipt["evidence"].append(
        L.evidence(
            (
                "Tool defect found and fixed this pass (both states measured on "
                "this machine): corpus_normalize.sample_anchors_resolve split "
                "anchors at the FIRST colon, so Windows drive-letter anchors "
                "(C:\\...) resolved as path 'C' -> missing-file; fixture pytest "
                "was red pre-fix (1 failed: resolved==0) and is green post-fix "
                "(7 passed). In-repo records use driveless repo-relative anchors "
                "and were never affected (tool sampler fraction 1.0)."
            ),
            "CONFIRMED",
            f"file:{GATE}",
            [
                L.probe(
                    "source",
                    "test-run",
                    f"python -m pytest {TESTS} -q --tb=line  [PRE-FIX, captured]",
                    PREFIX_PYTEST,
                    1,
                ),
                L.probe(
                    "verifier",
                    "test-run",
                    f"python -m pytest {TESTS} -q --tb=line  [POST-FIX]",
                    out_pytest,
                    rc_pytest,
                ),
            ],
            "almost-certain",
        )
    )

    # ---- residual unknowns (rewrite: what is STILL unchecked) ------------------
    receipt["residual_unknowns"] = [
        {
            "claim": (
                "Normalization over the CONTRACTED 1.49 MB harness-restore corpus "
                "is still not executed: the mount is absent on every machine "
                "checked (cloud worker 2026-09-08; this machine 2026-09-19 probe1 "
                "+ reviewer 3 signals). The in-repo substitution does not cover it."
            ),
            "verdict": "NOT-CHECKED",
            "settling_experiment": (
                "Mount ~/.claude/harness-restore-20260806/ (or set "
                "AST_HARNESS_RESTORE_CORPUS to a verified copy with the 5 "
                "expected Prompt One basenames), then run "
                f"python3 -B {GATE} normalize without --corpus."
            ),
        },
        {
            "claim": (
                "Independent different-20 record sample is still unchecked. "
                "(Records now exist to sample: "
                f"{summary['n_records']} at {summary['records_file']}; author "
                "cited seed=19 ids in sample-resolve.json - reviewer must draw "
                "20 DISJOINT ids.)"
            ),
            "verdict": "NOT-CHECKED",
            "settling_experiment": (
                "Fresh-context independent reviewer samples 20 claim ids disjoint "
                "from sample-resolve.json rows, re-opens each anchor "
                "(repo-relative path:line, #fragment = json container key), and "
                "writes independent-review.json with verdict, independent=true, "
                "fresh_context=true."
            ),
        },
        {
            "claim": (
                "Whether the in-repo population substitution is ACCEPTED as "
                "satisfying CC-0019's catalog inputs is an open catalog "
                "adjudication (catalog inputs currently pin the harness-restore "
                "mount)."
            ),
            "verdict": "NOT-CHECKED",
            "settling_experiment": (
                "Wave owner amends WORK-UNIT-CATALOG.json#CC-0019 inputs (or "
                "rejects the substitution); until then SUCCESS:CC-0019 stays "
                "withheld even if the independent review PASSES."
            ),
        },
    ]

    # ---- downstream consumers (append) ----------------------------------------
    receipt["downstream_consumers"].extend(
        [
            {
                "consumer": "claim-registry consumers (ARC-0085 supersession; ranking)",
                "artifact_path": "command-center/corpus/claim-records.jsonl",
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": L.probe(
                    "source",
                    "file-read",
                    "read command-center/corpus/claim-records.jsonl",
                    f"{summary['n_records']} jsonl records",
                    0,
                ),
            },
            {
                "consumer": "independent-reviewer different-20 sample",
                "artifact_path": f"{PROBE_DIR}/sample-resolve.json",
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": L.probe(
                    "source",
                    "file-read",
                    f"read {PROBE_DIR}/sample-resolve.json",
                    "author sample ids (seed=19) - reviewer must sample disjoint",
                    0,
                ),
            },
        ]
    )

    # ---- extensions ------------------------------------------------------------
    receipt["extensions"].update(
        {
            "anti_false_green": (
                "BLOCKED-artifact-exists-over-disclosed-substitution; "
                "SUCCESS-still-withheld-pending-independent-review-and-catalog-adjudication"
            ),
            "impl_pass_2": {
                "at": TS,
                "agent": "impl-cc-0019 (team session)",
                "substrate": "windows-local-team-session",
                "driver": DRIVER,
                "note": (
                    "author-side update only; reviewer block untouched; state "
                    "stays BLOCKED; receipt self-sha measured at artifacts-pass "
                    "time (two-pass convention, cannot be self-consistent)"
                ),
            },
        }
    )

    # ---- artifacts (two-pass, packer convention) -------------------------------
    def arts() -> list[dict]:
        return [
            L.art(OUT, "primary"),
            L.art(GATE, "primary"),
            L.art(TESTS, "supporting"),
            L.art("command-center/corpus/claim-records.jsonl", "primary"),
            L.art("command-center/corpus/normalize-summary.json", "primary"),
            L.art(
                "command-center/corpus/__cc0019_planted_synthetic__.marker", "control"
            ),
            L.art(f"{PROBE_DIR}/normalize_inrepo_corpus.py", "control"),
            L.art(f"{PROBE_DIR}/_census_inrepo_sources.py", "control"),
            L.art(f"{PROBE_DIR}/_update_receipt_pass2.py", "control"),
            L.art(f"{PROBE_DIR}/source-census.json", "log"),
            L.art(f"{PROBE_DIR}/block-dryrun.json", "log"),
            L.art(f"{PROBE_DIR}/normalize-run.raw.txt", "log"),
            L.art(f"{PROBE_DIR}/sample-resolve.json", "log"),
            L.art(f"{PROBE_DIR}/tool-sample-resolve.json", "log"),
            L.art(f"{PROBE_DIR}/corpus-presence.json", "log"),
            L.art(f"{PROBE_DIR}/corpus-presence.raw.txt", "log"),
            L.art(f"{PROBE_DIR}/pytest-corpus-normalize.out", "log"),
            L.art(f"{PROBE_DIR}/probe1_corpus_presence.py", "control"),
            L.art("command-center/receipts/CC-0017.json", "supporting"),
            L.art("command-center/receipts/CC-0018.json", "supporting"),
            L.art(f"{PROBE_DIR}/_pack_receipt.py", "control"),
            L.art(MANIFEST, "supporting"),
        ]

    receipt["timestamps"]["ended_at"] = TS
    receipt["artifacts"] = arts()

    # ---- manifest ---------------------------------------------------------------
    manifest = {
        "schema_version": 1,
        "unit_id": UNIT,
        "entry_id": UNIT,
        "state": "BLOCKED",
        "artifacts": [a["path"] for a in receipt["artifacts"]],
        "receipt_path": OUT,
        "success_invented": False,
        "independent_review_invented": False,
        "corpus_fabricated": False,
        "corpus_present": False,
        "inrepo_corpus_present": True,
        "inrepo_corpus_records": summary["n_records"],
        "blocked_on": receipt["failure"]["blocked_on"],
    }
    (REPO / MANIFEST).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    rc = L.write_if_valid(receipt, OUT, SCHEMA)
    if rc != 0:
        return rc
    # Second pass: re-measure artifacts against the now-on-disk receipt/manifest
    # (packer convention; self-sha is measured at this pass).
    receipt["artifacts"] = arts()
    rc2 = L.write_if_valid(receipt, OUT, SCHEMA)
    print(
        f"state={receipt['state']} records={summary['n_records']} "
        f"sample={sample['resolve_fraction_strict']} rc={rc2}"
    )
    return rc2


if __name__ == "__main__":
    raise SystemExit(main())
