#!/usr/bin/env python3
"""Build evaluation observations: synthetic 12-condition fixtures + live receipts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX = HERE / "fixtures"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _json(path: Path, doc: Any) -> None:
    _write(path, json.dumps(doc, indent=2, sort_keys=True) + "\n")


def ensure_fixtures() -> dict[str, str]:
    """Create on-disk artifacts the clean-room predicate can stat and parse."""
    FIX.mkdir(parents=True, exist_ok=True)
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": ["id", "sentinel", "unit_id"],
        "properties": {
            "id": {"type": "string", "minLength": 1},
            "sentinel": {"type": "string", "minLength": 8},
            "unit_id": {"type": "string", "minLength": 3},
            "note": {"type": "string"},
        },
        "additionalProperties": True,
    }
    _json(FIX / "artifact.schema.json", schema)

    def body(uid: str, sentinel: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        doc = {
            "id": uid,
            "sentinel": sentinel,
            "unit_id": "CNF-0170",
            "note": "synthetic fixture for CNF-0170 clean-room coverage; padding="
            + ("x" * 80),
        }
        if extra:
            doc.update(extra)
        return doc

    healthy = body("FIX-HEALTHY", "SUCCESS:CNF-0170-FIXTURE")
    _json(FIX / "healthy.json", healthy)
    _json(FIX / "healthy-evidence.json", {"anchor": "exists", "pad": "y" * 80})

    _json(
        FIX / "mention-only.json",
        body(
            "FIX-MENTION",
            "NOPE",
            extra={
                "prose": "example: the sentinel is SUCCESS:CNF-0170-FIXTURE in this sentence",
                "sentinel": "NOT-THE-TOKEN",
            },
        ),
    )
    _json(FIX / "invalid.json", {"totally": "unrelated", "passing_tests": 999999, "pad": "z" * 80})
    (FIX / "empty.json").write_bytes(b"")
    (FIX / "tiny.json").write_bytes(b"{}\n")
    _write(FIX / "not-json.txt", "this is not json but it is long enough to pass the size floor. " * 4)

    sha, nbytes = sha256_file(FIX / "healthy.json")
    _json(
        FIX / "UNIT-ARTIFACT-MANIFEST.json",
        {
            "schema_version": 1,
            "unit_id": "CNF-0170-FIXTURE",
            "artifacts": [
                {
                    "path": "command-center/p2-wave/probes/CNF-0170/fixtures/healthy.json",
                    "sha256": sha,
                    "bytes": nbytes,
                    "present": True,
                    "unit_id": "CNF-0170-FIXTURE",
                }
            ],
        },
    )
    return {
        "healthy": "command-center/p2-wave/probes/CNF-0170/fixtures/healthy.json",
        "schema": "command-center/p2-wave/probes/CNF-0170/fixtures/artifact.schema.json",
        "evidence": "command-center/p2-wave/probes/CNF-0170/fixtures/healthy-evidence.json",
        "manifest": "command-center/p2-wave/probes/CNF-0170/fixtures/UNIT-ARTIFACT-MANIFEST.json",
    }


def _healthy_base(paths: dict[str, str]) -> dict[str, Any]:
    sha, nbytes = sha256_file(REPO / paths["healthy"])
    return {
        "id": "FIX-HEALTHY",
        "repo": str(REPO),
        "state": "SUCCESS",
        "exit_code": 0,  # recorded; clean-room must ignore this as success
        "digest": "deadbeef" * 8,  # plausible digest; not a receipt
        "artifacts": [{"path": paths["healthy"], "role": "primary"}],
        "schema_path": paths["schema"],
        "sentinel": "SUCCESS:CNF-0170-FIXTURE",
        "evidence": [{"path": paths["evidence"]}],
        "tests": [{"id": "t-healthy", "result": "PASS"}],
        "negative_controls": [
            {"id": "nc-c8", "fired_on_bad": True, "silent_on_good": True}
        ],
        "reviewer": {
            "independent": True,
            "verdict": "PASS",
            "reviewer_id": "CNF-0170-fixture-reviewer",
        },
        "defects": [],
        "manifest": {
            "path": paths["healthy"],
            "sha256": sha,
            "bytes": nbytes,
            "registered": True,
            "present": True,
        },
        "consumer_required_fields": ["unit_id", "sentinel"],
    }


def synthetic_cases() -> list[dict[str, Any]]:
    paths = ensure_fixtures()
    healthy = _healthy_base(paths)
    cases: list[dict[str, Any]] = [healthy]

    def mutant(cid: str, n: int, **updates: Any) -> dict[str, Any]:
        row = dict(healthy)
        row["id"] = cid
        row["target_unsatisfied"] = n
        for k, v in updates.items():
            row[k] = v
        return row

    cases.append(mutant("FIX-C1-blocked", 1, state="BLOCKED", exit_code=0))
    cases.append(
        mutant(
            "FIX-C2-absent",
            2,
            artifacts=[{"path": "command-center/p2-wave/probes/CNF-0170/fixtures/no-such.json"}],
        )
    )
    cases.append(
        mutant(
            "FIX-C3-empty",
            3,
            artifacts=[{"path": "command-center/p2-wave/probes/CNF-0170/fixtures/empty.json"}],
        )
    )
    cases.append(
        mutant(
            "FIX-C3-tiny",
            3,
            artifacts=[{"path": "command-center/p2-wave/probes/CNF-0170/fixtures/tiny.json"}],
        )
    )
    cases.append(
        mutant(
            "FIX-C4-invalid",
            4,
            artifacts=[{"path": "command-center/p2-wave/probes/CNF-0170/fixtures/invalid.json"}],
        )
    )
    cases.append(
        mutant(
            "FIX-C5-missing",
            5,
            artifacts=[{"path": "command-center/p2-wave/probes/CNF-0170/fixtures/invalid.json"}],
            sentinel="SUCCESS:CNF-0170-FIXTURE",
        )
    )
    cases.append(
        mutant(
            "FIX-C5-mention",
            5,
            artifacts=[{"path": "command-center/p2-wave/probes/CNF-0170/fixtures/mention-only.json"}],
        )
    )
    cases.append(
        mutant(
            "FIX-C6-missing-anchor",
            6,
            evidence=[{"path": "command-center/p2-wave/probes/CNF-0170/fixtures/no-anchor.json"}],
        )
    )
    cases.append(mutant("FIX-C7-fail", 7, tests=[{"id": "t-fail", "result": "FAIL"}]))
    cases.append(
        mutant(
            "FIX-C8-control-miss",
            8,
            negative_controls=[
                {"id": "nc-c8", "fired_on_bad": False, "silent_on_good": True}
            ],
        )
    )
    cases.append(
        mutant(
            "FIX-C9-self",
            9,
            reviewer={"independent": False, "verdict": "PASS", "reviewer_id": "author"},
        )
    )
    cases.append(
        mutant(
            "FIX-C10-open-p0",
            10,
            defects=[{"id": "D1", "severity": "P0", "status": "OPEN"}],
        )
    )
    cases.append(
        mutant(
            "FIX-C11-unregistered",
            11,
            manifest={
                "path": paths["healthy"],
                "sha256": "0" * 64,
                "bytes": 0,
                "registered": False,
                "present": False,
            },
        )
    )
    cases.append(
        mutant(
            "FIX-C12-unreadable",
            12,
            artifacts=[{"path": "command-center/p2-wave/probes/CNF-0170/fixtures/not-json.txt"}],
            schema_path=paths["schema"],
        )
    )
    return cases


LIVE_RECEIPTS = (
    "command-center/phase3/A2/REFUTATION.json",
    "command-center/phase3/A2/MIGRATION.json",
    "command-center/phase3/A1/FAILURE-MODES.json",
    "command-center/phase3/A1/REFUTATION.json",
)


def _manifest_row(unit_id: str, artifact_rel: str) -> dict[str, Any] | None:
    man = REPO / "command-center/p2-wave/probes" / unit_id / "UNIT-ARTIFACT-MANIFEST.json"
    if not man.is_file():
        return None
    try:
        doc = json.loads(man.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    want = artifact_rel.replace("\\", "/")
    for row in doc.get("artifacts") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("path") or "").replace("\\", "/") == want:
            return row
    return None


def observe_live_receipt(rel: str) -> dict[str, Any] | None:
    path = REPO / rel
    if not path.is_file():
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(doc, dict):
        return None
    unit_id = str(doc.get("unit_id") or doc.get("id") or "")
    sha, nbytes = sha256_file(path)
    man = _manifest_row(unit_id, rel) if unit_id else None
    tests = []
    for t in doc.get("tests") or []:
        if isinstance(t, dict):
            tests.append(
                {
                    "id": t.get("id") or t.get("name"),
                    "result": t.get("result") or t.get("status"),
                }
            )
    evidence = []
    for item in doc.get("evidence") or []:
        if isinstance(item, dict) and item.get("path"):
            evidence.append({"path": str(item["path"]).split(":")[0]})
        elif isinstance(item, str) and ":" in item:
            evidence.append({"path": item.split(":")[0]})
    reviewer = doc.get("reviewer")
    rev = None
    if isinstance(reviewer, dict):
        rev = {
            "independent": bool(reviewer.get("independent")),
            "verdict": reviewer.get("verdict") or reviewer.get("status"),
            "reviewer_id": reviewer.get("reviewer_id") or reviewer.get("id"),
        }
    artifacts = [{"path": rel, "role": "primary"}]
    schema = doc.get("output_schema") or doc.get("$schema")
    schema_path = None
    if isinstance(schema, str) and schema.endswith(".json") and not schema.startswith("http"):
        schema_path = schema.replace("\\", "/")
    man_obs = None
    if man:
        live_sha = sha
        man_obs = {
            "path": rel,
            "sha256": str(man.get("sha256") or ""),
            "bytes": man.get("bytes"),
            "registered": True,
            "present": man.get("present") is True and str(man.get("sha256") or "") == live_sha,
        }
    else:
        man_obs = {
            "path": rel,
            "sha256": sha,
            "bytes": nbytes,
            "registered": False,
            "present": False,
        }
    return {
        "id": f"LIVE-{unit_id or path.stem}",
        "repo": str(REPO),
        "live": True,
        "state": doc.get("state") or doc.get("status"),
        "exit_code": None,
        "artifacts": artifacts,
        "schema_path": schema_path,
        "sentinel": doc.get("sentinel") or "",
        "evidence": evidence or None,
        "tests": tests or None,
        "negative_controls": doc.get("negative_controls"),
        "reviewer": rev,
        "defects": doc.get("defects"),
        "manifest": man_obs,
        "consumer_required_fields": ["unit_id"],
    }


def live_cases() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for rel in LIVE_RECEIPTS:
        row = observe_live_receipt(rel)
        if row:
            out.append(row)
    receipts = REPO / "command-center/receipts"
    if receipts.is_dir():
        for path in sorted(receipts.glob("*.json")):
            rel = path.relative_to(REPO).as_posix()
            if rel.endswith("CNF-0170.json"):
                continue
            row = observe_live_receipt(rel)
            if row:
                out.append(row)
    return out


def all_cases() -> list[dict[str, Any]]:
    return synthetic_cases() + live_cases()
