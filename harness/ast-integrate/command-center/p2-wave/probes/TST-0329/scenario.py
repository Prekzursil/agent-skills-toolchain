"""Healthy fixture plus twelve single-condition mutations."""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable

from conditions import (
    ARTIFACT_REL,
    CONDITION_IDS,
    CONDITION_TEXT,
    EVIDENCE_REL,
    MANIFEST_REL,
    MIN_BYTES,
    SCHEMA_REL,
    SENTINEL,
)
from reducer import reduce_completion, sha256_bytes

SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["state", "artifact_id"],
    "properties": {
        "state": {"type": "string", "enum": ["SUCCESS", "COMPLETE"]},
        "artifact_id": {"type": "string", "pattern": "^art-"},
        "sentinel": {"type": "string"},
        "export": {"type": "object"},
        "padding": {"type": "string"},
    },
}


def _write_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _artifact_doc(*, sentinel: str, artifact_id: str, consumer: str, padding: str) -> dict[str, Any]:
    return {
        "artifact_id": artifact_id,
        "state": "SUCCESS",
        "sentinel": sentinel,
        "export": {"for_consumer": consumer},
        "padding": padding,
    }


def _obs_template() -> dict[str, Any]:
    return {
        "exit_code": 0,
        "terminal_state": "SUCCESS",
        "artifact_rel": ARTIFACT_REL,
        "schema_rel": SCHEMA_REL,
        "min_bytes": MIN_BYTES,
        "sentinel": SENTINEL,
        "evidence_rels": [EVIDENCE_REL],
        "tests": [{"id": "t-self", "result": "PASS"}],
        "negative_controls": [
            {
                "id": "nc-broken-detector",
                "fired_on_bad": True,
                "silent_on_good": True,
            }
        ],
        "reviewer": {
            "reviewer_id": "independent-fresh-context",
            "verdict": "PASS",
            "independent": True,
        },
        "defects": [],
        "manifest_rel": MANIFEST_REL,
    }


def materialize_healthy(root: Path) -> dict[str, Any]:
    obs = _obs_template()
    (root / "evidence").mkdir(parents=True, exist_ok=True)
    (root / "out").mkdir(parents=True, exist_ok=True)
    (root / EVIDENCE_REL).write_text("anchor: live both-states control\n", encoding="utf-8")
    _write_json(root / SCHEMA_REL, SCHEMA)
    doc = _artifact_doc(
        sentinel=SENTINEL,
        artifact_id="art-healthy-001",
        consumer="consumer:downstream-ok",
        padding="x" * 800,
    )
    _write_json(root / ARTIFACT_REL, doc)
    digest = sha256_bytes((root / ARTIFACT_REL).read_bytes())
    _write_json(
        root / MANIFEST_REL,
        {
            "schema_version": 1,
            "artifacts": [
                {
                    "path": ARTIFACT_REL,
                    "sha256": digest,
                    "present": True,
                }
            ],
        },
    )
    return obs


def _rewrite_artifact(root: Path, **fields: Any) -> None:
    path = root / ARTIFACT_REL
    data = json.loads(path.read_text(encoding="utf-8"))
    data.update(fields)
    _write_json(path, data)


def _refresh_manifest(root: Path) -> None:
    path = root / ARTIFACT_REL
    digest = sha256_bytes(path.read_bytes()) if path.is_file() else "0" * 64
    _write_json(
        root / MANIFEST_REL,
        {
            "schema_version": 1,
            "artifacts": [
                {"path": ARTIFACT_REL, "sha256": digest, "present": path.is_file()}
            ],
        },
    )


def mut_c1(root: Path, obs: dict[str, Any]) -> None:
    obs["terminal_state"] = "RUNNING"


def mut_c2(root: Path, obs: dict[str, Any]) -> None:
    """Named :10646 case: exit 0, artifact gone."""
    obs["exit_code"] = 0
    (root / ARTIFACT_REL).unlink()


def mut_c3(root: Path, obs: dict[str, Any]) -> None:
    _rewrite_artifact(root, padding="")
    _refresh_manifest(root)


def mut_c4(root: Path, obs: dict[str, Any]) -> None:
    _rewrite_artifact(root, artifact_id=123)
    _refresh_manifest(root)


def mut_c5(root: Path, obs: dict[str, Any]) -> None:
    _rewrite_artifact(root, sentinel="NOT-THE-REQUIRED-SENTINEL")
    _refresh_manifest(root)


def mut_c6(root: Path, obs: dict[str, Any]) -> None:
    obs["evidence_rels"] = ["evidence/does-not-exist.txt"]


def mut_c7(root: Path, obs: dict[str, Any]) -> None:
    obs["tests"] = [{"id": "t-self", "result": "FAIL"}]


def mut_c8(root: Path, obs: dict[str, Any]) -> None:
    obs["negative_controls"] = [
        {
            "id": "nc-broken-detector",
            "fired_on_bad": False,
            "silent_on_good": True,
        }
    ]


def mut_c9(root: Path, obs: dict[str, Any]) -> None:
    obs["reviewer"] = {
        "reviewer_id": "self",
        "verdict": "NOT-REVIEWED",
        "independent": False,
    }


def mut_c10(root: Path, obs: dict[str, Any]) -> None:
    obs["defects"] = [
        {"id": "D-P0", "severity": "P0", "status": "open", "summary": "blocker"}
    ]


def mut_c11(root: Path, obs: dict[str, Any]) -> None:
    _write_json(
        root / MANIFEST_REL,
        {
            "schema_version": 1,
            "artifacts": [
                {
                    "path": ARTIFACT_REL,
                    "sha256": "deadbeef" * 8,
                    "present": True,
                }
            ],
        },
    )


def mut_c12(root: Path, obs: dict[str, Any]) -> None:
    _rewrite_artifact(root, export={})
    _refresh_manifest(root)


MUTATIONS: list[dict[str, Any]] = [
    {
        "id": "C1",
        "mutation": "terminal_state set to RUNNING (non-terminal)",
        "apply": mut_c1,
    },
    {
        "id": "C2",
        "mutation": (
            "exit_code=0 and artifact unlinked "
            "(_USER-PROMPTS.md:10646 exit-zero-missing-artifact)"
        ),
        "apply": mut_c2,
        "named_10646": True,
    },
    {
        "id": "C3",
        "mutation": "padding stripped so artifact bytes < min_bytes",
        "apply": mut_c3,
    },
    {
        "id": "C4",
        "mutation": "artifact_id coerced to integer (schema wants string)",
        "apply": mut_c4,
    },
    {
        "id": "C5",
        "mutation": "required sentinel replaced with a decoy token",
        "apply": mut_c5,
    },
    {
        "id": "C6",
        "mutation": "evidence_rels pointed at a missing anchor file",
        "apply": mut_c6,
    },
    {
        "id": "C7",
        "mutation": "recorded test result flipped to FAIL",
        "apply": mut_c7,
    },
    {
        "id": "C8",
        "mutation": "negative control fired_on_bad set false (inert detector)",
        "apply": mut_c8,
    },
    {
        "id": "C9",
        "mutation": "reviewer.verdict NOT-REVIEWED and independent=false",
        "apply": mut_c9,
    },
    {
        "id": "C10",
        "mutation": "open P0 defect attached",
        "apply": mut_c10,
    },
    {
        "id": "C11",
        "mutation": "manifest sha256 replaced with a plausible but wrong digest",
        "apply": mut_c11,
    },
    {
        "id": "C12",
        "mutation": "export.for_consumer removed (downstream cannot read handle)",
        "apply": mut_c12,
    },
]


def _run_one(apply: Callable[..., None] | None) -> dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(prefix="tst0329-"))
    try:
        obs = materialize_healthy(tmp)
        if apply is not None:
            apply(tmp, obs)
        verdict = reduce_completion(obs, tmp)
        skip_id = None
        skip_verdict = None
        return {"root": str(tmp), "obs": obs, "verdict": verdict}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_one(apply: Callable[..., None] | None) -> dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(prefix="tst0329-"))
    try:
        obs = materialize_healthy(tmp)
        if apply is not None:
            apply(tmp, obs)
        return reduce_completion(obs, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_one_with_skip(apply: Callable[..., None], skip_cid: str) -> dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(prefix="tst0329-skip-"))
    try:
        obs = materialize_healthy(tmp)
        apply(tmp, obs)
        return reduce_completion(obs, tmp, skip=frozenset({skip_cid}))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_conformance() -> dict[str, Any]:
    healthy = run_one(None)
    table = []
    independence = []
    holes_detected = []
    ok = True
    if healthy.get("verdict") != "TRUE" or healthy.get("failing_condition_ids"):
        ok = False

    for spec in MUTATIONS:
        live = run_one(spec["apply"])
        failing = list(live.get("failing_condition_ids") or [])
        unsat = [
            c["id"]
            for c in live.get("conditions") or []
            if c.get("result") == "UNSATISFIED"
        ]
        independent = unsat == [spec["id"]]
        reducer_false = live.get("verdict") == "FALSE"
        skip = run_one_with_skip(spec["apply"], spec["id"])
        hole = skip.get("verdict") == "TRUE"
        row = {
            "condition": spec["id"],
            "condition_text": CONDITION_TEXT[spec["id"]],
            "mutation": spec["mutation"],
            "reducer_verdict": live.get("verdict"),
            "failing_condition_ids": failing,
            "named_10646": bool(spec.get("named_10646")),
        }
        table.append(row)
        independence.append(
            {
                "condition": spec["id"],
                "unsatisfied": unsat,
                "exactly_one": independent,
                "skip_k_verdict": skip.get("verdict"),
                "skip_k_exposes_hole": hole,
            }
        )
        holes_detected.append(
            {
                "condition": spec["id"],
                "full_reducer_false": reducer_false,
                "skip_condition_true": hole,
            }
        )
        if not reducer_false or not independent or not hole:
            ok = False

    c2 = next(r for r in table if r["condition"] == "C2")
    if not c2.get("named_10646") or c2.get("reducer_verdict") != "FALSE":
        ok = False

    if len(table) != 12:
        ok = False

    return {
        "pass": ok,
        "healthy_verdict": healthy.get("verdict"),
        "healthy_failing": healthy.get("failing_condition_ids"),
        "table": table,
        "independence": independence,
        "hole_detector": holes_detected,
        "n_mutations": len(table),
        "n_false": sum(1 for r in table if r["reducer_verdict"] == "FALSE"),
        "named_10646_is_c2": True,
        "condition_ids": list(CONDITION_IDS),
    }
