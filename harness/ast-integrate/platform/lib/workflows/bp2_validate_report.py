"""Emit the EXACT validator output for each of the twelve bp-2 blueprints.

The unit contract is: "Validate every one with `python platform/lib/wfdsl/validate.py` and report
the validator's exact output per file." So this shells the real CLI once per document and records
its verbatim stdout plus exit code - not a paraphrase, and not a re-implementation of the checks
in this process, because a re-implementation could disagree with the shipped validator.

Adds two things the CLI does not cover, each recorded separately so the provenance of every
number is clear:
  * schema_refs: every declared ``schema_ref``/``output_schema`` resolved and COMPILED through
    platform/lib/schema_resolver.py (the CLI does not open them)
  * structural fingerprint distinctness across the twelve

Writes platform/workflows/BP2-VALIDATION.json and ends with a terminal SUCCESS:/FAILED: marker.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bp2_common as C  # noqa: E402

VALIDATE_CLI = REPO_ROOT / "platform" / "lib" / "wfdsl" / "validate.py"
OUT = REPO_ROOT / "platform" / "workflows" / "BP2-VALIDATION.json"


def run_cli(rel_path: str) -> dict:
    proc = subprocess.run(
        [sys.executable, str(VALIDATE_CLI), "workflow", rel_path],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=300,
    )
    stdout = proc.stdout.strip()
    parsed = None
    try:
        parsed = json.loads(stdout)[0]
    except Exception:  # noqa: BLE001 - keep the raw text either way
        parsed = None
    return {
        "command": f"python platform/lib/wfdsl/validate.py workflow {rel_path}",
        "exit_code": proc.returncode,
        "stdout_verbatim": stdout,
        "stderr_verbatim": proc.stderr.strip(),
        "parsed": parsed,
    }


def main() -> int:
    report: dict = {
        "artifact": "platform/workflows/BP2-VALIDATION.json",
        "unit": "blueprints/bp-2",
        "range": "blueprints 13-24 of 96 (design cards BP-BRN-02 .. BP-REQ-02)",
        "validator": "platform/lib/wfdsl/validate.py (shelled per file; output verbatim)",
        "documents": {},
    }

    failures: list[str] = []
    for bp_id in sorted(C.BP2_IDS):
        rel = f"platform/workflows/{C.BP2_IDS[bp_id]}"
        cli = run_cli(rel)
        doc = C.load(bp_id)
        refs = sorted(set(C.iter_schema_refs(doc)))
        ref_fail = C.schema_ref_failures(doc)
        wex = C.worked_example_errors(doc)
        entry = {
            "file": rel,
            "blueprint_index": doc["x_extensions"]["blueprint_index"],
            "design_card": doc["x_extensions"]["design_card"],
            "flagship": bool(doc.get("flagship")),
            "categories": doc.get("categories"),
            "stage_count": len(C.fingerprint(doc)["stage_kinds"])
            and sum(C.fingerprint(doc)["stage_kinds"].values()),
            "stage_kinds": C.fingerprint(doc)["stage_kinds"],
            "validator": cli,
            "schema_refs_declared": len(refs),
            "schema_refs_resolving": len(refs) - len(ref_fail),
            "schema_refs_unresolvable": ref_fail,
            "worked_examples": len(C.worked_examples(doc)),
            "worked_example_problems": wex,
        }
        report["documents"][bp_id] = entry
        if cli["exit_code"] != 0 or ref_fail or wex:
            failures.append(bp_id)

    keys = {bp_id: C.fingerprint_key(C.load(bp_id)) for bp_id in sorted(C.BP2_IDS)}
    report["distinctness"] = {
        "method": "mechanical structural fingerprint (stage-kind multiset, barrier modes, "
        "fan-out source/concurrency, loop convergence shape, gate predicate+blocking+on_fail, "
        "conditional stages, replay/resume/retry/failure/routing/cache shape, network, "
        "stopping-rule ids)",
        "documents": len(keys),
        "distinct_fingerprints": len(set(keys.values())),
        "collisions": [
            [a, b]
            for i, a in enumerate(sorted(keys))
            for b in sorted(keys)[i + 1 :]
            if keys[a] == keys[b]
        ],
    }
    report["totals"] = {
        "documents": len(C.BP2_IDS),
        "schema_valid": sum(
            1
            for e in report["documents"].values()
            if e["validator"]["parsed"] and e["validator"]["parsed"]["schema_valid"]
        ),
        "zero_semantic_violations": sum(
            1
            for e in report["documents"].values()
            if e["validator"]["parsed"]
            and e["validator"]["parsed"]["semantic_violations"] == 0
        ),
        "zero_semantic_advisories": sum(
            1
            for e in report["documents"].values()
            if e["validator"]["parsed"]
            and e["validator"]["parsed"]["semantic_advisories"] == 0
        ),
        "exit_code_zero": sum(
            1 for e in report["documents"].values() if e["validator"]["exit_code"] == 0
        ),
        "all_schema_refs_resolve": sum(
            1 for e in report["documents"].values() if not e["schema_refs_unresolvable"]
        ),
        "flagship": sum(1 for e in report["documents"].values() if e["flagship"]),
    }
    report["ok"] = not failures and not report["distinctness"]["collisions"]
    OUT.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")

    for bp_id, e in report["documents"].items():
        p = e["validator"]["parsed"] or {}
        print(
            f"exit={e['validator']['exit_code']} schema_valid={p.get('schema_valid')} "
            f"viol={p.get('semantic_violations')} adv={p.get('semantic_advisories')} "
            f"refs={e['schema_refs_resolving']}/{e['schema_refs_declared']} "
            f"stages={e['stage_count']:>2} {'FLAGSHIP' if e['flagship'] else '        '} {bp_id}"
        )
    print()
    print("totals:", json.dumps(report["totals"]))
    print(
        "distinctness:",
        report["distinctness"]["distinct_fingerprints"],
        "of",
        report["distinctness"]["documents"],
        "collisions=",
        report["distinctness"]["collisions"],
    )
    print(f"(artifact written: {OUT})")
    print(
        "SUCCESS:blueprints-bp-2-validation"
        if report["ok"]
        else "FAILED:blueprints-bp-2-validation " + ", ".join(failures)
    )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
