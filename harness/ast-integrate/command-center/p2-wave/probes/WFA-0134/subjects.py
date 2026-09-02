"""Golden workflow subject and the 12 per-condition mutants."""
from __future__ import annotations

import hashlib
import inspect
import json
import shutil
from pathlib import Path
from typing import Any

from tools.foundry import completion_predicate as CP

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = (
    "command-center/p2-wave/probes/WFA-0134/fixtures/blueprint.schema.json"
)
SENTINEL = "SUCCESS:wf-golden"
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0134/probe1_mutation.py"
)

GOLDEN_BLUEPRINT = {
    "id": "wf-golden",
    "title": "Golden workflow blueprint for WFA-0134 certification binding",
    "stages": [
        {
            "id": "s1",
            "action": "noop",
            "description": "terminal no-op stage the foundry can dispatch",
        }
    ],
    "certification_sentinel": SENTINEL,
    "roles": ["author"],
    "stop_rule": {"all": ["s1-done"]},
}


def _digest(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def _write_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def _write_manifest(man_path: Path, artifact: Path) -> None:
    _write_json(
        man_path,
        {
            "artifacts": [
                {
                    "path": artifact.as_posix(),
                    "sha256": _digest(artifact),
                    "present": True,
                }
            ]
        },
    )


def evidence_anchors() -> list[dict[str, Any]]:
    line = inspect.getsourcelines(CP.evaluate)[1]
    return [
        {
            "kind": "file:line",
            "path": "tools/foundry/completion_predicate.py",
            "line": line,
            "needle": "def evaluate(",
        },
        {"kind": "command", "command": P1_CMD},
    ]


def base_subject(artifact: Path, manifest: Path) -> dict[str, Any]:
    return {
        "workflow_id": "wf-golden",
        "unit_class": "workflow-artifact",
        "terminal_state": "SUCCESS",
        "artifact_path": artifact.as_posix(),
        "schema_path": SCHEMA_REL,
        "required_sentinel": SENTINEL,
        "min_bytes": CP.MIN_BYTES,
        "evidence": evidence_anchors(),
        "tests": [{"id": "schema-ok", "result": "PASS", "required": True}],
        "mutations": [
            {"id": "c2-absent-file", "fired": True, "expected": "REJECTED"}
        ],
        "reviewer": {
            "reviewer_id": "fixture-independent-reviewer",
            "verdict": "PASS",
            "independent": True,
        },
        "defects": [],
        "manifest_path": manifest.as_posix(),
    }


def materialize_golden(root: Path) -> dict[str, Any]:
    art_dir = root / "golden"
    if art_dir.exists():
        shutil.rmtree(art_dir)
    art_dir.mkdir(parents=True)
    artifact = art_dir / "blueprint.json"
    _write_json(artifact, GOLDEN_BLUEPRINT)
    manifest = art_dir / "manifest.json"
    _write_manifest(manifest, artifact)
    return base_subject(artifact, manifest)


def _clone_golden(root: Path, tag: str) -> tuple[dict[str, Any], Path, Path]:
    src = root / "golden"
    dst = root / tag
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    artifact = dst / "blueprint.json"
    manifest = dst / "manifest.json"
    _write_manifest(manifest, artifact)
    subject = base_subject(artifact, manifest)
    return subject, artifact, manifest


def materialize_mutant(root: Path, cid: int) -> dict[str, Any]:
    if not (root / "golden").is_dir():
        materialize_golden(root)
    tag = f"mutant-c{cid:02d}"
    subject, artifact, manifest = _clone_golden(root, tag)
    subject["workflow_id"] = f"wf-mutant-c{cid:02d}"

    if cid == 1:
        subject["terminal_state"] = "RUNNING"
    elif cid == 2:
        artifact.unlink()
    elif cid == 3:
        artifact.write_text("x\n", encoding="utf-8")
        _write_manifest(manifest, artifact)
    elif cid == 4:
        broken = dict(GOLDEN_BLUEPRINT)
        del broken["stages"]
        _write_json(artifact, broken)
        _write_manifest(manifest, artifact)
    elif cid == 5:
        body = dict(GOLDEN_BLUEPRINT)
        body["certification_sentinel"] = "SUCCESS:near-miss"
        _write_json(artifact, body)
        _write_manifest(manifest, artifact)
    elif cid == 6:
        subject["evidence"] = []
    elif cid == 7:
        subject["tests"] = [{"id": "schema-ok", "result": "FAIL", "required": True}]
    elif cid == 8:
        subject["mutations"] = [
            {"id": "c2-absent-file", "fired": False, "expected": "REJECTED"}
        ]
    elif cid == 9:
        subject["reviewer"] = {
            "reviewer_id": "fixture-independent-reviewer",
            "verdict": "FAIL",
            "independent": True,
        }
    elif cid == 10:
        subject["defects"] = [
            {"id": "DEF-P0-1", "severity": "P0", "resolved": False}
        ]
    elif cid == 11:
        _write_json(
            manifest,
            {
                "artifacts": [
                    {
                        "path": artifact.as_posix(),
                        "sha256": "0" * 64,
                        "present": True,
                    }
                ]
            },
        )
    elif cid == 12:
        body = dict(GOLDEN_BLUEPRINT)
        body["stages"] = [
            {
                "id": "s1",
                "action": "not-a-foundry-action",
                "description": "consumer must refuse this action",
            }
        ]
        _write_json(artifact, body)
        _write_manifest(manifest, artifact)
    else:
        raise ValueError(f"no mutant for condition {cid}")
    return subject


def materialize_provisional(root: Path) -> dict[str, Any]:
    subject, _, _ = _clone_golden(root, "provisional")
    subject["workflow_id"] = "wf-provisional"
    subject["reviewer"] = {
        "reviewer_id": "fixture-independent-reviewer",
        "verdict": "NOT-CHECKED",
        "independent": True,
    }
    return subject


def materialize_exit_zero_missing(root: Path) -> dict[str, Any]:
    dst = root / "exit-zero"
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    missing = dst / "absent-blueprint.json"
    return {
        "workflow_id": "wf-exit-zero",
        "unit_class": "workflow-artifact",
        "exit_code": 0,
        "terminal_state": "SUCCESS",
        "artifact_path": missing.as_posix(),
        "schema_path": SCHEMA_REL,
        "required_sentinel": SENTINEL,
        "evidence": evidence_anchors(),
        "tests": [{"id": "schema-ok", "result": "PASS", "required": True}],
        "mutations": [
            {"id": "c2-absent-file", "fired": True, "expected": "REJECTED"}
        ],
        "reviewer": {
            "reviewer_id": "fixture-independent-reviewer",
            "verdict": "PASS",
            "independent": True,
        },
        "defects": [],
        "manifest_path": (dst / "manifest.json").as_posix(),
    }


def materialize_na_with_reason(root: Path) -> dict[str, Any]:
    """Reducer N/A rendering (not a workflow-artifact skip)."""
    subject, _, _ = _clone_golden(root, "na-reason")
    subject["workflow_id"] = "wf-na-reason"
    subject["unit_class"] = "honor-subject"
    subject["applicability"] = {
        str(i): {"applicable": True} for i in range(1, 13)
    }
    subject["applicability"]["9"] = {
        "applicable": False,
        "reason": "other-unit-class-has-no-independent-reviewer-role",
    }
    return subject


def materialize_unreasoned_na(root: Path) -> dict[str, Any]:
    subject, _, _ = _clone_golden(root, "na-unreasoned")
    subject["workflow_id"] = "wf-na-unreasoned"
    subject["unit_class"] = "honor-subject"
    subject["applicability"] = {
        str(i): {"applicable": True} for i in range(1, 13)
    }
    subject["applicability"]["9"] = {"applicable": False}
    return subject
