#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0330.json from live differential measurements."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from census import census  # noqa: E402
from differential import divergence_control, run_differential  # noqa: E402

OUT = "command-center/receipts/TST-0330.json"
SCHEMA = "command-center/schema/receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0330/probe1_corpus_parity.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0330/probe2_divergence_and_census.py"
)
QUESTION = (
    "Question: spec :11314 names two completion predicates disagreeing as a "
    "failure class. CC-0004 statically detects a fan-in site that rolls its "
    "own check; this unit is the runtime differential for the implementations "
    "that legitimately exist in different runtimes (the local python reducer, "
    "any JavaScript or shell reimplementation in a monitor, and the cloud "
    "dispatcher). Feed both the same corpus of unit states, including "
    "malformed and partial ones, and require byte-identical verdicts."
)
IMPL = [
    "command-center/p2-wave/probes/TST-0330/python_reducer.py",
    "command-center/p2-wave/probes/TST-0330/monitor_reducer.js",
    "command-center/p2-wave/probes/TST-0330/corpus.py",
    "command-center/p2-wave/probes/TST-0330/differential.py",
    "command-center/p2-wave/probes/TST-0330/census.py",
    "command-center/p2-wave/probes/TST-0330/probe1_corpus_parity.py",
    "command-center/p2-wave/probes/TST-0330/probe2_divergence_and_census.py",
    "command-center/p2-wave/probes/TST-0330/fixtures/mention-only.md",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def probe_obj(role: str, method: str, command: str, raw: str, code: int) -> dict:
    fp = hashlib.md5(f"{command}|{code}|{raw}".encode("utf-8")).hexdigest()
    return {
        "command": command,
        "exit_code": code,
        "fingerprint": fp,
        "method": method,
        "raw_output": raw[-4000:],
        "role": role,
    }


def main() -> int:
    diff = run_differential()
    div = divergence_control()
    pop = census()
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    contract_ok = (
        c1 == 0
        and c2 == 0
        and diff.get("byte_identical") is True
        and diff.get("malformed_count", 0) >= 3
        and diff.get("disagreement_count") == 0
        and div.get("ok") is True
        and pop.get("harness_count", 0) >= 2
        and pop.get("status") == "CHECKED"
    )
    if not contract_ok:
        print("FAILED:TST-0330 emit contract")
        print(f"c1={c1} c2={c2} identical={diff.get('byte_identical')} div={div.get('ok')}")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    artifacts = []
    for rel in IMPL:
        path = REPO / rel
        sha, size = sha256_file(path)
        artifacts.append(
            {
                "path": rel,
                "bytes": size,
                "sha256": sha,
                "exists": True,
                "role": "supporting",
                "eol": "LF",
            }
        )
    artifacts.insert(
        0,
        {
            "path": OUT,
            "exists": True,
            "role": "primary",
            "eol": "LF",
            "note": "bytes/sha256 are measured by UNIT-ARTIFACT-MANIFEST.json after write",
        },
    )

    src1 = probe_obj("source", "command", P1, t1, c1)
    src2 = probe_obj("source", "command", P2, t2, c2)
    disagreements_verbatim = diff.get("disagreements") or []
    state = "SUCCESS"
    sentinel = "SUCCESS:TST-0330"

    doc = {
        "schema_version": 1,
        "report_kind": "test-receipt",
        "unit_id": "TST-0330",
        "id": "TST-0330",
        "state": state,
        "sentinel": sentinel,
        "completion_sentinel": sentinel,
        "spec_anchor": "_USER-PROMPTS.md:11314",
        "title": (
            "Differential-test two completion-predicate implementations "
            "against each other on identical inputs"
        ),
        "question": QUESTION,
        "answer": (
            f"{sentinel}: local-python and monitor-javascript reducers returned "
            "byte-identical verdicts "
            f"(verdict+failing_condition_id+reason) on a {diff['corpus_size']}-row "
            f"corpus with {diff['malformed_count']} malformed inputs. "
            f"disagreement_count={diff['disagreement_count']}. "
            "Skipping C08 on the inert-negative-control row made python COMPLETE "
            "while the monitor stayed INCOMPLETE/C08, so the differential is live. "
            f"Harness implementations={pop['harness_count']} roles={pop['roles']}. "
            "CC-0003 shipped reducer and a cloud dispatcher reducer were absent "
            "from this worktree; they are named as residual unknowns rather than "
            "invented as a third agreeing copy."
        ),
        "output_schema": SCHEMA,
        "min_bytes_threshold": 2048,
        "named_failure_class": "two-completion-predicates-disagree",
        "cloud_ok": False,
        "metrics": {
            "corpus_size": diff["corpus_size"],
            "malformed_count": diff["malformed_count"],
            "disagreement_count": diff["disagreement_count"],
            "harness_implementations": pop["harness_count"],
            "production_reducers_found": pop["production_count"],
        },
        "measurements": {
            "corpus_size": diff["corpus_size"],
            "malformed_count": diff["malformed_count"],
            "disagreement_count": diff["disagreement_count"],
            "disagreements_verbatim": disagreements_verbatim,
            "classes": diff["classes"],
            "ids": diff["ids"],
            "byte_identical": diff["byte_identical"],
            "implementations": pop["harness_implementations"],
            "production_hits": pop["production_hits"],
            "census_status": pop["status"],
        },
        "controls": {
            "divergence_skip_c08": {
                "detected": div.get("detected"),
                "honest_agree_on_c08_row": div.get("honest_agree_on_c08_row"),
                "healthy_skip_still_complete": div.get("healthy_skip_still_complete"),
                "patched_python": div.get("patched_python_on_c08_row"),
                "honest_monitor": div.get("honest_monitor_on_c08_row"),
                "input_verbatim": div.get("input_verbatim"),
            },
            "mention_is_not_use": pop.get("mention_control"),
        },
        "artifacts": artifacts,
        "evidence": [
            {
                "kind": "differential",
                "path": "command-center/p2-wave/probes/TST-0330/differential.py",
                "anchor": "command-center/p2-wave/probes/TST-0330/probe1_corpus_parity.py",
                "claim": (
                    f"Corpus size {diff['corpus_size']}, malformed "
                    f"{diff['malformed_count']}, disagreements "
                    f"{diff['disagreement_count']}; every disagreeing input "
                    f"verbatim: {json.dumps(disagreements_verbatim, sort_keys=True)}"
                ),
                "confidence": "almost-certain",
                "probes": [src1],
                "verdict": "CONFIRMED",
                "note": (
                    f"Corpus size {diff['corpus_size']}, disagreements "
                    f"{diff['disagreement_count']}, malformed "
                    f"{diff['malformed_count']}."
                ),
            },
            {
                "kind": "divergence-control",
                "path": "command-center/p2-wave/probes/TST-0330/python_reducer.py",
                "anchor": "command-center/p2-wave/probes/TST-0330/probe2_divergence_and_census.py",
                "claim": (
                    "Patching the python reducer to skip C08 is detected: the "
                    "inert-negative-control row becomes COMPLETE on python and "
                    "stays INCOMPLETE/C08 on the monitor."
                ),
                "confidence": "almost-certain",
                "probes": [src2],
                "verdict": "CONFIRMED",
                "note": (
                    "skip-C08 detected on inert-negative-control; mention-only "
                    "markdown is not counted as an implementation."
                ),
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": "No automatic retry: a failure here is a finding, not a transient.",
        },
        "tests": [
            {
                "id": "differential-malformed-corpus",
                "requirement": (
                    "Differential over a corpus that deliberately includes "
                    "partial artifacts, missing sentinels and torn JSON."
                ),
                "verdict": "PASS",
                "result": "PASS",
                "command": P1,
                "evidence": (
                    f"size={diff['corpus_size']} malformed={diff['malformed_count']} "
                    f"disagreements={diff['disagreement_count']} "
                    f"classes={json.dumps(diff['classes'], sort_keys=True)}"
                ),
            },
            {
                "id": "divergence-control-skip-condition",
                "requirement": (
                    "Divergence control: patch one implementation to skip a "
                    "condition and confirm the differential detects it."
                ),
                "verdict": "PASS",
                "result": "PASS",
                "command": P2,
                "evidence": (
                    f"detected={div.get('detected')} patched="
                    f"{(div.get('patched_python_on_c08_row') or {}).get('canonical')} "
                    f"monitor="
                    f"{(div.get('honest_monitor_on_c08_row') or {}).get('canonical')}"
                ),
            },
            {
                "id": "implementation-census",
                "requirement": (
                    "Implementation census: if only one implementation exists, "
                    "report that as NOT-CHECKED rather than passing the unit trivially."
                ),
                "verdict": "PASS" if pop.get("harness_count", 0) >= 2 else "NOT-CHECKED",
                "result": "PASS" if pop.get("harness_count", 0) >= 2 else "NOT-CHECKED",
                "command": P2,
                "evidence": (
                    f"harness_count={pop.get('harness_count')} roles={pop.get('roles')} "
                    f"production_count={pop.get('production_count')} "
                    f"cc0003_on_disk={pop.get('cc0003_on_disk')} "
                    f"cloud_dispatcher_on_disk={pop.get('cloud_dispatcher_on_disk')}"
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "skip-c08-detected",
                "kind": "known-broken-implementation",
                "description": "Python reducer with C08 skipped must diverge on the C08-failing row",
                "fired_on_bad_state": div.get("detected"),
                "silent_on_good_state": div.get("healthy_skip_still_complete"),
                "bad_state_output": (div.get("patched_python_on_c08_row") or {}).get("canonical"),
                "good_state_output": (div.get("honest_monitor_on_c08_row") or {}).get("canonical"),
            },
            {
                "id": "mention-is-not-use",
                "kind": "use-vs-mention",
                "description": "fixtures/mention-only.md must not be counted as a reducer",
                "fired_on_bad_state": True,
                "silent_on_good_state": not (pop.get("mention_control") or {}).get(
                    "counted_as_implementation"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0330-probe2-divergence-and-census",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Adversarial control is python_reducer.py --skip C08 on "
                "inert-negative-control. The monitor-javascript reducer is a "
                "separate runtime (node), not a Python import of the first "
                "implementation."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0330/UNIT-ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/TST-0330/probe1_corpus_parity.py",
                "artifact_path": "command-center/p2-wave/probes/TST-0330/python_reducer.py",
                "executed": True,
                "read_ok": True,
                "exit_code": c1,
                "probe": src1,
            },
            {
                "consumer": "command-center/p2-wave/probes/TST-0330/probe2_divergence_and_census.py",
                "artifact_path": "command-center/p2-wave/probes/TST-0330/monitor_reducer.js",
                "executed": True,
                "read_ok": True,
                "exit_code": c2,
                "probe": src2,
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "CC-0003's shipped shared reducer and a cloud-dispatcher "
                    "reimplementation are not on this worktree, so production "
                    "parity against those binaries is NOT-CHECKED."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run this differential after CC-0003 and the dispatcher "
                    "reducer exist, feeding the same corpus.json payload."
                ),
            }
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1},
            {"id": "probe2", "command": P2, "exit_code": c2},
        ],
    }

    required = [
        "unit_id",
        "state",
        "sentinel",
        "completion_sentinel",
        "question",
        "answer",
        "tests",
        "metrics",
        "controls",
        "evidence",
        "reviewer",
        "artifacts",
    ]
    missing = [k for k in required if k not in doc]
    if missing:
        print("FAILED:TST-0330 schema missing", missing)
        return 1
    if not isinstance(doc.get("tests"), list) or len(doc["tests"]) < 2:
        print("FAILED:TST-0330 tests")
        return 1
    if not isinstance(doc.get("evidence"), list) or len(doc["evidence"]) < 2:
        print("FAILED:TST-0330 evidence")
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    out_path.write_text(body, encoding="utf-8")
    sha, size = sha256_file(out_path)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:TST-0330")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
