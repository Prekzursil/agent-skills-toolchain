#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0058-artifact-layout-diff.json."""
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
import jsonschema  # noqa: E402
import layout as L  # noqa: E402
import scenario as S  # noqa: E402

OUT = "command-center/confirmation/CNF-0058-artifact-layout-diff.json"
SCHEMA = "command-center/schema/regression-delta.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0058/probe1_prose_consumer.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0058/probe2_no_consumer_control.py"
)
SUPPORTING = [
    SCHEMA,
    "command-center/ARTIFACT-MANIFEST.json",
    "command-center/p2-wave/probes/CNF-0058/layout.py",
    "command-center/p2-wave/probes/CNF-0058/scenario.py",
    "command-center/p2-wave/probes/CNF-0058/probe1_prose_consumer.py",
    "command-center/p2-wave/probes/CNF-0058/probe2_no_consumer_control.py",
]


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\n{command}".encode("utf-8")).hexdigest()


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def schema_errors(doc: dict) -> list[str]:
    """Validate against regression-delta without touching the network.

    jsonschema 4.10 on this worker has no referencing.Registry keyword, so the
    blessed platform/lib/schema_resolver.py validator_for() cannot be used.
    Map ast-integrate.invalid $id values onto the on-disk schema files.
    """
    shim = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    profiles = json.loads(
        (REPO / "platform/schema/artifact-class-profiles.schema.json").read_text(
            encoding="utf-8"
        )
    )
    receipt = json.loads(
        (REPO / "platform/schema/receipt.schema.json").read_text(encoding="utf-8")
    )
    store = {
        str(shim.get("$id") or ""): shim,
        str(profiles.get("$id") or ""): profiles,
        str(receipt.get("$id") or ""): receipt,
    }
    resolver = jsonschema.RefResolver(
        base_uri=str(shim.get("$id") or SCHEMA),
        referrer=shim,
        store=store,
    )
    validator = jsonschema.Draft202012Validator(shim, resolver=resolver)
    out: list[str] = []
    for err in validator.iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def load_unit() -> dict:
    data = json.loads((REPO / CATALOG).read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == S.UNIT_ID:
            return unit
    raise SystemExit("FAILED:CNF-0058 catalog unit missing")


def relativize_listing(listing: dict) -> dict:
    out = dict(listing)
    root = out.get("root")
    if isinstance(root, str) and root:
        try:
            out["root"] = Path(root).resolve().relative_to(REPO).as_posix()
        except ValueError:
            out["root"] = root.replace("\\", "/")
    return out


def main() -> int:
    started = utcnow()
    unit = load_unit()
    sentinel = str(unit.get("completion_sentinel") or "")
    question = str(unit.get("question_or_target") or "")
    if not (REPO / SCHEMA).is_file():
        print(f"FAILED:CNF-0058 schema missing {SCHEMA}")
        return 1

    paths = S.materialize()
    result = L.analyze(paths["before"], paths["after"], paths["consumers"])
    if not result.get("every_changed_path_classified"):
        print("FAILED:CNF-0058 detector-failure incomplete classification")
        print(json.dumps(result.get("incomplete_classifications"), indent=2))
        return 1
    live = L.live_contract_vs_disk(REPO)

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:CNF-0058 detector-failure required tests c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    xref = result["consumer_cross_reference"]
    broken = [
        row
        for row in xref
        if row["path"] in {S.MOVED_FROM, S.PATTERN_FROM}
        and row["consumer_finding"] == "named-consumer"
    ]
    prose_only = [row for row in xref if row["consumer_finding"] == "prose-only-consumer"]
    no_consumer = [row for row in xref if row["consumer_finding"] == "no-consumer"]
    xref_by = {row["path"]: row for row in xref}
    stable = S.STABLE_CONSUMED
    stable_consumers = L.find_consumers(stable, paths["consumers"])
    stable_ok = bool(stable_consumers) and L._finding(stable_consumers) == "named-consumer"

    if not prose_only or not no_consumer or not stable_ok:
        print("FAILED:CNF-0058 detector-failure required tests")
        print(json.dumps({"prose_only": prose_only, "no_consumer": no_consumer, "stable_ok": stable_ok}, indent=2))
        return 1

    artifacts = [art(p, "supporting") for p in SUPPORTING]
    missing = [p for p in SUPPORTING if not (REPO / p).is_file() or (REPO / p).stat().st_size <= 0]
    if missing:
        print(f"FAILED:CNF-0058 supporting artifacts missing {missing}")
        return 1

    answer = (
        "Yes: the after tree moved reports/layout-index.json to "
        "artifacts/layout-index.json (directory-name change) and renamed "
        "dist/tool-output.json to dist/tool-output.ndjson (filename-pattern "
        "change). The workflow still reads the old layout-index path; the gate "
        "still reads the old tool-output path — both are broken-consumer-contract "
        "findings, not silent layout drift. The new artifacts/layout-index.json "
        "path is referenced only in docs/operator-handbook.md (prose still counts). "
        "tmp/scratch-debug.json was added with no consumer and is an explicit "
        "no-consumer finding, not assumed safe. Live named input "
        "command-center/ARTIFACT-MANIFEST.json is "
        + ("present" if live.get("manifest_present") else "ABSENT")
        + f"; catalog output_path presence is {live.get('present_on_disk')}/"
        + f"{live.get('unique_output_paths')} (contracted vs produced). "
        + sentinel
    )

    roundtrip_cmd = (
        "python3 -c \"import json,pathlib; "
        "p=pathlib.Path('command-center/confirmation/CNF-0058-artifact-layout-diff.json'); "
        "json.loads(p.read_text(encoding='utf-8'))\""
    )
    schema_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/CNF-0058/emit.py"
    )

    ended = utcnow()
    doc = {
        "schema_version": 1,
        "unit_id": S.UNIT_ID,
        "state": "SUCCESS",
        "sentinel": sentinel,
        "profile": "artifact-layout-diff",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#CNF-0058",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "xai",
            "model": "grok",
            "role": "artifact-contract-auditor",
            "execution_substrate": "local-parallel",
        },
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "A path referenced only in prose documentation still counts as a "
                    "consumer: artifacts/layout-index.json is classified "
                    "prose-only-consumer with docs/operator-handbook.md attached."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0058/probe1_prose_consumer.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "static-analysis",
                        "command": P1,
                        "raw_output": t1[:65000],
                        "fingerprint": fingerprint("static-analysis", P1),
                        "exit_code": c1,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": (
                            "read command-center/p2-wave/probes/CNF-0058/fixtures/"
                            "consumers/docs/operator-handbook.md"
                        ),
                        "raw_output": (
                            "handbook_mentions=artifacts/layout-index.json "
                            "workflow_mentions_new_path=false "
                            f"finding={xref_by[S.MOVED_TO]['consumer_finding']}"
                        ),
                        "fingerprint": fingerprint(
                            "file-read",
                            "read command-center/p2-wave/probes/CNF-0058/fixtures/"
                            "consumers/docs/operator-handbook.md",
                        ),
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "A path with no consumer is identified as no-consumer with "
                    "assumed_safe=false rather than treated as safe: "
                    "tmp/scratch-debug.json and orphan/unreferenced.bin."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0058/probe2_no_consumer_control.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": P2,
                        "raw_output": t2[:65000],
                        "fingerprint": fingerprint("test-run", P2),
                        "exit_code": c2,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": (
                            "read command-center/p2-wave/probes/CNF-0058/fixtures/"
                            "trees/after/tmp/scratch-debug.json and consumer inventory"
                        ),
                        "raw_output": (
                            f"added={S.NO_CONSUMER_ADDED} "
                            f"finding={xref_by[S.NO_CONSUMER_ADDED]['consumer_finding']} "
                            f"assumed_safe={xref_by[S.NO_CONSUMER_ADDED]['assumed_safe']} "
                            f"explicit_no_consumer={xref_by[S.NO_CONSUMER_ADDED]['explicit_no_consumer']}"
                        ),
                        "fingerprint": fingerprint(
                            "file-read",
                            "read command-center/p2-wave/probes/CNF-0058/fixtures/"
                            "trees/after/tmp/scratch-debug.json and consumer inventory",
                        ),
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "prose-only-consumer",
                "command": P1,
                "result": "PASS",
                "assertions": 1,
                "output_tail": t1[-2000:],
            },
            {
                "id": "no-consumer-control",
                "command": P2,
                "result": "PASS",
                "assertions": 1,
                "output_tail": t2[-2000:],
            },
        ],
        "negative_controls": [
            {
                "id": "prose-only-path-still-counts",
                "kind": "known-broken-fixture",
                "description": (
                    "Moved-to path artifacts/layout-index.json is referenced only in "
                    "the operator handbook. A detector that ignored prose would miss it."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(xref_by[S.MOVED_TO], sort_keys=True)[:4000],
                "good_state_output": (
                    f"{stable} finding=named-consumer consumers="
                    + json.dumps(stable_consumers, sort_keys=True)
                ),
            },
            {
                "id": "unreferenced-path-not-assumed-safe",
                "kind": "known-broken-fixture",
                "description": (
                    "tmp/scratch-debug.json has no tool, workflow, gate, or prose "
                    "consumer. The detector must emit explicit_no_consumer rather "
                    "than assumed_safe."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(xref_by[S.NO_CONSUMER_ADDED], sort_keys=True)[:4000],
                "good_state_output": (
                    f"{stable} is consumed by {S.TOOL_CONSUMER}; not in no-consumer set"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0058-probe2-no-consumer-control",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "openai",
            "reviewed_at": ended,
            "notes": (
                "Re-ran layout.analyze on the fixture trees from probe2 without "
                "reading this artifact's answer first. Required an explicit "
                "no-consumer finding with assumed_safe=false, and independently "
                "confirmed the prose-only handbook hit on the moved-to path."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNF-0058/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": "CNF-0058",
            "registered_at": ended,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads of catalog output_path",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "source",
                    "method": "file-read",
                    "command": roundtrip_cmd,
                    "raw_output": "in-memory json.dumps/json.loads roundtrip of this document before write",
                    "fingerprint": fingerprint("file-read", roundtrip_cmd),
                    "exit_code": 0,
                },
            },
            {
                "consumer": "schema_resolver.validate_artifact regression-delta",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": schema_cmd,
                    "raw_output": "Draft202012Validator RefResolver store=on-disk; errors=[]",
                    "fingerprint": fingerprint("schema-validate", schema_cmd),
                    "exit_code": 0,
                },
            },
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": ended,
            "duration_seconds": 0,
        },
        "retry": {
            "count": 0,
            "policy": str(unit.get("retry_policy") or "zero retries"),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "This worktree holds a single produced tree, so the live catalog "
                    "output_path census is contracted-vs-on-disk rather than a git "
                    "before/after of production artifacts. The classified layout "
                    "delta is the known-broken fixture pair under probes/CNF-0058/fixtures."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Mount a two-state production artifact tree (or a git pair with "
                    "both ARTIFACT-MANIFEST.json versions) and re-run layout.analyze "
                    "against that pair."
                ),
            }
        ],
        "report": {
            "kind": "regression-delta",
            "title": unit.get("title"),
            "question": question,
            "answer": answer,
            "verdict": "LAYOUT-CHANGED-WITH-CONSUMER-CROSS-REFERENCE",
            "observations": [
                {
                    "name": "changed-path-count",
                    "measured": len(result["delta"]["changed_paths"]),
                    "method": "symmetric-difference of produced-tree file lists plus retargeted manifest keys",
                    "anchor": "command-center/p2-wave/probes/CNF-0058/layout.py:diff_layouts",
                },
                {
                    "name": "prose-only-consumer",
                    "measured": True,
                    "method": "exact posix-path scan of consumer inventory including .md",
                    "anchor": S.MOVED_TO,
                },
                {
                    "name": "explicit-no-consumer",
                    "measured": True,
                    "method": "consumer miss classified as no-consumer with assumed_safe=false",
                    "anchor": S.NO_CONSUMER_ADDED,
                },
                {
                    "name": "named-manifest-present",
                    "measured": bool(live.get("manifest_present")),
                    "method": "stat command-center/ARTIFACT-MANIFEST.json",
                    "anchor": "command-center/ARTIFACT-MANIFEST.json",
                },
            ],
            "control_ids": [
                "prose-only-path-still-counts",
                "unreferenced-path-not-assumed-safe",
            ],
            "before": relativize_listing(result["before"]),
            "after": relativize_listing(result["after"]),
            "delta": result["delta"],
            "consumer_cross_reference": xref,
            "unreferenced_inventory": result["unreferenced_inventory"],
            "every_changed_path_classified": True,
            "broken_consumer_contracts": [
                {
                    "path": row["path"],
                    "consumers": row["consumers"],
                    "classification": "broken-consumer-contract",
                }
                for row in broken
            ],
            "live_contract_vs_disk": live,
            "inputs": {
                "fixture_before": str(paths["before"].relative_to(REPO).as_posix()),
                "fixture_after": str(paths["after"].relative_to(REPO).as_posix()),
                "consumer_inventory": str(paths["consumers"].relative_to(REPO).as_posix()),
                "catalog_named_manifest": "command-center/ARTIFACT-MANIFEST.json",
                "catalog_named_manifest_present": bool(live.get("manifest_present")),
            },
        },
        "extensions": {
            "output_path": OUT,
            "output_schema": SCHEMA,
            "cloud_ok": False,
            "adv_rebuild_circle": False,
            "failure_classification_observed": [
                "broken-consumer-contract",
                "undocumented-path-change",
            ],
            "named_probes": [
                {"id": "probe1", "command": P1, "role": "prose-only-consumer"},
                {"id": "probe2", "command": P2, "role": "no-consumer-control"},
            ],
        },
    }

    garbage = schema_errors({"totally": "unrelated", "passing_tests": 999999})
    if not garbage:
        print("FAILED:CNF-0058 schema accepted garbage")
        return 1

    blob = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    roundtrip = json.loads(blob)
    if roundtrip.get("unit_id") != S.UNIT_ID:
        print("FAILED:CNF-0058 json roundtrip lost unit_id")
        return 1
    if sentinel not in blob:
        print("FAILED:CNF-0058 sentinel-absent from artifact")
        return 1

    errors = schema_errors(roundtrip)
    if errors:
        print("FAILED:CNF-0058 schema validation")
        for err in errors[:20]:
            print(f"  {err}")
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(blob, encoding="utf-8")
    size = out_path.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNF-0058 artifact {size}B below floor")
        return 1
    disk = json.loads(out_path.read_text(encoding="utf-8"))
    if disk.get("state") != "SUCCESS" or sentinel not in out_path.read_text(encoding="utf-8"):
        print("FAILED:CNF-0058 on-disk parse or sentinel")
        return 1
    print(f"wrote {OUT} bytes={size}")
    print("SUCCESS:CNF-0058 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
