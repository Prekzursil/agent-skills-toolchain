#!/usr/bin/env python3
"""Emit WFA-0145 recall-control artifact plus per-unit receipts.

Does not run tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import recall as R  # noqa: E402
import scout as S  # noqa: E402

UID = "WFA-0145"
OUT = "command-center/foundry/WFA-0145-scout-anti-rebuild-recall-control-with-a-planted-kno.json"
SCHEMA = "command-center/schema/foundry-artifact.schema.json#/$defs/recall-control"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0145/probe1_known_present_absent.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0145/probe2_rebuild_bias_recount.py"
)
QUESTION = (
    "Prove the scout is not blind before trusting any 'nothing found' answer: "
    "plant a known-superior existing workflow in the searchable corpus, issue a "
    "goal it satisfies, and require the scout to return it. Question: what is "
    "the scout's measured recall on a set of planted known-present items, and "
    "does it ever recommend BUILD when a superior existing workflow is present?"
)
WFA0143 = "command-center/foundry/WFA-0143-workflow-scout-executable-search-rank-and-provenance.json"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path)
    return {
        "path": rel,
        "sha256": digest,
        "bytes": size,
        "present": True,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/WFA-0145/SUBAGENT-RETURN.json",
        "role": role,
    }


def supporting_paths() -> list[str]:
    rels = [
        "command-center/p2-wave/probes/WFA-0145/scout.py",
        "command-center/p2-wave/probes/WFA-0145/recall.py",
        "command-center/p2-wave/probes/WFA-0145/probe1_known_present_absent.py",
        "command-center/p2-wave/probes/WFA-0145/probe2_rebuild_bias_recount.py",
        "command-center/p2-wave/probes/WFA-0145/fixtures/plants.json",
    ]
    for path in sorted((HERE / "fixtures" / "corpus").rglob("*.json")):
        rels.append(path.resolve().relative_to(REPO.resolve()).as_posix())
    return rels


def main() -> int:
    live = R.measure(mode="live")
    empty = R.measure(mode="always-empty")
    same = R.measure(mode="always-same")
    if not live["pass"]:
        print("FAILED:WFA-0145 live recall did not pass", live["miss_list"])
        return 1

    wfs = S.load_workflows()
    wfa0143_present = (REPO / WFA0143).is_file()
    schema_present = (
        REPO / "command-center/schema/foundry-artifact.schema.json"
    ).is_file()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    planted_only = [
        r
        for r in live["known_present"]
        if r["source_class"] != "registry"
    ]
    existing_only = [
        r for r in live["known_present"] if r["source_class"] == "registry"
    ]

    answer = (
        "Measured recall on planted known-present items is "
        + f"{sum(1 for r in planted_only if r['found'])}/{len(planted_only)} "
        + "with miss_list=[]. An additional existing (not planted here) registry "
        + f"incumbent wf-kept-stage-gate was {'found' if existing_only and existing_only[0]['found'] else 'MISSED'}. "
        + f"Known-absent goals ({len(live['known_absent'])}) returned empty ranked sets. "
        + "BUILD was never recommended while a superior covering workflow was present "
        + f"({len(live['build_when_superior_present'])} violations). "
        + (
            "WFA-0143 scout artifact is PRESENT; this control still measures the "
            "file-walking scout at probes/WFA-0145/scout.py."
            if wfa0143_present
            else (
                "WFA-0143 scout artifact is ABSENT on this worktree; this control "
                "measures command-center/p2-wave/probes/WFA-0145/scout.py walking "
                "fixtures/corpus (plants are files, not index injections)."
            )
        )
        + " Live 284-candidate registry from harness-restore is unread. "
        + "SUCCESS:WFA-0145"
    )

    doc = {
        "kind": "RecallControl",
        "unit_id": UID,
        "id": UID,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0145",
        "completion_sentinel": "SUCCESS:WFA-0145",
        "output_schema": SCHEMA,
        "schema_file_present": schema_present,
        "question": QUESTION,
        "answer": answer,
        "scout_under_test": {
            "implementation": "command-center/p2-wave/probes/WFA-0145/scout.py",
            "discovery": "walk fixtures/corpus/**/*.json; parse workflow objects and registry candidates",
            "plants_injected_into_index": False,
            "wfa0143_artifact": WFA0143,
            "wfa0143_present": wfa0143_present,
            "source_classes": list(S.SOURCE_CLASSES),
            "workflows_scanned": len(wfs),
            "workflow_ids": [w["id"] for w in wfs],
            "superior_min": S.SUPERIOR_MIN,
        },
        "recall": {
            "planted": live["planted"],
            "found": live["found"],
            "recall_fraction": live["recall_fraction"],
            "miss_list": live["miss_list"],
            "known_absent_all_empty": live["known_absent_all_empty"],
            "known_absent_nonempty": live["known_absent_nonempty"],
            "planted_source_classes": [r["source_class"] for r in planted_only],
            "existing_registry_found": bool(existing_only and existing_only[0]["found"]),
        },
        "anti_rebuild": {
            "build_when_superior_present": live["build_when_superior_present"],
            "ranked_below_rebuild": live["ranked_below_rebuild"],
            "rule": (
                "BUILD only when the ranked set has no covering workflow with "
                f"quality_score >= {S.SUPERIOR_MIN}; otherwise ADOPT and cite the incumbent id"
            ),
        },
        "known_present": live["known_present"],
        "known_absent": live["known_absent"],
        "detector_controls": {
            "always_empty": {
                "found": empty["found"],
                "pass": empty["pass"],
                "discriminates_present_absent": empty["discriminates_present_absent"],
            },
            "always_same": {
                "found": same["found"],
                "known_absent_all_empty": same["known_absent_all_empty"],
                "pass": same["pass"],
                "discriminates_present_absent": same["discriminates_present_absent"],
            },
            "live_discriminates_present_absent": live["discriminates_present_absent"],
        },
        "evidence": {
            "A": (
                "rerunnable: PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/WFA-0145/probe1_known_present_absent.py "
                "(live found/planted vs always-empty and always-same mutants)"
            ),
            "B": (
                "rerunnable: PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/WFA-0145/probe2_rebuild_bias_recount.py "
                "(independent file:line token grep plus BUILD flip when the superior plant is excluded)"
            ),
        },
        "tests": [
            {
                "id": "T1-present-and-absent",
                "name": "find planted known-present AND return empty for known-absent",
                "command": P1,
                "result": "PENDING",
            },
            {
                "id": "T2-anti-rebuild-and-independent-recount",
                "name": "never BUILD while superior present; token recount at file:line",
                "command": P2,
                "result": "PENDING",
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0145-probe2-rebuild-bias-recount",
            "verdict": "PENDING",
            "independent": True,
            "note": (
                "Mechanical: independent corpus grep plus both-states BUILD flip. "
                "Not a second vendor."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "WFA-0143 executable scout artifact is absent; recall is measured "
                    "against the file-walking scout shipped with this unit."
                ),
                "verdict": "NOT-CHECKED" if not wfa0143_present else "CHECKED",
                "settling_experiment": (
                    "Re-run probe1/probe2 against the WFA-0143 scout once that artifact exists."
                ),
            },
            {
                "claim": (
                    "The catalog cites 08-WORKFLOW-CANDIDATE-REGISTRY.json#candidates (284). "
                    "This worktree has a 2-candidate fixture copy only; live 284 is unread."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Point scout.CORPUS at the live harness-restore registry and re-measure recall."
                ),
            },
        ],
        "environment": {
            "os": platform.platform(),
            "python": sys.version.split()[0],
            "cwd": str(REPO),
            "ts": now,
        },
        "produced_by": {
            "execution_substrate": "local-serialized-linux",
            "role": "adversarial-refuter",
        },
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    rc1, t1 = run_cmd(P1)
    rc2, t2 = run_cmd(P2)
    print(f"probe1 rc={rc1}")
    print(t1[-2500:])
    print(f"probe2 rc={rc2}")
    print(t2[-2500:])
    if rc1 != 0 or rc2 != 0:
        print("FAILED:WFA-0145 emit probes")
        return 1

    doc["tests"][0]["result"] = "PASS"
    doc["tests"][1]["result"] = "PASS"
    doc["reviewer"]["verdict"] = "PASS"
    out_path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    rc1b, t1b = run_cmd(P1)
    rc2b, t2b = run_cmd(P2)
    if rc1b != 0 or rc2b != 0:
        print("FAILED:WFA-0145 emit re-run after stamp")
        print(t1b[-1500:])
        print(t2b[-1500:])
        return 1

    digest, size = sha256_file(out_path)
    if size < 1024:
        print(f"FAILED:WFA-0145 artifact too small {size}")
        return 1
    if "SUCCESS:WFA-0145" not in out_path.read_text(encoding="utf-8"):
        print("FAILED:WFA-0145 sentinel missing after write")
        return 1

    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0145",
        "registered": True,
        "cloud_ok": False,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "measure_line": None,
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": rc1b, "raw_output": t1b},
            {"id": "probe2", "command": P2, "exit_code": rc2b, "raw_output": t2b},
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": digest,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/WFA-0145/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "WFA-0145-probe2-rebuild-bias-recount",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for WFA-0145: live named probes exit 0, recall-control artifact "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
    }
    artifacts = [row(OUT, "primary")] + [row(p, "supporting") for p in supporting_paths()]
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
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:WFA-0145 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
