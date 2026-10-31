"""Registry-side provenance storage and digest verification (IMP-0080)."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class DigestMismatchError(Exception):
    pass


class EmptyQuerySuccess(Exception):
    pass


class UnresolvedCommitError(Exception):
    pass


def artifact_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    return (proc.stdout or "").strip()


def init_source_repo(path: Path, files: dict[str, bytes]) -> tuple[str, str]:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "imp0080@test.invalid"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "IMP-0080"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "commit.gpgsign", "false"], check=True, capture_output=True)
    for rel, body in files.items():
        dest = path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(body)
        subprocess.run(["git", "-C", str(path), "add", rel], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "commit", "-q", "-m", "plant"], check=True, capture_output=True)
    commit = _git(path, "rev-parse", "HEAD")
    tree = _git(path, "rev-parse", "HEAD^{tree}")
    return commit, tree


def make_attestation(
    *,
    package: str,
    version: str,
    artifact_digest: str,
    source_repo: str,
    commit_sha: str,
    tree_hash: str,
    builder_id: str = "",
    build_parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "package": package,
        "version": version,
        "artifact_digest_sha256": artifact_digest,
        "source_repo": source_repo,
        "commit_sha": commit_sha,
        "tree_hash": tree_hash,
        "builder_id": builder_id,
        "build_parameters": dict(build_parameters or {}),
    }


@dataclass
class QueryPayload:
    status: str
    record: dict[str, Any] | None = None
    package: str = ""
    version: str = ""


def interpret_query(doc: dict[str, Any] | None) -> QueryPayload:
    if not doc:
        raise EmptyQuerySuccess("empty query object is not a success")
    if not isinstance(doc, dict):
        raise EmptyQuerySuccess("query payload is not an object")
    if doc.get("ok") is True and not doc.get("record") and not doc.get("status"):
        raise EmptyQuerySuccess("ok=true empty success")
    rec = doc.get("record") if isinstance(doc.get("record"), dict) else None
    status = str(doc.get("status") or (rec or {}).get("status") or "NONE")
    package = str(doc.get("package") or (rec or {}).get("package") or "")
    version = str(doc.get("version") or (rec or {}).get("version") or "")
    return QueryPayload(status=status, record=rec, package=package, version=version)


class ProvenanceStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._index = self.root / "index.json"
        self._records: dict[str, dict[str, Any]] = {}
        if self._index.is_file():
            raw = json.loads(self._index.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                self._records = {str(k): v for k, v in raw.items() if isinstance(v, dict)}

    def _key(self, package: str, version: str) -> str:
        return f"{package}@{version}"

    def _save(self) -> None:
        self._index.write_text(json.dumps(self._records, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def publish(
        self,
        *,
        package: str,
        version: str,
        artifact: bytes | None = None,
        attestation: dict[str, Any] | None = None,
        source_repo: Path | None = None,
    ) -> dict[str, Any]:
        if attestation and attestation.get("commit_sha") in {None, "", "missing", "0" * 40}:
            raise UnresolvedCommitError("missing commit")
        if attestation and source_repo is not None:
            sha = str(attestation.get("commit_sha") or "")
            git_dir = Path(source_repo) / ".git"
            if sha and git_dir.exists():
                import subprocess as _sp
                proc = _sp.run(
                    ["git", "-C", str(source_repo), "cat-file", "-t", sha],
                    capture_output=True,
                    text=True,
                )
                if proc.returncode != 0:
                    raise UnresolvedCommitError(sha)
        rec: dict[str, Any] = {
            "package": package,
            "version": version,
            "status": "PRESENT" if attestation else "NONE",
        }
        if artifact is not None:
            blob_path = self.root / "blobs" / f"{package}-{version}.bin"
            blob_path.parent.mkdir(parents=True, exist_ok=True)
            blob_path.write_bytes(artifact)
            rec["artifact_digest_sha256"] = artifact_sha256(artifact)
            rec["artifact_path"] = str(blob_path)
        if attestation:
            rec.update(attestation)
            rec["status"] = "PRESENT"
        if source_repo is not None:
            rec["source_repo_path"] = str(source_repo)
        self._records[self._key(package, version)] = rec
        self._save()
        return rec

    def query(self, package: str, version: str) -> dict[str, Any]:
        rec = self._records.get(self._key(package, version))
        if rec is None:
            return {"status": "NONE", "record": None, "package": package, "version": version}
        return {
            "status": rec.get("status") or "NONE",
            "record": rec,
            "package": rec.get("package") or package,
            "version": rec.get("version") or version,
        }

    def query_all_published(self):
        for rec in self._records.values():
            yield {
                "status": rec.get("status") or "NONE",
                "record": rec,
                "package": rec.get("package") or "",
                "version": rec.get("version") or "",
            }

    def verify_against_artifact(self, package: str, version: str, artifact: bytes) -> dict[str, Any]:
        rec = self._records.get(self._key(package, version))
        if rec is None or rec.get("status") != "PRESENT":
            raise DigestMismatchError(f"missing {package}@{version}")
        actual = artifact_sha256(artifact)
        expected = rec.get("artifact_digest_sha256")
        if actual != expected:
            raise DigestMismatchError(f"expected {expected} actual {actual}")
        return {"verified": True, "artifact_digest_sha256": actual}

    def verify_commit_tree(self, package: str, version: str, source: Path) -> dict[str, Any]:
        rec = self._records.get(self._key(package, version))
        if rec is None:
            raise UnresolvedCommitError(package)
        commit = _git(source, "rev-parse", "HEAD")
        tree = _git(source, "rev-parse", "HEAD^{tree}")
        if commit != rec.get("commit_sha") or tree != rec.get("tree_hash"):
            raise UnresolvedCommitError(f"{commit} {tree}")
        return {"verified": True, "commit_sha": commit, "tree_hash": tree}
