#!/usr/bin/env python3
"""Shared harvest/claim helpers for RES-0068 (map-N + barrier / K-of-N)."""
from __future__ import annotations

import base64
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SNAP = HERE / "snapshots"
ARTIFACT_REL = "command-center/research/RES-0068.json"
ARTIFACT = REPO / ARTIFACT_REL
HARVEST_INDEX = HERE / "harvest_index.json"
HARVEST_META = HERE / "harvest_meta.json"
UID = "RES-0068"
SENTINEL = "SUCCESS:RES-0068"
COMPLETION_SENTINEL = (
    "SUCCESS:RES-0068 in the receipt AND quoted barrier policies per engine "
    "plus a named engine exhibiting the local no-timeout pathology"
)
MIN_BYTES = 256
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})

# Snapshot catalog: only files the claims actually cite.
SOURCES: dict[str, dict[str, str]] = {
    "aws_asl_spec.html": {
        "url": "https://states-language.net/spec.html",
        "rail": "R1-structured-spec",
    },
    "aws_sfn_map_distributed.html": {
        "url": "https://docs.aws.amazon.com/step-functions/latest/dg/state-map-distributed.html",
        "rail": "R2-prose",
    },
    "gh_celery_canvas_rst.json": {
        "url": "https://api.github.com/repos/celery/celery/contents/docs/userguide/canvas.rst",
        "rail": "R1-api",
    },
    "celery_canvas_txt": {
        "url": "https://docs.celeryq.dev/en/stable/_sources/userguide/canvas.rst.txt",
        "rail": "R2-prose",
    },
    "gh_celery_config_rst.json": {
        "url": "https://api.github.com/repos/celery/celery/contents/docs/userguide/configuration.rst",
        "rail": "R1-api",
    },
    "celery_config_txt": {
        "url": "https://docs.celeryq.dev/en/stable/_sources/userguide/configuration.rst.txt",
        "rail": "R2-prose",
    },
    "gh_celery_defaults.json": {
        "url": "https://api.github.com/repos/celery/celery/contents/celery/app/defaults.py",
        "rail": "R1-api",
    },
    "raw_celery_defaults.py": {
        "url": "https://raw.githubusercontent.com/celery/celery/main/celery/app/defaults.py",
        "rail": "R1-api-decoded",
    },
    "airflow_dags_gh.json": {
        "url": "https://api.github.com/repos/apache/airflow/contents/airflow-core/docs/core-concepts/dags.rst",
        "rail": "R1-api",
    },
    "airflow_trigger_rules.md": {
        "url": "https://raw.githubusercontent.com/apache/airflow/main/airflow-core/docs/core-concepts/dags.rst",
        "rail": "R2-prose",
    },
    "gh_airflow_config_yml.json": {
        "url": "https://api.github.com/repos/apache/airflow/contents/airflow-core/src/airflow/config_templates/config.yml",
        "rail": "R1-api",
    },
    "airflow_config_yml": {
        "url": "https://raw.githubusercontent.com/apache/airflow/main/airflow-core/src/airflow/config_templates/config.yml",
        "rail": "R2-prose",
    },
    "airflow_config_ref.html": {
        "url": "https://airflow.apache.org/docs/apache-airflow/stable/configurations-ref.html",
        "rail": "R2-prose",
    },
    "gh_argo_workflow_types.json": {
        "url": "https://api.github.com/repos/argoproj/argo-workflows/contents/pkg/apis/workflow/v1alpha1/workflow_types.go",
        "rail": "R1-api",
    },
    "argo_fields.md": {
        "url": "https://raw.githubusercontent.com/argoproj/argo-workflows/main/docs/fields.md",
        "rail": "R2-prose",
    },
    "gh_temporal_activity.json": {
        "url": "https://api.github.com/repos/temporalio/sdk-python/contents/temporalio/activity.py",
        "rail": "R1-api",
    },
    "temporal_activity_failures.html": {
        "url": "https://docs.temporal.io/encyclopedia/detecting-activity-failures",
        "rail": "R2-prose",
    },
    "gh_durable_common.json": {
        "url": "https://api.github.com/repos/MicrosoftDocs/azure-docs/contents/articles/durable-task/common/durable-task-fan-in-fan-out.md",
        "rail": "R1-api",
    },
    "durable_fanout_common.md": {
        "url": "https://raw.githubusercontent.com/MicrosoftDocs/azure-docs/main/articles/durable-task/common/durable-task-fan-in-fan-out.md",
        "rail": "R2-prose",
    },
    "durable_fanout_pattern.html": {
        "url": "https://learn.microsoft.com/en-us/azure/azure-functions/durable/durable-functions-cloud-backup",
        "rail": "R2-prose",
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes()
    return sha256_bytes(raw.replace(b"\r\n", b"\n")), len(raw)


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "")


def decode_github_json(raw: bytes) -> str | None:
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(doc, dict):
        return None
    content = doc.get("content")
    if not isinstance(content, str) or not content.strip():
        return None
    try:
        return base64.b64decode(content).decode("utf-8", "replace")
    except Exception:
        return None


def strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text)


def searchable_text(path: Path) -> str:
    raw = path.read_bytes()
    parts = [raw.decode("utf-8", "replace")]
    decoded = decode_github_json(raw)
    if decoded:
        parts.append(decoded)
    joined = "\n".join(parts)
    parts.append(strip_tags(joined))
    return "\n".join(parts)


def quote_in_snapshot(path: Path, quote: str) -> bool:
    if not quote or not path.is_file():
        return False
    blob = norm(searchable_text(path))
    return norm(quote) in blob


def load_meta_times() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if HARVEST_META.is_file():
        try:
            doc = json.loads(HARVEST_META.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            doc = {}
        for entry in doc.get("entries") or []:
            if isinstance(entry, dict) and entry.get("name"):
                out[str(entry["name"])] = entry
    return out


def build_harvest_index() -> dict[str, Any]:
    meta = load_meta_times()
    files: dict[str, Any] = {}
    for name, spec in SOURCES.items():
        path = SNAP / name
        if not path.is_file() or path.stat().st_size <= 0:
            raise FileNotFoundError(f"missing snapshot {name}")
        raw = path.read_bytes()
        sha = sha256_bytes(raw)
        prev = meta.get(name) or {}
        files[name] = {
            "name": name,
            "path": f"command-center/p2-wave/probes/RES-0068/snapshots/{name}",
            "url": spec["url"],
            "rail": spec["rail"],
            "http_status": int(prev.get("status") or 200),
            "bytes": len(raw),
            "sha256": sha,
            "fetched_at": prev.get("fetched_at") or utc_now(),
        }
    idx = {
        "unit_id": UID,
        "built_at": utc_now(),
        "files": files,
    }
    HARVEST_INDEX.write_text(json.dumps(idx, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return idx


def load_harvest_index() -> dict[str, Any]:
    if not HARVEST_INDEX.is_file():
        return build_harvest_index()
    return json.loads(HARVEST_INDEX.read_text(encoding="utf-8"))


def rail(name: str, quote: str, idx: dict[str, Any]) -> dict[str, Any]:
    rec = idx["files"][name]
    path = SNAP / name
    if not quote_in_snapshot(path, quote):
        raise AssertionError(f"quote not in snapshot {name}: {quote[:80]!r}")
    live_sha = sha256_bytes(path.read_bytes())
    if live_sha != rec["sha256"]:
        raise AssertionError(f"stale harvest sha for {name}")
    return {
        "snapshot": name,
        "permalink": rec["url"],
        "fetch_timestamp": rec["fetched_at"],
        "http_status": rec["http_status"],
        "sha256": rec["sha256"],
        "bytes": rec["bytes"],
        "quote": quote,
        "rail_kind": rec["rail"],
    }


def evidence_tier(n_rails: int) -> str:
    if n_rails >= 2:
        return "E2"
    if n_rails == 1:
        return "E3"
    return "E4"


def grade_claim(claim: dict[str, Any], idx: dict[str, Any] | None = None) -> dict[str, Any]:
    """Mechanical grader: two rails + live sha + quote-in-bytes. One rail => E3."""
    idx = idx or load_harvest_index()
    rails = claim.get("source_lineage") or claim.get("rails") or []
    problems: list[str] = []
    ok_rails = 0
    for r in rails:
        if not isinstance(r, dict):
            problems.append("non-object-rail")
            continue
        snap = SNAP / str(r.get("snapshot") or "")
        quote = str(r.get("quote") or "")
        want_sha = str(r.get("sha256") or "")
        if not snap.is_file():
            problems.append(f"missing-snapshot:{snap.name}")
            continue
        live = sha256_bytes(snap.read_bytes())
        if live != want_sha:
            problems.append(f"sha-mismatch:{snap.name}")
            continue
        if int(r.get("http_status") or 0) != 200:
            problems.append(f"http:{r.get('http_status')}")
            continue
        if not quote_in_snapshot(snap, quote):
            problems.append(f"quote-absent:{snap.name}")
            continue
        if not r.get("permalink") or not r.get("fetch_timestamp"):
            problems.append(f"incomplete-rail:{snap.name}")
            continue
        ok_rails += 1
    tier = evidence_tier(ok_rails)
    citable = tier in {"E1", "E2"} and not problems
    return {
        "ok_rails": ok_rails,
        "tier": tier,
        "citable_as_measured_fact": citable,
        "problems": problems,
    }
