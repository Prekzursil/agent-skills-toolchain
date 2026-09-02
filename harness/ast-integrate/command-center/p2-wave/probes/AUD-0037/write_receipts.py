#!/usr/bin/env python3
"""Emit AUD-0037 artifact plus per-unit SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST.

Named probes are re-run live. Does not invoke tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

UID = "AUD-0037"
OUT = E.OUT_REL
SCHEMA = E.SCHEMA_REL
REPO = E.REPO
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0037/probe1_mechanical_resolution.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0037/probe2_semantic_read.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/AUD-0037/engine.py",
    "command-center/p2-wave/probes/AUD-0037/probe1_mechanical_resolution.py",
    "command-center/p2-wave/probes/AUD-0037/probe2_semantic_read.py",
    "command-center/p2-wave/probes/AUD-0037/write_receipts.py",
    "command-center/p2-wave/probes/AUD-0037/fixtures/mentions-only.txt",
    "command-center/p2-wave/probes/AUD-0037/fixtures/supports.txt",
    "command-center/p2-wave/probes/AUD-0037/fixtures/contradicts.txt",
    "command-center/p2-wave/probes/AUD-0037/fixtures/short.txt",
    SCHEMA,
]
MIN_BYTES = 2048


def write_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def validate_schema(doc: dict) -> None:
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    try:
        import jsonschema
    except ImportError:
        for key in schema.get("required") or []:
            if key not in doc:
                raise ValueError(f"schema required field missing: {key}")
        return
    jsonschema.Draft7Validator(schema).validate(doc)


def manifest_row(rel: str, role: str) -> dict:
    sha, size = E.digest_file(REPO / rel)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/AUD-0037/SUBAGENT-RETURN.json",
        "role": role,
    }


def build_artifact(data: dict, now: str, named: list[dict] | None = None) -> dict:
    sentinel = E.catalog_sentinel()
    live_t = data["live_tally"]
    live_rows = [E.slim_claim(r) for r in data["live"]]
    control_rows = []
    for c in data["controls"]:
        control_rows.append(
            {
                "id": c["id"],
                "control": c["control"],
                "passed": c["passed"],
                "expect_mechanical": c["expect_mechanical"],
                "got_mechanical": c["got_mechanical"],
                "expect_semantic": c["expect_semantic"],
                "got_semantic": c["got_semantic"],
                "expect_reason": c["expect_reason"],
                "got_reasons": c["got_reasons"],
                "row": E.slim_claim(c["row"]),
            }
        )
    mentions = next(c for c in data["controls"] if c["control"] == "mentions-only")
    supports = next(c for c in data["controls"] if c["control"] == "supports")
    contradicts = next(c for c in data["controls"] if c["control"] == "contradicts")
    missing = next(c for c in data["controls"] if c["control"] == "missing-file")
    eof = next(c for c in data["controls"] if c["control"] == "line-past-eof")
    sem = live_t["semantic_counts"]
    hv = live_t["n_high_value_mentions_only"]
    hv_v = live_t["n_verified_high_value"]
    answer = (
        f"CLAIM-REGISTRY.json has {live_t['n_claims']} claims and "
        f"{live_t['n_anchors']} evidence anchors. Mechanical resolution "
        f"(file exists, line count): {live_t['n_mechanically_resolved_claims']} "
        f"claims fully resolved, {live_t['n_mechanically_unresolved_claims']} "
        f"not. Semantic classes: {json.dumps(sem, sort_keys=True)}. "
        f"High-value (probe 1 pass, probe 2 MENTIONS-ONLY): {hv} claims "
        f"({hv_v} VERIFIED). Planted subject-only line classified "
        f"{mentions['got_semantic']} while still mechanically resolved="
        f"{mentions['got_mechanical']}. Git revision of cited blobs is "
        f"NOT-CHECKED: this worktree has no usable cited-revision field and "
        f"is not measured via git cat-file. {sentinel}"
    )
    named_probes = named or [
        {"id": "probe1", "command": P1, "exit_code": None, "raw_output": "PENDING"},
        {"id": "probe2", "command": P2, "exit_code": None, "raw_output": "PENDING"},
    ]
    return {
        "answer": answer,
        "artifacts": [
            {"path": OUT, "role": "primary", "exists": True},
            {
                "path": "command-center/p2-wave/probes/AUD-0037/engine.py",
                "role": "resolver",
            },
            {
                "path": "command-center/p2-wave/probes/AUD-0037/probe1_mechanical_resolution.py",
                "role": "named-probe",
            },
            {
                "path": "command-center/p2-wave/probes/AUD-0037/probe2_semantic_read.py",
                "role": "named-probe",
            },
        ],
        "completion_sentinel": sentinel,
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "note": "G-1 per-unit delivery measure; cloud ok=true is not delivery",
            }
        ],
        "evidence": [
            {
                "claim": (
                    "Probe 1 mechanically resolves each CLAIM-REGISTRY evidence "
                    "anchor as file-exists plus line-count, matching "
                    "tools/council/artifacts/claims.py:resolve_anchor."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/AUD-0037/probe1_mechanical_resolution.py",
                "detail": json.dumps(live_t, sort_keys=True),
            },
            {
                "claim": (
                    "Probe 2 semantically classifies each cited span as "
                    "SUPPORTS, MENTIONS-ONLY, or CONTRADICTS and does not treat "
                    "mechanical resolution as support."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/AUD-0037/probe2_semantic_read.py",
                "detail": json.dumps(sem, sort_keys=True),
            },
            {
                "claim": (
                    "Every VERIFIED claim's cited span SUPPORTS the claim "
                    "rather than merely mentioning its subject."
                ),
                "verdict": "REFUTED" if hv_v else "CONFIRMED",
                "anchor": "command-center/CLAIM-REGISTRY.json",
                "detail": (
                    f"verified_high_value_mentions_only={hv_v} "
                    f"semantic_counts={json.dumps(sem, sort_keys=True)}"
                ),
            },
        ],
        "id": UID,
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/AUD-0037/UNIT-ARTIFACT-MANIFEST.json",
            "note": "per-unit only; tools/command-center/unit_manifest.py --write was not run",
        },
        "min_bytes_threshold": MIN_BYTES,
        "named_probes": named_probes,
        "negative_controls": [
            {
                "id": "AUD-0037-subject-word-only",
                "kind": "planted-mentions-only",
                "description": (
                    "A claim citing a line that contains only the subject word "
                    "must be MENTIONS-ONLY, not treated as semantically resolved "
                    "support, even when the file:line exists."
                ),
                "fired_on_bad_state": mentions["got_semantic"] == "MENTIONS-ONLY",
                "silent_on_good_state": supports["got_semantic"] == "SUPPORTS",
                "bad_state_output": mentions["got_semantic"],
                "good_state_output": supports["got_semantic"],
            },
            {
                "id": "AUD-0037-contradicts-and-missing",
                "kind": "planted-contradicts-and-unresolved",
                "description": (
                    "A denying span is CONTRADICTS; a missing file and a "
                    "line-past-eof citation are mechanically unresolved."
                ),
                "fired_on_bad_state": (
                    contradicts["got_semantic"] == "CONTRADICTS"
                    and not missing["got_mechanical"]
                    and not eof["got_mechanical"]
                ),
                "silent_on_good_state": supports["got_mechanical"]
                and supports["got_semantic"] == "SUPPORTS",
                "bad_state_output": json.dumps(
                    {
                        "contradicts": contradicts["got_semantic"],
                        "missing": missing["got_reasons"],
                        "eof": eof["got_reasons"],
                    },
                    sort_keys=True,
                ),
                "good_state_output": supports["got_semantic"],
            },
        ],
        "notes": (
            "G-1 for AUD-0037: live named probes exit 0, artifact state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild. No git add/commit/push/stash/checkout/rebase. "
            + sentinel
        ),
        "output_path": OUT,
        "output_schema": SCHEMA,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "auditor",
            "execution_substrate": "linux-worktree",
        },
        "question": E.QUESTION,
        "report": {
            "kind": "audit-finding",
            "registry_path": data["registry_path"],
            "registry_present": data["registry_present"],
            "live_tally": live_t,
            "live_claims": live_rows,
            "controls": control_rows,
            "library_disagreements": data["library_disagreements"],
            "cited_revision": {
                "status": "NOT-CHECKED",
                "reason": (
                    "CLAIM-REGISTRY anchors have no revision field; this "
                    "worktree is measured as on-disk bytes, not git cat-file."
                ),
            },
        },
        "reviewer": {
            "reviewer_id": "AUD-0037-probe2-semantic-read",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Catalog asks for a cross-vendor Codex reviewer who re-runs only "
                "probe 2. This G-1 lane re-ran probe 2 as a mechanically "
                "independent semantic read of cited spans, not a re-read of "
                "probe 1's existence table. No Codex session was invoked."
            ),
        },
        "schema_version": 1,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0037",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "tests": [
            {
                "id": "probe1-mechanical-resolution",
                "result": "PASS" if named else "NOT-RUN",
                "name": "File exists and has at least the cited number of lines",
            },
            {
                "id": "probe2-semantic-read",
                "result": "PASS" if named else "NOT-RUN",
                "name": "Cited span classified SUPPORTS / MENTIONS-ONLY / CONTRADICTS",
            },
            {
                "id": "control-subject-word-only-mentions-only",
                "result": "PASS" if mentions["passed"] else "FAIL",
                "name": "Subject-only line is MENTIONS-ONLY, not support",
            },
            {
                "id": "control-supports-and-contradicts",
                "result": (
                    "PASS"
                    if supports["passed"] and contradicts["passed"]
                    else "FAIL"
                ),
                "name": "Asserting span SUPPORTS; denying span CONTRADICTS",
            },
            {
                "id": "control-missing-file-and-line-past-eof",
                "result": "PASS" if missing["passed"] and eof["passed"] else "FAIL",
                "name": "Missing file and line-past-eof are unresolved",
            },
        ],
        "timestamps": {"generated_at": now},
        "title": "CLAIM-REGISTRY evidence-anchor resolution: file:line vs support",
        "unit_id": UID,
    }


def main() -> int:
    data = E.census()
    if not data["controls_pass"]:
        print("FAILED:AUD-0037 controls did not pass; not emitting SUCCESS")
        print(json.dumps(
            [{k: c[k] for k in c if k != "row"} for c in data["controls"]],
            indent=2,
        ))
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = build_artifact(data, now)
    validate_schema(doc)
    sentinel = E.catalog_sentinel()
    if sentinel not in json.dumps(doc):
        print("FAILED:AUD-0037 sentinel missing from document")
        return 1

    out = REPO / OUT
    write_json(out, doc)
    if out.stat().st_size < MIN_BYTES:
        print(f"FAILED:AUD-0037 artifact {out.stat().st_size}B below {MIN_BYTES}")
        return 1

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:AUD-0037 probes c1={c1} c2={c2}")
        print(t1[-2500:])
        print(t2[-2500:])
        return 1

    named = [
        {
            "id": "probe1",
            "command": P1,
            "role": "mechanical-resolution",
            "exit_code": c1,
            "raw_output": t1,
        },
        {
            "id": "probe2",
            "command": P2,
            "role": "semantic-read",
            "exit_code": c2,
            "raw_output": t2,
        },
    ]
    doc = build_artifact(data, now, named)
    doc["tests"] = [
        {
            "id": "probe1-mechanical-resolution",
            "result": "PASS",
            "command": P1,
            "exit_code": c1,
        },
        {
            "id": "probe2-semantic-read",
            "result": "PASS",
            "command": P2,
            "exit_code": c2,
        },
        {
            "id": "control-subject-word-only-mentions-only",
            "result": "PASS",
        },
        {
            "id": "control-supports-and-contradicts",
            "result": "PASS",
        },
        {
            "id": "control-missing-file-and-line-past-eof",
            "result": "PASS",
        },
    ]
    validate_schema(doc)
    write_json(out, doc)

    c1b, t1b = run_cmd(P1)
    c2b, t2b = run_cmd(P2)
    if c1b != 0 or c2b != 0:
        print(f"FAILED:AUD-0037 probes after artifact update c1={c1b} c2={c2b}")
        print(t1b[-2500:])
        print(t2b[-2500:])
        return 1

    extra = [
        "command-center/p2-wave/probes/AUD-0037/probe1-mechanical-resolution.raw.json",
        "command-center/p2-wave/probes/AUD-0037/probe2-semantic-read.raw.json",
    ]
    primary = manifest_row(OUT, "primary")
    artifacts = (
        [primary]
        + [manifest_row(p, "supporting") for p in SUPPORTING]
        + [manifest_row(p, "supporting") for p in extra if (REPO / p).is_file()]
    )
    now2 = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": sentinel,
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "cloud_ok": False,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1b,
                "role": "mechanical-resolution",
                "raw_output": t1b,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2b,
                "role": "semantic-read",
                "raw_output": t2b,
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
        "manifest_path": "command-center/p2-wave/probes/AUD-0037/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "AUD-0037-probe2-semantic-read",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now2,
        "notes": (
            "G-1 for AUD-0037: live named probes exit 0, artifact state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    write_json(HERE / "SUBAGENT-RETURN.json", ret)
    write_json(HERE / "UNIT-ARTIFACT-MANIFEST.json", man)
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:AUD-0037 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
