#!/usr/bin/env python3
"""Historical documents that already cite the frozen GitHub issues."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from score import load_fields

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

ISSUE_RE = re.compile(
    r"https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/issues/(\d+)"
)

HISTORICAL_RUNS: list[tuple[str, str]] = [
    ("RES-0115-artifact", "command-center/research/RES-0115.json"),
    (
        "RES-0115-emit-registry",
        "command-center/p2-wave/probes/RES-0115/emit_registry.py",
    ),
    (
        "RES-0115-captures",
        "command-center/p2-wave/probes/RES-0115/snapshots/captures.json",
    ),
    (
        "RES-0115-independent-pair",
        "command-center/p2-wave/probes/RES-0115/fixtures/independent-pair.json",
    ),
    (
        "RES-0043-inspector-readme",
        "command-center/p2-wave/probes/RES-0043/corpus/clients/inspector/README.md",
    ),
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def lineage(rel: str) -> dict[str, Any]:
    path = REPO / rel
    digest, size = sha256_file(path)
    ts = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    return {
        "resolved_url": path.resolve().as_uri(),
        "fetch_timestamp": ts,
        "sha256": digest,
        "path": rel,
        "bytes": size,
    }


def extract_issue_ids(text: str) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for m in ISSUE_RE.finditer(text):
        iid = f"{m.group(1)}/{m.group(2)}#{m.group(3)}"
        if iid not in seen:
            seen.add(iid)
            ids.append(iid)
    return ids


def load_historical_runs() -> list[dict[str, Any]]:
    fields = load_fields()
    runs = []
    for run_id, rel in HISTORICAL_RUNS:
        path = REPO / rel
        text = path.read_text(encoding="utf-8", errors="replace")
        ids = extract_issue_ids(text)
        sources = []
        skipped = []
        for iid in ids:
            if iid in fields:
                sources.append(dict(fields[iid]))
            else:
                skipped.append(iid)
        if not sources:
            raise RuntimeError(f"{run_id} produced zero frozen-issue sources from {rel}")
        lin = lineage(rel)
        runs.append(
            {
                "run_id": run_id,
                "path": rel,
                "sources": sources,
                "cited_ids": [s["id"] for s in sources],
                "skipped_uncached": skipped,
                "file_sha256": lin["sha256"],
                "resolved_url": lin["resolved_url"],
                "fetch_timestamp": lin["fetch_timestamp"],
                "bytes": lin["bytes"],
            }
        )
    return runs
