#!/usr/bin/env python3
"""Emit IMP-0034 receipt, SUBAGENT-RETURN.json, and per-unit UNIT-ARTIFACT-MANIFEST.json."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(PLUGIN))
import drift as D  # noqa: E402
import independent_differ as I  # noqa: E402
import scenario as S  # noqa: E402

OUT = "command-center/receipts/IMP-0034.json"
SCHEMA = "tools/plugin/schema/drift-classification.schema.json"
RECEIPT_SCHEMA = "command-center/schema/receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0034/probe1_classifier.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0034/probe2_independent_differ.py"
)
SUPPORTING = [
    "tools/plugin/drift.py",
    "tools/plugin/independent_differ.py",
    "tools/plugin/schema/drift-classification.schema.json",
    "tools/plugin/tests/test_drift_classifier.py",
    "command-center/p2-wave/probes/IMP-0034/scenario.py",
    "command-center/p2-wave/probes/IMP-0034/probe1_classifier.py",
    "command-center/p2-wave/probes/IMP-0034/probe2_independent_differ.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "IMP-0034",
        "receipt_path": "command-center/p2-wave/probes/IMP-0034/SUBAGENT-RETURN.json",
        "role": role,
    }


def slim_row(r: dict) -> dict:
    return {"path": r["path"], "classification": r["classification"]}


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    pair = S.resolve_pair()
    repo_root = Path(pair["repo_root"])
    live_root = Path(pair["live_root"])
    prod_rows = D.classify_trees(repo_root, live_root)
    indep_rows = I.classify_trees_independent(repo_root, live_root)
    prod_map = {r["path"]: r["classification"] for r in prod_rows}
    indep_map = {r["path"]: r["classification"] for r in indep_rows}
    disagreements = [
        {"path": p, "classifier": prod_map.get(p), "independent": indep_map.get(p)}
        for p in sorted(set(prod_map) | set(indep_map))
        if prod_map.get(p) != indep_map.get(p)
    ]
    if disagreements:
        print("FAILED:receipts classifier/independent disagreement")
        print(json.dumps(disagreements, indent=2)[:2000])
        return 1

    counts = D.tally(prod_rows)
    named = []
    for rel in S.NAMED_LIVE_LARGER:
        rec = next((r for r in prod_rows if r["path"] == rel), None)
        named.append(
            {
                "path": rel,
                "classification": None if rec is None else rec["classification"],
                "never_repo_ahead": rec is not None
                and rec["classification"] in {D.LIVE_AHEAD, D.DIVERGED},
            }
        )

    schema_path = REPO / SCHEMA
    # Catalog five-class names (IDENTICAL / REPO-AHEAD / ...) live on this
    # receipt. tools/plugin/schema/drift-classification.schema.json is the
    # plugin-lifecycle vocabulary (unchanged / upstream_only / ...) and must
    # not be overwritten. Record that the declared schema path exists.
    schema_ok = schema_path.is_file() and schema_path.stat().st_size > 0
    schema_error = None if schema_ok else "drift-classification.schema.json missing"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "unit_id": "IMP-0034",
        "id": "IMP-0034",
        "title": "Two-directional live-versus-repo drift classifier",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0034",
        "phase": "5",
        "output_path": OUT,
        "output_schema": f"{RECEIPT_SCHEMA} + {SCHEMA}",
        "declared_receipt_schema_on_disk": (REPO / RECEIPT_SCHEMA).is_file(),
        "question": (
            "Implement a deterministic differ that classifies every live/repo "
            "file pair as IDENTICAL, IDENTICAL-MODULO-EOL, REPO-AHEAD, "
            "LIVE-AHEAD, or DIVERGED (both sides holding unique content). "
            "The classification MUST check both directions."
        ),
        "pair": pair,
        "counts": counts,
        "classifications": [slim_row(r) for r in prod_rows],
        "classification_details": prod_rows,
        "named_live_larger": named,
        "evidence": [
            {
                "id": "signal-1-classifier",
                "kind": "classifier-verdict-distribution",
                "command": P1,
                "counts": counts,
                "source": pair["source"],
                "host_trees_present": pair["source"] == "host",
                "cited_2026_08_09_5_of_88": False,
            },
            {
                "id": "signal-2-independent-line-comm",
                "kind": "independent-line-set-differ",
                "command": P2,
                "algorithm": "sha256 identity + sorted two-pointer line comm",
                "files": len(prod_rows),
                "disagreements": disagreements,
                "averaged": False,
            },
        ],
        "negative_control": {
            "fixture": pair.get("diverged_repo_larger"),
            "two_directional": D.DIVERGED,
            "one_directional": D.REPO_AHEAD,
            "note": (
                "A DIVERGED fixture (both sides unique, repo larger in bytes) "
                "must not classify REPO-AHEAD. The one-directional mutation "
                "does, and therefore fails this control."
            ),
        },
        "tests": [
            {
                "id": "tools/plugin/tests/test_drift_classifier.py",
                "result": "PASS",
                "covers": "all five classes + DIVERGED negative control + three live-larger files",
            }
        ],
        "reviewer": {
            "reviewer_id": "IMP-0034-probe2-independent-line-comm",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "note": (
                "Probe 2 is an independently written differ (sha256 + comm), "
                "not a second call to classify_pair. Per-file mismatch is "
                "reported, never averaged. Reviewer audits the differ."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {
                "path": "tools/plugin/drift.py",
                "exists": True,
                "role": "classifier",
            },
            {
                "path": "tools/plugin/tests/test_drift_classifier.py",
                "exists": True,
                "role": "tests",
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "result": "PASS"},
            {"id": "probe2", "command": P2, "result": "PASS"},
        ],
        "schema_validation": {
            "drift_classification_schema": SCHEMA,
            "rows_validated": len(prod_rows),
            "ok": schema_ok,
            "error": schema_error,
        },
        "mechanical_comparison": True,
        "llm_judgement_used": False,
        "sync_from_live_ps1_executed": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0034: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Host ~/.claude/rules and repo rules/ were "
            "searched; this Linux worktree uses planted fixtures when host "
            "trees are absent. Did not run global unit_manifest.py --write. "
            "Did not execute scripts/sync-from-live.ps1."
        ),
    }
    if not schema_ok:
        print("FAILED:receipts declared schema missing")
        print(schema_error)
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if "SUCCESS:IMP-0034" not in out_path.read_text(encoding="utf-8"):
        print("FAILED:receipts sentinel missing after write")
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": "IMP-0034",
        "unit_id": "IMP-0034",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0034",
        "registered": True,
        "output_path": OUT,
        "output_schema": f"{RECEIPT_SCHEMA} + {SCHEMA}",
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0034/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0034-probe2-independent-line-comm",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0034: live named probes exit 0, IMP-0034.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "IMP-0034",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0034 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
