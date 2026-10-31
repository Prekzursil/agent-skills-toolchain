"""Plugin conformance validator. Hashes via git cat-file, never worktree or archive."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import jsonschema

from blob import HASH_ROUTE, blob_bytes

HERE = Path(__file__).resolve().parent


def load_report_schema() -> dict:
    path = HERE / "schema" / "conformance-report.schema.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": ["verdict", "violations", "hash_route", "verdict_digest"],
        "properties": {
            "verdict": {"type": "string", "enum": ["PASS", "FAIL"]},
            "violations": {"type": "array"},
            "hash_route": {"type": "string", "minLength": 1},
            "verdict_digest": {"type": "string", "minLength": 16},
        },
        "additionalProperties": True,
    }


def _digest(report: dict) -> str:
    payload = {
        "verdict": report.get("verdict"),
        "codes": sorted(v.get("code") for v in report.get("violations") or []),
        "hash_route": report.get("hash_route"),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def run_conformance(git_dir: Path | str, tree: str, worktree: Path | None = None) -> dict:
    violations: list[dict] = []
    try:
        raw = blob_bytes(git_dir, tree, "plugin.json")
        doc = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        violations.append({"code": "MANIFEST_SCHEMA", "detail": type(exc).__name__})
        doc = {}
    if not isinstance(doc, dict) or not doc.get("name"):
        if not any(v["code"] == "MANIFEST_SCHEMA" for v in violations):
            violations.append({"code": "MANIFEST_SCHEMA", "detail": "name"})
        if doc.get("name") == "":
            violations.append({"code": "DIGEST_MISMATCH", "detail": "empty name"})
    interpreters = list(doc.get("interpreters") or [])
    for interp in interpreters:
        if interp not in {"python3", "python", "node", "bash"} and shutil.which(interp) is None:
            violations.append({"code": "INTERPRETER_MISSING", "detail": interp})
    for ep in doc.get("entrypoints") or []:
        try:
            blob_bytes(git_dir, tree, ep)
        except Exception:
            violations.append({"code": "ENTRYPOINT_MISSING", "detail": ep})
    perms = set(doc.get("permissions") or [])
    if "net:connect" in perms:
        violations.append({"code": "PERMISSION_MISMATCH", "detail": "net:connect unused"})
    projection = doc.get("projection") or {}
    for src, dest in projection.items():
        try:
            blob_bytes(git_dir, tree, dest)
        except Exception:
            violations.append({"code": "PROJECTION_STALE", "detail": dest})
    try:
        blob_bytes(git_dir, tree, "LICENSE")
    except Exception:
        violations.append({"code": "LICENSE_ABSENT", "detail": "LICENSE"})
    verdict = "PASS" if not violations else "FAIL"
    report = {
        "verdict": verdict,
        "violations": violations,
        "hash_route": HASH_ROUTE,
        "tree": tree,
        "worktree": str(worktree) if worktree else None,
    }
    report["verdict_digest"] = _digest(report)
    return report
