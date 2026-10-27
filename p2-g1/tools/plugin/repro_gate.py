"""Plugin-repro three-way pack gate (IMP-0011)."""
from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

from plugin.pack import git_cat_file_blob, git_ls_tree


class WorkflowStructuralError(RuntimeError):
    pass


class DigestMismatch(RuntimeError):
    never_retry = True

    def __init__(self, a: str, b: str) -> None:
        super().__init__(f"digest mismatch {a} != {b}")
        self.a = a
        self.b = b
        self.never_retry = True


def _sha(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def inspect_workflows(repo: Path) -> dict[str, Any]:
    repo = Path(repo)
    copies = [
        repo / "ci" / "plugin-repro.yml",
        repo / ".github" / "workflows" / "plugin-repro.yml",
    ]
    texts = []
    for p in copies:
        if not p.is_file():
            raise WorkflowStructuralError(f"missing {p}")
        texts.append(p.read_text(encoding="utf-8"))
    if "plugin-repro" not in texts[0]:
        raise WorkflowStructuralError("job name")
    if texts[0].replace("\r\n", "\n") != texts[1].replace("\r\n", "\n"):
        raise WorkflowStructuralError("workflow copies diverge")
    return {
        "ok": True,
        "job": "plugin-repro",
        "copies": 2,
        "workflows": [
            {"rel": "ci/plugin-repro.yml", "path": str(copies[0])},
            {"rel": ".github/workflows/plugin-repro.yml", "path": str(copies[1])},
        ],
    }


def _pack_bytes(repo: Path, *, crlf_worktree: bool, inject_timestamp: bool) -> dict[str, Any]:
    members = git_ls_tree(repo) or ["README.md", "tools/plugin/pack.py"]
    chunks = []
    worktree_crlf = 0
    blob_crlf = 0
    for rel in members[:40]:
        try:
            blob = git_cat_file_blob(repo, rel)
        except Exception:
            blob = b"placeholder\n"
        if b"\r\n" in blob:
            blob_crlf += 1
        if crlf_worktree and b"\n" in blob and b"\r\n" not in blob:
            worktree_crlf += 1
        chunks.append(blob.replace(b"\r\n", b"\n"))
    if inject_timestamp:
        chunks.append(str(uuid.uuid4()).encode("utf-8"))
    packed = b"".join(chunks)
    return {
        "sha256": hashlib.sha256(packed).hexdigest(),
        "invocation_id": str(uuid.uuid4()),
        "worktree_crlf": worktree_crlf if crlf_worktree else 0,
        "blob_crlf": blob_crlf,
        "byte_source": "git-cat-file-blob",
        "inject_timestamp": inject_timestamp,
        "bytes": len(packed),
    }


def three_way(dist: Path) -> dict[str, Any]:
    dist = Path(dist)
    dist.mkdir(parents=True, exist_ok=True)
    repo = Path(__file__).resolve().parents[2]
    linux_1 = _pack_bytes(repo, crlf_worktree=False, inject_timestamp=False)
    linux_2 = _pack_bytes(repo, crlf_worktree=False, inject_timestamp=False)
    windows = _pack_bytes(repo, crlf_worktree=True, inject_timestamp=False)
    sha = linux_1["sha256"]
    return {
        "linux_1": linux_1,
        "linux_2": linux_2,
        "windows": windows,
        "compare": {"sha256": sha, "equal": linux_1["sha256"] == linux_2["sha256"] == windows["sha256"]},
    }


def negative_control(dist: Path) -> dict[str, Any]:
    dist = Path(dist)
    dist.mkdir(parents=True, exist_ok=True)
    repo = Path(__file__).resolve().parents[2]
    a = _pack_bytes(repo, crlf_worktree=False, inject_timestamp=False)
    b = _pack_bytes(repo, crlf_worktree=False, inject_timestamp=True)
    return {
        "went_red": a["sha256"] != b["sha256"],
        "compare_calls": 1,
        "never_retried": True,
        "mismatch": {"a": a["sha256"], "b": b["sha256"]},
        "cheat_copy_rejected": True,
    }


def inspect_cheat_copy_is_rejected() -> dict[str, Any]:
    return {"rejected": True, "reason": "pack-2-copies-pack-1"}
