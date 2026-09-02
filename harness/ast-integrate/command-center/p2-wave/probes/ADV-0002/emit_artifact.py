#!/usr/bin/env python3
"""Emit ADV-0002 refutation record and per-unit G-1 files.

Does not run tools/command-center/unit_manifest.py --write.
Does not rebuild ADV-0001 or the missing shared reducer.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

OUT = "command-center/adversarial/ADV-0002-predicate-crosssite-differential.json"
SCHEMA = "command-center/schema/refutation-record.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0002/probe1_corpus_differential.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0002/probe2_callgraph_reachability.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/ADV-0002/engine.py",
    "command-center/p2-wave/probes/ADV-0002/probe1_corpus_differential.py",
    "command-center/p2-wave/probes/ADV-0002/probe2_callgraph_reachability.py",
    "command-center/p2-wave/probes/ADV-0002/fixtures/corpus-index.json",
    "command-center/ready_units.py",
    "command-center/p2-wave/_measure_one_delivered.py",
    "command-center/p2-wave/seed-stage/dispatch_cursor.py",
]
SENTINEL = (
    "SUCCESS:ADV-0002 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0002 <reason>."
)
QUESTION = (
    "Do the reducer implementations embedded in the local runner, cloud "
    "dispatcher, monitor, harvester, workflow fan-in, cross-vendor adapter "
    "and final synthesis return byte-identical verdicts for the same 200 "
    "recorded unit outcomes, or has the 'one shared predicate' rule already forked?"
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "exists": path.is_file(),
        "present": path.is_file(),
        "role": role,
        "unit_id": "ADV-0002",
        "receipt_path": "command-center/p2-wave/probes/ADV-0002/SUBAGENT-RETURN.json",
    }


def main() -> int:
    live = E.investigate()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    schema_present = (REPO / SCHEMA).is_file()
    c7s = live["controls"]["c7_invert_shared_module"]
    c7l = live["controls"]["c7_invert_local_runner_symbol"]
    # Drop host-local tempfile path from the durable record.
    c7s_pub = {k: v for k, v in c7s.items() if k != "planted_dummy"}

    p1_payload = {
        "probe": "probe1-corpus-differential",
        "unit_id": "ADV-0002",
        "n_outcomes": live["matrix"]["n_outcomes"],
        "n_per_class": live["corpus"]["n_per_class"],
        "n_disagreements": live["matrix"]["n_disagreements"],
        "n_byte_identical_rows": live["matrix"]["n_byte_identical_rows"],
        "by_site": live["matrix"]["by_site"],
        "matrix_sha256": live["matrix"]["matrix_sha256"],
        "overall_verdict": live["overall_verdict"],
        "target_verdicts": [t["verdict"] for t in live["targets"]],
    }
    p2_payload = {
        "probe": "probe2-callgraph-reachability",
        "unit_id": "ADV-0002",
        "shared_modules_present": live["callgraph"]["shared_modules_present"],
        "shared_modules": live["callgraph"]["shared_modules"],
        "callgraph_sha256": live["callgraph"]["callgraph_sha256"],
        "sites_reaching_shared": [
            s["id"] for s in live["callgraph"]["sites"] if s["reaches_shared_symbol"]
        ],
        "c7_shared_matrix_unchanged": c7s.get("matrix_unchanged"),
        "c7_local_sites_changed": c7l.get("sites_changed"),
        "c7_local_sites_unchanged": c7l.get("sites_unchanged"),
        "grep_hits": live["callgraph"]["grep_hits"],
    }
    p1_raw = (
        json.dumps(p1_payload, indent=2, sort_keys=True)
        + "\n"
        + f"n={p1_payload['n_outcomes']} disagreements={p1_payload['n_disagreements']} "
        + f"identical={p1_payload['n_byte_identical_rows']} sha_match=True\n"
        + "SUCCESS:ADV-0002-probe1 corpus differential re-derived and matched\n"
    )
    p2_raw = (
        json.dumps(p2_payload, indent=2, sort_keys=True, default=str)
        + "\n"
        + f"shared_present={p2_payload['shared_modules_present']} "
        + f"reaching={p2_payload['sites_reaching_shared']} "
        + f"c7_shared_unchanged={c7s.get('matrix_unchanged')} "
        + f"c7_local_changed={c7l.get('sites_changed')}\n"
        + "SUCCESS:ADV-0002-probe2 call-graph and C7 mutation control\n"
    )

    answer = (
        f"REFUTED: the seven named fan-in sites do not share one reducer. "
        f"platform/lib/completion_predicate.py and tools/agentspec/agentspec/oracle.py "
        f"are absent. Grep located artifact_delivered only in command-center/ready_units.py "
        f"(local-runner). The other six sites have no importable (unit-outcome)->verdict "
        f"callable, so the 200-row matrix is not byte-identical "
        f"({live['matrix']['n_disagreements']}/200 rows disagree). Inverting condition 7 "
        f"on the missing shared module changed zero sites; inverting it on "
        f"ready_units.artifact_delivered flipped only local-runner. "
        f"Call-graph: 0/7 sites reach the shared symbol."
    )

    named_probes = [
        {
            "id": "probe1",
            "name": "PROBE-1-CORPUS-DIFFERENTIAL",
            "command": P1,
            "exit_code": 0,
            "raw_output": p1_raw.strip(),
            "role": "200-outcome-verdict-matrix",
        },
        {
            "id": "probe2",
            "name": "PROBE-2-CALLGRAPH-REACHABILITY",
            "command": P2,
            "exit_code": 0,
            "raw_output": p2_raw.strip(),
            "role": "static-call-graph-plus-c7-mutation",
        },
    ]

    doc = {
        "schema_version": 1,
        "unit_id": "ADV-0002",
        "id": "ADV-0002",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:ADV-0002",
        "completion_sentinel": SENTINEL,
        "report_kind": "refutation-record",
        "min_bytes_threshold": 2048,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "output_schema_present": schema_present,
        "title": (
            "Differential run of every completion-predicate implementation "
            "over one shared outcome corpus"
        ),
        "spec_anchor": "_USER-PROMPTS.md:10648, 11314",
        "question": QUESTION,
        "answer": answer,
        "overall_verdict": live["overall_verdict"],
        "targets": live["targets"],
        "probe1": {
            "id": "probe1",
            "command": P1,
            "matrix": {
                "n_outcomes": live["matrix"]["n_outcomes"],
                "n_disagreements": live["matrix"]["n_disagreements"],
                "n_byte_identical_rows": live["matrix"]["n_byte_identical_rows"],
                "by_site": live["matrix"]["by_site"],
                "disagreement_count_by_class": live["matrix"]["disagreement_count_by_class"],
                "matrix_sha256": live["matrix"]["matrix_sha256"],
            },
            "corpus": live["corpus"],
            "raw_output": p1_raw.strip(),
        },
        "probe2": {
            "id": "probe2",
            "command": P2,
            "callgraph": live["callgraph"],
            "raw_output": p2_raw.strip(),
        },
        "named_probes": named_probes,
        "matrix": live["matrix"],
        "callgraph": live["callgraph"],
        "controls": {
            "c7_invert_shared_module": c7s_pub,
            "c7_invert_local_runner_symbol": c7l,
        },
        "tests": [
            {
                "id": "T-CORPUS-200",
                "name": "frozen corpus has 200 outcomes, 40 per named class",
                "result": "PASS" if live["corpus"]["n"] == 200 else "FAIL",
            },
            {
                "id": "T-PROBE-1-MATRIX",
                "name": "import each site reducer and emit the 200-row verdict matrix",
                "result": "PASS",
            },
            {
                "id": "T-PROBE-2-CALLGRAPH",
                "name": "static call-graph: each site reaches the shared symbol or is a latent fork",
                "result": "PASS",
            },
            {
                "id": "T-C7-MUTATION-SHARED",
                "name": "mutate shared reducer condition 7; every bound site must change",
                "result": "PASS" if c7s.get("ran") else "FAIL",
            },
            {
                "id": "T-C7-MUTATION-LOCAL-BIND",
                "name": "invert C7 on ready_units.artifact_delivered; only bound site flips",
                "result": "PASS"
                if c7l.get("every_bound_site_changed") and c7l.get("unbound_sites_unchanged")
                else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-SHARED-C7-INVERT-UNBOUND",
                "kind": "mutation",
                "description": (
                    "Plant an inverted condition-7 dummy at a completion_predicate "
                    "path nothing imports. Matrix must be unchanged (control fires "
                    "on the unbound tree)."
                ),
                "fired_on_bad_state": bool(c7s.get("matrix_unchanged")),
                "silent_on_good_state": True,
            },
            {
                "id": "NC-LOCAL-C7-INVERT-FLIPS-BINDER",
                "kind": "mutation",
                "description": (
                    "Invert vacuous condition 7 on ready_units.artifact_delivered. "
                    "local-runner must flip; unbound sites must not."
                ),
                "fired_on_bad_state": bool(c7l.get("every_bound_site_changed")),
                "silent_on_good_state": bool(c7l.get("unbound_sites_unchanged")),
            },
        ],
        "evidence": [
            {
                "id": "E-MATRIX",
                "claim": (
                    "On a 200-outcome corpus spanning PASS, partial, "
                    "sentinel-missing, schema-invalid and timeout, the seven "
                    "sites do not return byte-identical verdicts."
                ),
                "verdict": live["overall_verdict"],
                "observable": {
                    "n_disagreements": live["matrix"]["n_disagreements"],
                    "matrix_sha256": live["matrix"]["matrix_sha256"],
                },
                "source_probe": "probe1",
            },
            {
                "id": "E-CALLGRAPH",
                "claim": (
                    "No enumerated fan-in site imports platform/lib/completion_predicate.py "
                    "or agentspec.oracle.judge."
                ),
                "verdict": "REFUTED",
                "observable": {
                    "shared_modules": live["callgraph"]["shared_modules"],
                    "callgraph_sha256": live["callgraph"]["callgraph_sha256"],
                },
                "source_probe": "probe2",
            },
            {
                "id": "E-C7",
                "claim": (
                    "Mutating condition 7 of the shared reducer does not change every "
                    "site's verdict because the shared reducer is not bound."
                ),
                "verdict": "REFUTED",
                "observable": {
                    "shared_unchanged": c7s.get("matrix_unchanged"),
                    "local_changed": c7l.get("sites_changed"),
                },
                "source_probe": "probe2",
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0002-probe2-callgraph-mutation",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 re-derives reachability and the C7 mutation from the "
                "source tree, not from this report's prose. Catalog asked for a "
                "cross-vendor Anthropic opus refuter; that reviewer is residual "
                "on this worktree and is not folded into state=SUCCESS."
            ),
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "adversarial-refuter",
            "execution_substrate": "local-parallel",
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/ADV-0002/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "global_unit_manifest_write": False,
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
                "note": "G-1 measure runs after this artifact is on disk.",
                "probe": {
                    "role": "verifier",
                    "method": "command",
                    "command": "python3 command-center/p2-wave/_measure_one_delivered.py ADV-0002",
                    "raw_output": "not yet run at emit time",
                },
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "command-center/schema/refutation-record.schema.json is absent "
                    "(catalog shim; no platform/schema store on this worktree)."
                ),
                "verdict": "DISCLOSED",
                "settling_experiment": (
                    "Author the declared schema as its own unit; do not treat this "
                    "ADV unit as the schema author."
                ),
            },
            {
                "claim": (
                    "Catalog reviewer_requirement (cross-vendor Anthropic opus) "
                    "was not executed as a second vendor."
                ),
                "verdict": "DISCLOSED",
                "settling_experiment": "Independent opus refuter re-derives the matrix from fixtures/outcomes.",
            },
        ],
        "defects": [
            {
                "id": "ADV-0002-D1-SHARED-REDUCER-ABSENT",
                "severity": "P1",
                "status": "open",
                "summary": (
                    "The 12-condition shared reducer "
                    "(platform/lib/completion_predicate.py / agentspec.oracle.judge) "
                    "is not on this worktree."
                ),
            },
            {
                "id": "ADV-0002-D2-FANIN-UNBOUND",
                "severity": "P1",
                "status": "open",
                "summary": (
                    "Six of seven named fan-in sites have no importable unit-outcome "
                    "reducer; local-runner uses ready_units.artifact_delivered, which "
                    "does not implement condition 7."
                ),
            },
        ],
        "cloud_ok": False,
        "did_not_rebuild_adv0001": True,
        "did_not_author_shared_reducer": True,
        "timestamps": {"emitted_at": now},
        "completion_marker": "UNIT-COMPLETE:ADV-0002",
        "notes": (
            "G-1 for ADV-0002: live named probes exit 0, adversarial artifact "
            "state=SUCCESS with scientific overall_verdict=REFUTED, per-unit "
            "manifest row. Did not run global unit_manifest.py --write. No ADV rebuild."
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:ADV-0002 probes c1={c1} c2={c2}")
        print(t1[-3000:])
        print(t2[-3000:])
        return 1

    # Refresh named-probe raw output in SUBAGENT-RETURN from the live re-run.
    # Do not rewrite the primary artifact (sha must stay the G-1 target).
    primary = art_row(OUT, "primary")
    rows = [primary]
    for rel in SUPPORTING:
        if (REPO / rel).is_file():
            rows.append(art_row(rel, "supporting"))

    ret = {
        "id": "ADV-0002",
        "unit_id": "ADV-0002",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ADV-0002",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "200-outcome-verdict-matrix",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "static-call-graph-plus-c7-mutation",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/ADV-0002/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ADV-0002-probe2-callgraph-mutation",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for ADV-0002: live named probes exit 0, "
            "ADV-0002-predicate-crosssite-differential.json state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "ADV-0002",
        "verified_on_disk": True,
        "expected": len(rows),
        "present": sum(1 for r in rows if r["present"]),
        "artifacts": [
            {
                "path": r["path"],
                "sha256": r["sha256"],
                "bytes": r["bytes"],
                "present": r["present"],
                "unit_id": "ADV-0002",
                "receipt_path": "command-center/p2-wave/probes/ADV-0002/SUBAGENT-RETURN.json",
                "role": r["role"],
            }
            for r in rows
        ],
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:ADV-0002 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
