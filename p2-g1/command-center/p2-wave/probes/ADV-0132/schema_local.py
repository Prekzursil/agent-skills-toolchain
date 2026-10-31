"""Offline validator for command-center/schema/divergence-report.schema.json.

The shim $ref targets https://ast-integrate.invalid/... which has no DNS.
Populate a disk store and never fetch.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/divergence-report.schema.json"
SHIM_URI = (
    "https://ast-integrate.invalid/command-center/schema/divergence-report.schema.json"
)
STORE_FILES = {
    SHIM_URI: REPO / SCHEMA_REL,
    "https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json": (
        REPO / "platform/schema/artifact-class-profiles.schema.json"
    ),
    "https://ast-integrate.invalid/platform/schema/receipt.schema.json": (
        REPO / "platform/schema/receipt.schema.json"
    ),
}
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {"unit_id": "ADV-0132", "state": "SUCCESS"},
    {
        "schema_version": 1,
        "unit_id": "ADV-0132",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ADV-0132 placeholder",
        "spec_anchor": "_USER-PROMPTS.md:11198",
        "min_bytes_threshold": 1,
        "artifacts": [
            {
                "path": "a",
                "bytes": 1,
                "sha256": "a" * 64,
                "exists": True,
            }
        ],
        "evidence": [
            {
                "claim": "c",
                "verdict": "NOT-CHECKED",
                "anchor": "a",
                "probes": [
                    {
                        "role": "source",
                        "method": "file-read",
                        "command": "x",
                        "raw_output": "y",
                        "fingerprint": "z",
                    }
                ],
            }
        ]
        * 2,
        "timestamps": {
            "started_at": "2026-08-25T00:00:00Z",
            "ended_at": "2026-08-25T00:00:00Z",
        },
        "retry": {"count": 0, "policy": "zero retries first observation is verdict"},
        "tests": [{"id": "t", "command": "c", "result": "PASS"}],
        "negative_controls": [
            {
                "id": "n",
                "kind": "mutation",
                "description": "d",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            }
        ],
        "reviewer": {
            "reviewer_id": "r",
            "verdict": "PASS",
            "independent": True,
        },
        "manifest_registration": {"registered": True, "manifest_path": "m"},
        "downstream_consumers": [
            {
                "consumer": "c",
                "artifact_path": "p",
                "executed": True,
                "read_ok": True,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": "x",
                    "raw_output": "y",
                    "fingerprint": "q",
                },
            }
        ],
        "residual_unknowns": [
            {
                "claim": "c",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "s",
            }
        ],
        "report": {
            "kind": "not-a-divergence-report",
            "observations": [
                {"name": "n", "measured": 1, "method": "m", "anchor": "a"}
            ],
            "control_ids": ["c1"],
        },
    },
)


def _load_jsonschema():
    saved = list(sys.path)
    sys.path[:] = [
        p for p in saved if p not in ("", ".") and Path(p).resolve() != REPO
    ]
    sys.modules.pop("platform", None)
    try:
        from jsonschema import Draft202012Validator, RefResolver  # type: ignore

        return Draft202012Validator, RefResolver
    finally:
        sys.path[:] = saved


Draft202012Validator, RefResolver = _load_jsonschema()


def load_store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for uri, path in STORE_FILES.items():
        doc = json.loads(path.read_text(encoding="utf-8"))
        store[uri] = doc
        sid = doc.get("$id")
        if isinstance(sid, str) and sid:
            store[sid] = doc
    return store


def validator() -> Any:
    store = load_store()
    schema = store[SHIM_URI]
    resolver = RefResolver(base_uri=SHIM_URI, referrer=schema, store=store)
    return Draft202012Validator(schema, resolver=resolver)


def errors(doc: Any) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def garbage_rejected() -> bool:
    return all(bool(errors(g)) for g in GARBAGE)


def payload(doc: dict) -> dict:
    """Overlay report fields so probes can read conclusions/headline/etc."""
    if not isinstance(doc, dict):
        return {}
    out = dict(doc)
    report = doc.get("report")
    if isinstance(report, dict):
        out.update(report)
    return out


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def artifact_row(rel: str, role: str) -> dict[str, Any]:
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }
