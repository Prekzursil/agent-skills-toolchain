"""IMP-0155 fixture corpus and capture of 10 provenance records.

Sources live on disk. Capture reads bytes; refetch reads them again.
Two retrieval methods are exercised so `retrieval_method` is not a label.
"""

from __future__ import annotations

import io
import json
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from foundry.provenance import (  # noqa: E402
    ProvenanceRecord,
    attach_provenance,
    capture,
    provenance_only,
)

CAND_DIR = HERE / "fixtures" / "candidates"
PACK_DIR = HERE / "fixtures" / "pack"
TAR_PATH = PACK_DIR / "candidates.tar"
DECOY_POSIX = "wf-DECOY.json"
DECOY_TAR = "wf-tar-DECOY.json"
FROZEN_TIME = datetime(2026, 8, 24, 18, 0, 0, tzinfo=timezone.utc)

# 10 candidates: 8 posix-read + 2 tar-member. Distinct payloads so a wrong ref
# cannot hash-match by coincidence.
CANDIDATES = [
    {
        "id": f"IMP-0155-cand-{i:02d}",
        "kind": "workflow-candidate",
        "title": f"foundry candidate {i:02d}",
        "body": f"stage-graph payload {i:02d} unique-bytes={'*' * (i + 3)}\n",
    }
    for i in range(10)
]


def _write_json(path: Path, doc: dict) -> bytes:
    raw = (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return raw


def ensure_fixtures() -> dict[str, Path]:
    """Idempotent: rewrite the same bytes every time (deterministic corpus)."""
    CAND_DIR.mkdir(parents=True, exist_ok=True)
    PACK_DIR.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    posix_payloads: dict[str, bytes] = {}
    for i, cand in enumerate(CANDIDATES):
        name = f"wf-{i:02d}.json"
        path = CAND_DIR / name
        posix_payloads[name] = _write_json(path, cand)
        paths[name] = path
    decoy = {
        "id": "IMP-0155-decoy-posix",
        "kind": "workflow-candidate",
        "title": "DECOY — different bytes from every sampled candidate",
        "body": "decoy-posix-payload\n",
    }
    paths[DECOY_POSIX] = CAND_DIR / DECOY_POSIX
    _write_json(paths[DECOY_POSIX], decoy)

    tar_members: list[tuple[str, bytes]] = []
    for i in (8, 9):
        name = f"wf-{i:02d}.json"
        tar_members.append((name, posix_payloads[name]))
    decoy_tar_doc = {
        "id": "IMP-0155-decoy-tar",
        "kind": "workflow-candidate",
        "title": "DECOY tar member",
        "body": "decoy-tar-payload\n",
    }
    decoy_tar_bytes = (json.dumps(decoy_tar_doc, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    tar_members.append((DECOY_TAR, decoy_tar_bytes))

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for name, data in tar_members:
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            info.mtime = 0
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            tf.addfile(info, io.BytesIO(data))
    TAR_PATH.write_bytes(buf.getvalue())
    paths["candidates.tar"] = TAR_PATH
    return paths


def posix_source() -> str:
    return "repo:command-center/p2-wave/probes/IMP-0155/fixtures/candidates"


def tar_source() -> str:
    return "repo:command-center/p2-wave/probes/IMP-0155/fixtures/pack/candidates.tar"


def sample_specs() -> list[dict[str, str]]:
    """How each of the 10 sampled candidates is retrieved."""
    specs = []
    for i in range(8):
        specs.append(
            {
                "id": CANDIDATES[i]["id"],
                "method": "posix-read",
                "source": posix_source(),
                "ref": f"wf-{i:02d}.json",
            }
        )
    for i in (8, 9):
        specs.append(
            {
                "id": CANDIDATES[i]["id"],
                "method": "tar-member",
                "source": tar_source(),
                "ref": f"wf-{i:02d}.json",
            }
        )
    return specs


def capture_sample(*, repo_root: Path | None = None) -> list[dict]:
    """Capture 10 records. Returned rows carry candidate id + provenance only."""
    ensure_fixtures()
    root = repo_root or REPO
    rows = []
    for spec in sample_specs():
        rec = capture(
            source=spec["source"],
            ref=spec["ref"],
            retrieval_method=spec["method"],
            now=FROZEN_TIME,
            repo_root=root,
        )
        candidate = attach_provenance({"id": spec["id"]}, rec)
        rows.append(
            {
                "id": spec["id"],
                "provenance": provenance_only(candidate),
            }
        )
    return rows


def second_agent_records(rows: list[dict]) -> list[dict[str, str]]:
    """What a second agent receives: only the five provenance fields."""
    return [provenance_only(row) for row in rows]


def decoy_ref_for(record: dict[str, str]) -> str:
    if record["retrieval_method"] == "tar-member":
        return DECOY_TAR
    return DECOY_POSIX


__all__ = [
    "CANDIDATES",
    "DECOY_POSIX",
    "DECOY_TAR",
    "FROZEN_TIME",
    "HERE",
    "REPO",
    "TAR_PATH",
    "capture_sample",
    "decoy_ref_for",
    "ensure_fixtures",
    "posix_source",
    "sample_specs",
    "second_agent_records",
    "tar_source",
]
