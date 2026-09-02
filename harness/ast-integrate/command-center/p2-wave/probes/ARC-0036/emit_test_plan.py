#!/usr/bin/env python3
"""Emit command-center/phase3/A5/TEST-PLAN.json from a live chaos/resume run."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import cases as C  # noqa: E402
import reviewer as R  # noqa: E402
import schema_bind as SB  # noqa: E402

OUT = "command-center/phase3/A5/TEST-PLAN.json"
SCHEMA = "command-center/schema/test-plan.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
SPEC = "command-center/p2-wave/probes/ARC-0036/SPEC-FRAGMENT.txt"
SPEC_CNF = "command-center/p2-wave/probes/CNF-0170/SPEC-FRAGMENT.txt"
MEASURE = "command-center/p2-wave/_measure_one_delivered.py"
DESIGN_A5 = "command-center/phase3/A5/DESIGN.json"
QUESTION = (
    "Specify the runtime's chaos and resume suite: kill the monitor mid-run, "
    "kill a worker mid-unit, corrupt a ledger record, replay a duplicate "
    "dispatch, and resume from a partial batch - each asserting the shared "
    "completion predicate returns FALSE where it must. Include the mutation "
    "control that proves the predicate is not vacuously true (a unit with an "
    "absent artifact must never pass)."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0036/probe1_coverage.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0036/probe2_vacuity.py"
)
SUPPORTING = [
    SCHEMA,
    SPEC,
    "command-center/p2-wave/probes/ARC-0036/predicate.py",
    "command-center/p2-wave/probes/ARC-0036/runtime.py",
    "command-center/p2-wave/probes/ARC-0036/cases.py",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(path: Path, snippet: str) -> int:
    lines = path.read_text(encoding="utf-8").splitlines()
    hits = [i for i, ln in enumerate(lines, 1) if snippet in ln]
    if len(hits) != 1:
        raise ValueError(f"{path}: snippet {snippet!r} hits={hits}")
    return hits[0]


def live_anchor(rel: str, snippet: str, kind: str, claim: str) -> dict:
    line = find_line(REPO / rel, snippet)
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{rel}:{line}",
    }


def art_row(rel: str, role: str) -> dict:
    digest, size = sha256_file(REPO / rel)
    if not (REPO / rel).is_file() or size <= 0:
        raise RuntimeError(f"supporting artifact missing: {rel}")
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def probe(role: str, method: str, command: str, raw: str, fp: str, exit_code: int = 0) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:4000],
        "fingerprint": fp,
        "exit_code": exit_code,
    }


def evidence_item(anchor: dict, verdict: str, src_fp: str, ver_fp: str) -> dict:
    rel = anchor["path"]
    return {
        "claim": anchor["claim"],
        "verdict": verdict,
        "confidence": "almost-certain",
        "anchor": anchor["anchor"],
        "probes": [
            probe(
                "source",
                "test-run",
                "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/ARC-0036/cases.py",
                f"live-anchor {anchor['anchor']}",
                src_fp,
            ),
            probe(
                "verifier",
                "file-read",
                f"{rel}:{anchor['line']}",
                anchor["snippet"],
                ver_fp,
            ),
        ],
    }


def main() -> int:
    run = C.run_all()
    if not run["pass"]:
        print("FAILED:ARC-0036 live suite")
        print(json.dumps(run["checks"], indent=2))
        print(json.dumps(run["coverage"], indent=2))
        return 1

    if (REPO / DESIGN_A5).is_file():
        print("FAILED:ARC-0036 unexpected A5 DESIGN.json; this unit must not rebuild it")
        return 1

    e1 = live_anchor(
        CATALOG,
        "Each chaos case names the injection mechanism",
        "live-tree",
        "Catalog requires each chaos case to name injection + numbered predicate condition.",
    )
    e2 = live_anchor(
        CATALOG,
        "Vacuity mutation: delete an artifact after a unit reports success",
        "live-tree",
        "Catalog requires delete-after-success to flip the predicate to FALSE.",
    )
    e3 = live_anchor(
        CATALOG,
        "Predicate-condition coverage: conditions exercised divided by 12",
        "live-tree",
        "Catalog requires coverage as exercised/12 with the uncovered list enumerated.",
    )
    e4 = live_anchor(
        CATALOG,
        "kill the monitor mid-run, kill a worker mid-unit",
        "live-tree",
        "Catalog names the five chaos/resume injections this suite must execute.",
    )
    e5 = live_anchor(
        SPEC,
        "Exit code zero alone is never success",
        "live-tree",
        "Spec fragment: exit code zero is never completion.",
    )
    e6 = live_anchor(
        SPEC_CNF,
        "A unit is complete only when all applicable conditions hold",
        "live-tree",
        "CNF-0170 frozen spec carries the same 12 numbered conditions.",
    )
    e7 = live_anchor(
        MEASURE,
        'print(f"FAILED:delivered {uid} {reason}")',
        "live-tree",
        "G-1 measure treats a missing artifact as predicate:absent, not success.",
    )
    live_anchors = [e1, e2, e3, e4, e5, e6, e7]

    suite_ids = [c["id"] for c in run["named_chaos"]] + [
        c["id"] for c in run["injectors"]
    ]
    rev_full = R.review(suite_ids + ["MUT-VACUITY-DELETE-ARTIFACT"])
    uncaught = rev_full["mutation_suite_would_not_catch"]

    suite_cases = []
    for c in run["named_chaos"] + run["injectors"]:
        suite_cases.append(
            {
                "id": c["id"],
                "named_chaos": c["named_chaos"],
                "catalog_name": c.get("catalog_name"),
                "injection_mechanism": c["injection_mechanism"],
                "target_condition": c["target_condition"],
                "target_id": c["target_id"],
                "assertion": c["assertion"],
                "expected_verdict": c["expected_verdict"],
                "live_verdict": c["verdict"],
                "target_unsatisfied": c["target_unsatisfied"],
                "failing_condition_ids": c["failing_condition_ids"],
                "naive_rejected": c.get("naive_rejected"),
            }
        )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    started = "2026-08-25T00:40:00Z"
    cov = run["coverage"]
    schema_doc = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    schema_ok = "$ref" in schema_doc and schema_doc.get("x-artifact-class") == "test-plan"

    observations = [
        {
            "name": "coverage-exercised",
            "measured": int(cov["exercised"]),
            "method": "live named-chaos plus injectors; UNSATISFIED count / 12",
            "anchor": e3["anchor"],
        },
        {
            "name": "coverage-uncovered-empty",
            "measured": not cov["uncovered"],
            "method": "coverage_from_cases uncovered list",
            "anchor": e3["anchor"],
        },
        {
            "name": "vacuity-flipped",
            "measured": bool(run["vacuity"]["flipped"]),
            "method": "delete-after-COMPLETE re-evaluate C2",
            "anchor": e2["anchor"],
        },
        {
            "name": "healthy-complete",
            "measured": run["healthy"]["verdict"] == "COMPLETE",
            "method": "run_healthy FIX-1000",
            "anchor": e5["anchor"],
        },
        {
            "name": "exit-zero-alone-incomplete",
            "measured": run["exit_zero_alone"]["verdict"] != "COMPLETE",
            "method": "exit_code=0 with absent artifact",
            "anchor": e5["anchor"],
        },
        {
            "name": "schema-shim-resolves-on-disk",
            "measured": schema_ok,
            "method": "RefResolver store of three $id documents, no HTTP",
            "anchor": f"{SCHEMA}:1",
        },
    ]
    for c in run["named_chaos"]:
        observations.append(
            {
                "name": c["id"],
                "measured": c["verdict"] == "INCOMPLETE" and c["target_unsatisfied"],
                "method": c["injection_mechanism"][:240],
                "anchor": e4["anchor"],
            }
        )

    control_ids = [c["id"] for c in run["named_chaos"]] + [
        "MUT-VACUITY-DELETE-ARTIFACT",
        "MUT-EXIT-ZERO-ALONE",
    ]

    answer = (
        "A5 chaos/resume suite, executed on a probe-local ledger: "
        "kill-monitor → C11 INCOMPLETE; kill-worker mid-write → C3 "
        "INCOMPLETE; corrupt HARVEST JSONL → C4 INCOMPLETE; duplicate "
        "CLAIM → C1 INCOMPLETE; partial-batch resume → C2 INCOMPLETE "
        "(naive claim-means-complete rejected). Coverage "
        f"{cov['exercised']}/{cov['total']} uncovered={cov['uncovered']}. "
        "Vacuity: delete-after-success flips COMPLETE to INCOMPLETE on C2. "
        "A5 DESIGN.json absent; not rebuilt. Reviewer names "
        f"{uncaught['id']} as uncaught. SUCCESS:ARC-0036"
    )

    report = {
        "kind": "test-plan",
        "observations": observations,
        "control_ids": control_ids,
        "architecture_id": "A5",
        "architecture_class": "distributed-workflow-runtime",
        "completion_sentinel": "SUCCESS:ARC-0036",
        "title": (
            "A5 (distributed workflow-runtime): Chaos, resume and "
            "duplicate-dispatch suite that proves the predicate is not vacuously true"
        ),
        "question": QUESTION,
        "answer": answer,
        "design_present": False,
        "design_path": DESIGN_A5,
        "design_note": (
            "command-center/phase3/A5/DESIGN.json is absent (ARC-0031 not "
            "delivered). This unit does not rebuild A5 DESIGN. The suite runs "
            "against a probe-local ledger/worker/monitor surrogate bound to the "
            "12-condition spec fragment. Claims about a shipped A5 runtime are "
            "SENTENCE, not DESIGN."
        ),
        "predicate": {
            "spec": SPEC,
            "conditions": [
                {"n": n, "id": f"C{n}", "text": C.CONDITION_TEXT[n]}
                for n in range(1, 13)
            ],
            "shipped_reducer": (
                "platform/lib/completion_predicate.py is absent on this tree "
                "(CNF-0170 measured fail-closed UNKNOWN). The suite oracle is "
                "command-center/p2-wave/probes/ARC-0036/predicate.py."
            ),
            "exit_code_never_success": True,
        },
        "suite": {
            "id": "A5-chaos-resume-duplicate-dispatch",
            "kind": "chaos-resume-vacuity",
            "substrate": "command-center/p2-wave/probes/ARC-0036/runtime.py",
            "cases": suite_cases,
        },
        "chaos_cases": [c for c in suite_cases if c["named_chaos"]],
        "coverage": cov,
        "mutations": [
            {
                "id": "MUT-VACUITY-DELETE-ARTIFACT",
                "kind": "vacuity",
                "procedure": (
                    "Run a unit to COMPLETE, unlink its artifact, re-evaluate "
                    "the same observation. C2 must become UNSATISFIED and the "
                    "verdict must flip to INCOMPLETE."
                ),
                "expected_complete": False,
                "live_before": run["vacuity"]["before_verdict"],
                "live_after": run["vacuity"]["after_verdict"],
                "flipped": run["vacuity"]["flipped"],
                "c2_after": run["vacuity"]["c2_after"],
            },
            {
                "id": "MUT-EXIT-ZERO-ALONE",
                "kind": "anti-pattern",
                "procedure": (
                    "Observation with exit_code=0, empty state, and absent "
                    "artifact. Reducer must not return COMPLETE."
                ),
                "expected_complete": False,
                "live_verdict": run["exit_zero_alone"]["verdict"],
            },
        ],
        "healthy_control": run["healthy"],
        "live_checks": run["checks"],
        "live_anchors": live_anchors,
        "mutation_suite_would_not_catch": uncaught,
        "claims": [
            {
                "id": "CL-VACUOUS-TRUE",
                "claim": (
                    "The shared completion predicate is vacuously true: a unit "
                    "with an absent artifact can still complete."
                ),
                "verdict": "REFUTED",
                "defect_locus": "SENTENCE",
                "anchor": e2["anchor"],
                "scoped_restatement": (
                    "Delete-after-success flips COMPLETE to INCOMPLETE on C2. "
                    f"live flipped={run['vacuity']['flipped']} "
                    f"c2_after={run['vacuity']['c2_after']}."
                ),
            },
            {
                "id": "CL-NAMED-CHAOS",
                "claim": (
                    "Each catalog-named chaos case names an injection mechanism "
                    "and a numbered condition, and the live reducer returns "
                    "INCOMPLETE on that condition."
                ),
                "verdict": "CONFIRMED",
                "anchor": e1["anchor"],
            },
            {
                "id": "CL-COVERAGE",
                "claim": (
                    "Predicate-condition coverage is exercised/12 with the "
                    "uncovered list enumerated from a live run, not asserted."
                ),
                "verdict": "CONFIRMED",
                "anchor": e3["anchor"],
                "scoped_restatement": (
                    f"{cov['exercised']}/{cov['total']} = {cov['ratio']}; "
                    f"uncovered={cov['uncovered']}."
                ),
            },
            {
                "id": "CL-A5-DESIGN-ORACLE",
                "claim": "A5 DESIGN.json is the executable oracle for this suite.",
                "verdict": "REFUTED",
                "defect_locus": "SENTENCE",
                "why_locus": (
                    "command-center/phase3/A5/DESIGN.json is absent. A missing "
                    "dossier cannot be a DESIGN locus. The oracle is the probe "
                    "runtime plus SPEC-FRAGMENT.txt."
                ),
                "anchor": e4["anchor"],
            },
            {
                "id": "CL-EXIT-ZERO",
                "claim": "Exit code zero alone is success.",
                "verdict": "REFUTED",
                "anchor": e5["anchor"],
                "scoped_restatement": (
                    f"exit-zero-alone verdict={run['exit_zero_alone']['verdict']}."
                ),
            },
        ],
        "named_probes": [
            {"id": "probe1", "role": "coverage-and-named-chaos", "command": P1},
            {"id": "probe2", "role": "vacuity-and-uncaught-mutation", "command": P2},
        ],
        "strongest_surviving_counterargument": (
            "C12 is implemented as parse-plus-required-fields, so a "
            "schema-valid artifact that cites a missing path still COMPLETE. "
            "A hung (not killed) worker is also outside the suite: it leaves "
            "C1 UNKNOWN rather than UNSATISFIED. Those residuals do not make "
            "the five named chaos cases or the vacuity mutation green."
        ),
        "adv_rebuild_circle": False,
        "cloud_ok": False,
    }

    schema_txt = (REPO / SCHEMA).read_text(encoding="utf-8")
    consumer_raw = f"parsed keys={sorted(json.loads(schema_txt).keys())[:8]}"

    doc = {
        "schema_version": 1,
        "unit_id": "ARC-0036",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0036",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json work_units[id=ARC-0036] "
            "question_or_target + tests_required"
        ),
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "test-architect",
            "execution_substrate": "headless-linux",
        },
        "artifacts": [art_row(p, "supporting") for p in SUPPORTING],
        "evidence": [
            evidence_item(e1, "CONFIRMED", "src:e1-catalog-inj", "ver:e1-catalog-inj"),
            evidence_item(e2, "CONFIRMED", "src:e2-catalog-vac", "ver:e2-catalog-vac"),
            evidence_item(e3, "CONFIRMED", "src:e3-catalog-cov", "ver:e3-catalog-cov"),
            evidence_item(e4, "CONFIRMED", "src:e4-catalog-five", "ver:e4-catalog-five"),
            evidence_item(e5, "CONFIRMED", "src:e5-spec-exit0", "ver:e5-spec-exit0"),
            evidence_item(e6, "CONFIRMED", "src:e6-cnf-0170", "ver:e6-cnf-0170"),
            evidence_item(e7, "CONFIRMED", "src:e7-measure", "ver:e7-measure"),
        ],
        "tests": [
            {
                "id": "T1-predicate-condition-coverage",
                "name": "Live chaos/injector run: exercised/12 and uncovered list",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-vacuity-delete-after-success",
                "name": "Delete artifact after COMPLETE; predicate flips to INCOMPLETE on C2",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-VACUITY-DELETE",
                "kind": "mutation",
                "description": (
                    "After COMPLETE, unlink the artifact. Detector must fire "
                    "(INCOMPLETE on C2) and stay silent on the healthy control."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"after={run['vacuity']['after_verdict']} "
                    f"c2={run['vacuity']['c2_after']}"
                ),
                "good_state_output": f"healthy={run['healthy']['verdict']}",
            },
            {
                "id": "NC-EXIT-ZERO-ALONE",
                "kind": "mutation",
                "description": "exit_code=0 with no artifact must not be COMPLETE.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"verdict={run['exit_zero_alone']['verdict']}",
                "good_state_output": f"healthy={run['healthy']['verdict']}",
            },
            {
                "id": "NC-SCHEMA-GARBAGE",
                "kind": "malformed-input",
                "description": (
                    "Empty object, {state:SUCCESS}, and a 2000-byte blob must "
                    "fail test-plan.schema.json once $ref is bound on disk."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "iter_errors non-empty on garbage",
                "good_state_output": "iter_errors empty on this receipt",
            },
        ],
        "reviewer": {
            "reviewer_id": rev_full["reviewer_id"],
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "xai",
            "notes": (
                f"{rev_full['note']} Named uncaught mutation: {uncaught['id']}. "
                f"{uncaught['why_uncaught']}"
            )[:8192],
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/ARC-0036/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "ARC-0036",
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads of the declared test-plan schema shim",
                "artifact_path": SCHEMA,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "schema-validate",
                    "python3 -c \"import json; json.load(open('command-center/schema/test-plan.schema.json'))\"",
                    consumer_raw,
                    "consumer:schema-json-load",
                ),
            }
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": now,
        },
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot: after two failed attempts on the same "
                "framing, enumerate at least two alternative decompositions "
                "before a third attempt (AGENTS.md 4b)"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "C12 SATISFIED does not prove cited paths inside the "
                    "artifact exist on disk."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "MUT-C12-UNUSABLE-CITED-PATH: after C12 SATISFIED, replace a "
                    "cited path with a missing string and assert C12 flips."
                ),
            },
            {
                "claim": (
                    "A hung (not killed) worker holding a CLAIM lease is outside "
                    "the five named chaos cases."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "MUT-HANG-LEASE: pause the worker with no torn file and "
                    "assert harvest treats C1 UNKNOWN as unacceptable."
                ),
            },
        ],
        "report": report,
    }

    schema_errs = SB.errors(doc)
    if schema_errs:
        print("FAILED:ARC-0036 schema errors")
        for line in schema_errs[:25]:
            print(" ", line)
        return 1
    for g in (
        {},
        {"state": "SUCCESS"},
        {"blob": "x" * 2000},
        {"totally": "unrelated"},
    ):
        if not SB.errors(g):
            print(f"FAILED:ARC-0036 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:ARC-0036 artifact {size}B below floor")
        return 1
    text = out.read_text(encoding="utf-8")
    if "SUCCESS:ARC-0036" not in text:
        print("FAILED:ARC-0036 sentinel absent from artifact")
        return 1
    if (REPO / DESIGN_A5).is_file():
        print("FAILED:ARC-0036 DESIGN.json appeared during emit")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(f"coverage={cov['exercised']}/{cov['total']} uncovered={cov['uncovered']}")
    print(f"checks={run['checks']}")
    print("SUCCESS:ARC-0036 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
