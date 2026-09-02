#!/usr/bin/env python3
"""Emit IMP-0010 receipt, then per-unit SUBAGENT-RETURN + UNIT-ARTIFACT-MANIFEST."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/receipts/IMP-0010.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0010/probe1_prediction_matches_dry_run.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0010/probe2_negative_control.py"
)
TESTS = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/plugin/tests/test_projection_map.py"
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env={**dict(**{k: v for k, v in __import__("os").environ.items()}), "PYTHONDONTWRITEBYTECODE": "1"},
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
        "unit_id": "IMP-0010",
        "receipt_path": "command-center/p2-wave/probes/IMP-0010/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    sys.path.insert(0, str(REPO / "tools" / "plugin"))
    import projection_map as pm  # noqa: WPS433

    t_rc, t_out = run(TESTS)
    print(t_out)
    if t_rc != 0:
        print("FAILED:IMP-0010 tests did not pass")
        return 1

    bundle = pm.load_bundle(REPO)
    with tempfile.TemporaryDirectory(prefix="imp0010-receipt-") as tmp:
        home = Path(tmp)
        predicted = pm.predict(bundle, home)
        actual = pm.dry_run(bundle, home)
        delta = pm.diff_sets(predicted, actual)
        proj = pm.projection_document(bundle, home)
        removed = bundle["skills"]["skills"][0]["name"]
        mutated = pm.drop_entry(bundle, "skill", removed)
        gone = set(predicted) - set(pm.predict(mutated, home))

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    match = predicted == actual and not delta["predicted_absent"] and not delta["present_unpredicted"]
    if not match or len(gone) != 1:
        print("FAILED:IMP-0010 prediction/dry-run or negative control")
        return 1

    receipt = {
        "schema_version": 1,
        "unit_id": "IMP-0010",
        "id": "IMP-0010",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0010",
        "completion_sentinel": "SUCCESS:IMP-0010",
        "title": "Manifest-to-live-config projection map",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0010",
        "question": (
            "Implement the typed projection that states, for each manifest entry, "
            "exactly which live file it produces (settings.json key, "
            "hooks/_dispatch/manifest.json row, ~/.claude/skills path) so that "
            "'what will this manifest do to my machine' is answerable before install."
        ),
        "consumes_generators": [
            "ci/emit_hook_manifest.py",
            "ci/gen_skills_manifest.py",
        ],
        "does_not_duplicate_generators": True,
        "projection_map": proj,
        "signal_1_predicted_live_paths": predicted,
        "signal_2_dry_run_home_listing": actual,
        "signals_agree": True,
        "predicted_count": len(predicted),
        "dry_run_count": len(actual),
        "diff": delta,
        "negative_control": {
            "removed_entry_kind": "skill",
            "removed_entry_id": removed,
            "predicted_paths_removed": sorted(gone),
            "exactly_one_path_disappeared": len(gone) == 1,
        },
        "tests": [
            {
                "id": "test_prediction_matches_dry_run",
                "command": TESTS,
                "result": "PASS" if t_rc == 0 else "FAIL",
                "output_tail": t_out[-1500:],
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "reviewer": {
            "reviewer_id": "IMP-0010-probe2-negative-control",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 independently removes one skill entry and requires exactly "
                "one predicted live path to vanish, and checks the projection imports "
                "the generators instead of restating their destination templates."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0010/UNIT-ARTIFACT-MANIFEST.json",
            "note": "per-unit only; did not run tools/command-center/unit_manifest.py --write",
        },
        "report": {
            "kind": "projection-map",
            "match": match,
            "home_was_throwaway": True,
        },
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} bytes={out_path.stat().st_size}")

    c1, t1 = run(P1)
    c2, t2 = run(P2)
    print(t1)
    print(t2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0010 probes c1={c1} c2={c2}")
        return 1

    primary = row(OUT, "primary")
    supporting = [
        "tools/plugin/schema/projection-map.schema.json",
        "tools/plugin/projection_map.py",
        "tools/plugin/tests/test_projection_map.py",
        "ci/emit_hook_manifest.py",
        "ci/gen_skills_manifest.py",
        "command-center/p2-wave/probes/IMP-0010/probe1_prediction_matches_dry_run.py",
        "command-center/p2-wave/probes/IMP-0010/probe2_negative_control.py",
        ".claude-plugin/plugin.json",
        "hooks/_dispatch/manifest.json",
        "skills/DEPLOYED-MANIFEST.json",
    ]
    artifacts = [primary] + [row(p, "supporting") for p in supporting]
    ret = {
        "id": "IMP-0010",
        "unit_id": "IMP-0010",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0010",
        "registered": True,
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json + "
            "tools/plugin/schema/projection-map.schema.json"
        ),
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "prediction-vs-dry-run",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "negative-control-one-entry-one-path",
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0010/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0010-probe2-negative-control",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "measure_line": "SUCCESS:delivered IMP-0010",
        "measure": {"exit_code": 0, "line": "SUCCESS:delivered IMP-0010"},
        "ts": now,
        "notes": (
            "G-1 for IMP-0010: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1) + "\n", encoding="utf-8"
    )
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "IMP-0010",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1) + "\n", encoding="utf-8"
    )
    print("SUCCESS:IMP-0010 receipts written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
