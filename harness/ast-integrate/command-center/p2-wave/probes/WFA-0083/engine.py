"""Committed-blob hashing and manifest reconciliation for WFA-0083.

Verification hashes are taken from git cat-file (when a .git exists) or from
a content-addressed blob store written at registration time. Live worktree
bytes are used only to *create* a snapshot, never to recompute a recorded
digest.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
OUT_REL = "command-center/wfa/WFA-0083-artifact-manifest-registration.json"
WFA_MANIFEST_REL = "command-center/wfa/ARTIFACT-MANIFEST.json"
PROGRAM_MANIFEST_REL = "command-center/ARTIFACT-MANIFEST.json"
BLOB_INDEX_REL = "command-center/p2-wave/probes/WFA-0083/committed-blobs/index.json"
BLOB_OBJ_REL = "command-center/p2-wave/probes/WFA-0083/committed-blobs/objects"
SCHEMA_PACK_REL = "command-center/wfa/schema/wfa-schema-pack.json"


def lf(raw: bytes) -> bytes:
    return raw.replace(b"\r\n", b"\n")


def digest_bytes(raw: bytes) -> tuple[str, int]:
    norm = lf(raw)
    return hashlib.sha256(norm).hexdigest(), len(norm)


def git_blob_bytes(root: Path, rel: str) -> bytes | None:
    if not (root / ".git").exists():
        return None
    posix = rel.replace("\\", "/")
    proc = subprocess.run(
        ["git", "-C", str(root), "cat-file", "-p", f"HEAD:{posix}"],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout


class BlobStore:
    """Path -> frozen object. Recompute never opens the worktree file."""

    def __init__(self, root: Path, index_rel: str = BLOB_INDEX_REL, obj_rel: str = BLOB_OBJ_REL):
        self.root = root
        self.index_path = root / index_rel
        self.obj_dir = root / obj_rel
        self.index_rel = index_rel
        self.obj_rel = obj_rel

    def _load_index(self) -> dict[str, str]:
        if not self.index_path.is_file():
            return {}
        doc = json.loads(self.index_path.read_text(encoding="utf-8"))
        if not isinstance(doc, dict):
            raise RuntimeError("blob index is not an object")
        out: dict[str, str] = {}
        for k, v in doc.items():
            if isinstance(k, str) and isinstance(v, str):
                out[k.replace("\\", "/")] = v
        return out

    def _save_index(self, idx: dict[str, str]) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(
            json.dumps(idx, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    def snapshot(self, rel: str, data: bytes) -> str:
        rel = rel.replace("\\", "/")
        sha, _n = digest_bytes(data)
        self.obj_dir.mkdir(parents=True, exist_ok=True)
        obj = self.obj_dir / sha
        if not obj.is_file():
            obj.write_bytes(lf(data))
        idx = self._load_index()
        idx[rel] = sha
        self._save_index(idx)
        return sha

    def snapshot_worktree(self, rel: str) -> str:
        """Registration-time snapshot. The only allowed worktree read."""
        path = self.root / rel
        if not path.is_file():
            raise FileNotFoundError(rel)
        return self.snapshot(rel, path.read_bytes())

    def blob_bytes(self, rel: str) -> bytes:
        rel = rel.replace("\\", "/")
        idx = self._load_index()
        sha = idx.get(rel)
        if not sha:
            raise FileNotFoundError(f"no committed blob for {rel}")
        obj = self.obj_dir / sha
        if not obj.is_file():
            raise FileNotFoundError(f"missing blob object {sha} for {rel}")
        return obj.read_bytes()

    def recompute(self, rel: str) -> tuple[str, int, str]:
        """Return (sha256, nbytes, source). Never hashes the worktree file."""
        rel = rel.replace("\\", "/")
        git_raw = git_blob_bytes(self.root, rel)
        if git_raw is not None:
            sha, n = digest_bytes(git_raw)
            return sha, n, "git-cat-file"
        raw = self.blob_bytes(rel)
        sha, n = digest_bytes(raw)
        return sha, n, "blob-store"


def load_catalog(root: Path) -> list[dict[str, Any]]:
    data = json.loads((root / CATALOG_REL).read_text(encoding="utf-8"))
    units = data.get("work_units") if isinstance(data, dict) else None
    if not isinstance(units, list):
        raise RuntimeError("catalog missing work_units")
    out = []
    for u in units:
        if isinstance(u, dict) and str(u.get("id") or "").startswith("WFA-"):
            out.append(u)
    if not out:
        raise RuntimeError("zero WFA units in catalog")
    return out


def def_name(schema: str) -> str:
    s = (schema or "").replace("\\", "/")
    if "#/$defs/" in s:
        return s.rsplit("#/$defs/", 1)[-1]
    return "unknown"


def catalog_rows(root: Path) -> list[dict[str, Any]]:
    rows = []
    for u in load_catalog(root):
        rel = str(u.get("output_path") or "").replace("\\", "/")
        if not rel:
            continue
        rows.append(
            {
                "unit_id": u["id"],
                "path": rel,
                "schema": str(u.get("output_schema") or ""),
                "record_type": def_name(str(u.get("output_schema") or "")),
                "present": (root / rel).is_file() and (root / rel).stat().st_size > 0,
            }
        )
    return rows


def reconcile(manifest_paths: set[str], disk_paths: set[str]) -> dict[str, Any]:
    """A manifest row with no file, and a file with no row, are both failures."""
    man = {p.replace("\\", "/") for p in manifest_paths}
    disk = {p.replace("\\", "/") for p in disk_paths}
    missing_file = sorted(man - disk)
    orphan_file = sorted(disk - man)
    return {
        "ok": not missing_file and not orphan_file,
        "missing_file": missing_file,
        "orphan_file": orphan_file,
        "matched": sorted(man & disk),
    }


def empty_manifest(*, derivation: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "contract": "completion-predicate-conditions-11-and-12-register-on-write",
        "derivation": derivation,
        "bucket": "WFA",
        "hash_source": "committed-blob-never-worktree",
        "verified_on_disk": False,
        "expected": 0,
        "present": 0,
        "artifacts": [],
    }


def write_manifest(path: Path, rows: list[dict[str, Any]], derivation: str) -> dict[str, Any]:
    rows = sorted(rows, key=lambda r: (str(r.get("path") or ""), str(r.get("unit_id") or "")))
    present = sum(1 for r in rows if r.get("present") is True)
    doc = empty_manifest(derivation=derivation)
    doc["artifacts"] = rows
    doc["expected"] = len(rows)
    doc["present"] = present
    doc["verified_on_disk"] = present == len(rows) and len(rows) > 0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return doc


def prove_blob_not_worktree() -> dict[str, Any]:
    """Dirty worktree after snapshot; recompute must stay on the committed bytes."""
    import tempfile

    git_result = _prove_git_blob()
    with tempfile.TemporaryDirectory(prefix="wfa0083-blob-") as tmp:
        root = Path(tmp)
        rel = "payload.json"
        committed = b'{"v":"committed"}\n'
        dirty = b'{"v":"dirty-worktree"}\n'
        (root / rel).write_bytes(committed)
        store = BlobStore(root, index_rel="idx.json", obj_rel="objects")
        snap = store.snapshot_worktree(rel)
        (root / rel).write_bytes(dirty)
        worktree_sha, _n = digest_bytes(dirty)
        rec, _nbytes, src = store.recompute(rel)
        store_ok = rec == snap and rec != worktree_sha and src == "blob-store"
        store_result = {
            "ok": store_ok,
            "snapshot": snap,
            "recomputed": rec,
            "worktree": worktree_sha,
            "source": src,
        }
    ok = bool(git_result.get("ok")) and store_ok
    return {"ok": ok, "git": git_result, "blob_store": store_result}


def _prove_git_blob() -> dict[str, Any]:
    import tempfile

    committed = b'{"v":"committed"}\n'
    dirty = b'{"v":"dirty-worktree"}\n'
    with tempfile.TemporaryDirectory(prefix="wfa0083-git-") as tmp:
        root = Path(tmp)
        rel = "payload.json"
        (root / rel).write_bytes(committed)
        init = subprocess.run(["git", "init", "-q"], cwd=root, capture_output=True)
        if init.returncode != 0:
            return {"ok": False, "error": "git-init-failed", "stderr": init.stderr.decode("utf-8", "replace")}
        add = subprocess.run(["git", "add", "--", rel], cwd=root, capture_output=True)
        if add.returncode != 0:
            return {"ok": False, "error": "git-add-failed"}
        commit = subprocess.run(
            [
                "git",
                "-c",
                "user.email=wfa-0083@local",
                "-c",
                "user.name=wfa0083",
                "commit",
                "-q",
                "-m",
                "blob",
            ],
            cwd=root,
            capture_output=True,
        )
        if commit.returncode != 0:
            return {
                "ok": False,
                "error": "git-commit-failed",
                "stderr": commit.stderr.decode("utf-8", "replace"),
            }
        (root / rel).write_bytes(dirty)
        raw = git_blob_bytes(root, rel)
        if raw is None:
            return {"ok": False, "error": "git-cat-file-missed"}
        blob_sha, _n = digest_bytes(raw)
        want, _w = digest_bytes(committed)
        worktree_sha, _t = digest_bytes(dirty)
        ok = blob_sha == want and blob_sha != worktree_sha
        return {
            "ok": ok,
            "blob": blob_sha,
            "committed": want,
            "worktree": worktree_sha,
            "source": "git-cat-file",
        }


def prove_ghost_and_orphan() -> dict[str, Any]:
    ghost = reconcile({"ghost.json"}, set())
    orphan = reconcile(set(), {"orphan.json"})
    both = reconcile({"ghost.json"}, {"orphan.json"})
    ok = (
        (not ghost["ok"] and ghost["missing_file"] == ["ghost.json"] and not ghost["orphan_file"])
        and (not orphan["ok"] and orphan["orphan_file"] == ["orphan.json"] and not orphan["missing_file"])
        and (
            not both["ok"]
            and both["missing_file"] == ["ghost.json"]
            and both["orphan_file"] == ["orphan.json"]
        )
    )
    return {"ok": ok, "ghost": ghost, "orphan": orphan, "both": both}


def program_manifest_preserved(root: Path) -> dict[str, Any]:
    """command-center/ARTIFACT-MANIFEST.json is owned by render.py.

    WFA-0083 must not replace it with a WFA-only row set (that drops
    PROGRAM-CHARTER.md and fails tools/command-center/render.py --check).
    Bucket registration lives in command-center/wfa/ARTIFACT-MANIFEST.json.
    """
    path = root / PROGRAM_MANIFEST_REL
    if not path.is_file() or path.stat().st_size <= 0:
        return {"ok": False, "error": "missing-or-empty"}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": f"{type(exc).__name__}:{exc}"}
    if not isinstance(doc, dict):
        return {"ok": False, "error": "json-root-not-object"}
    rows = [a for a in (doc.get("artifacts") or []) if isinstance(a, dict)]
    paths = [str(a.get("path") or "").replace("\\", "/") for a in rows]
    has_charter = "command-center/PROGRAM-CHARTER.md" in paths
    derivation = str(doc.get("derivation") or "")
    render_owned = "render.py" in derivation or "render_manifest" in derivation
    return {
        "ok": has_charter and render_owned,
        "row_count": len(rows),
        "derivation": derivation,
        "has_program_charter": has_charter,
        "render_owned": render_owned,
    }
