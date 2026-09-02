"""File-backed local fixture marketplace (no public publish).

Under PR-ONLY the public listing path is BLOCKED. Install, upgrade,
rollback, offline-from-export, and unsigned refusal are local and do
not publish. Stopping condition 13 (release/canary succeeds) has no
canary channel and is UNSATISFIABLE-AS-WRITTEN.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

PKG = "cap.skill.demo"
V1 = "1.0.0"
V2 = "1.1.0"
FILES_V1 = {"SKILL.md": "# demo v1\nlocal fixture package\n"}
FILES_V2 = {"SKILL.md": "# demo v2\nupgraded fixture package\n"}
SIG_PREFIX = "local-dev-sig:"


def _dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def _write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump(obj), encoding="utf-8")


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def payload_for_sig(pkg: dict[str, Any]) -> bytes:
    body = {k: pkg[k] for k in sorted(pkg) if k != "signature"}
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign(pkg: dict[str, Any]) -> str:
    return SIG_PREFIX + hashlib.sha256(payload_for_sig(pkg)).hexdigest()


def make_package(name: str, version: str, files: dict[str, str]) -> dict[str, Any]:
    pkg = {
        "files": files,
        "name": name,
        "version": version,
    }
    pkg["payload_sha256"] = hashlib.sha256(payload_for_sig(pkg)).hexdigest()
    pkg["signature"] = sign(pkg)
    return pkg


class FixtureMarket:
    def __init__(self, root: Path, release_mode: str = "PR-ONLY") -> None:
        self.root = root
        self.release_mode = release_mode
        self.index_path = root / "index.json"
        self.blobs = root / "blobs"

    def index(self) -> dict[str, Any]:
        return _read(self.index_path)

    def index_sha256(self) -> str:
        return sha256_file(self.index_path)

    def _save_index(self, idx: dict[str, Any]) -> None:
        _write(self.index_path, idx)

    def seed_working(self) -> None:
        if self.root.exists():
            shutil.rmtree(self.root)
        self.blobs.mkdir(parents=True, exist_ok=True)
        idx: dict[str, Any] = {
            "packages": {},
            "release_mode": self.release_mode,
            "schema": "a3-fixture-market/v1",
        }
        self._save_index(idx)
        for version, files in ((V1, FILES_V1), (V2, FILES_V2)):
            pkg = make_package(PKG, version, files)
            rel = f"blobs/{PKG}-{version}.json"
            blob = self.root / rel
            _write(blob, pkg)
            idx = self.index()
            pkg_row = idx["packages"].setdefault(PKG, {"versions": {}})
            pkg_row["versions"][version] = {
                "blob": rel,
                "sha256": sha256_file(blob),
            }
            self._save_index(idx)

    def seed_missing_blob(self, source: "FixtureMarket") -> None:
        if self.root.exists():
            shutil.rmtree(self.root)
        shutil.copytree(source.root, self.root)
        idx = self.index()
        idx["packages"][PKG]["versions"][V1]["blob"] = "blobs/does-not-exist.json"
        self._save_index(idx)

    def publish_public(self, pkg: dict[str, Any]) -> dict[str, Any]:
        if self.release_mode == "PR-ONLY":
            return {
                "blocked": True,
                "code": "BLOCKED-PR-ONLY",
                "ok": False,
                "package": pkg.get("name"),
                "reason": (
                    "OQ-3 forbids public marketplace release; propose a pull "
                    "request instead"
                ),
            }
        raise RuntimeError("public publish is out of scope on this fixture")

    def canary_succeeds(self) -> dict[str, Any]:
        return {
            "condition": 13,
            "ok": False,
            "text": "release/canary succeeds",
            "verdict": "UNSATISFIABLE-AS-WRITTEN",
            "why": (
                "PR-ONLY has no canary channel and never a public marketplace "
                "release"
            ),
        }

    def propose_pr(self, dest: Path, pkg: dict[str, Any]) -> dict[str, Any]:
        before = self.index_sha256()
        dest.mkdir(parents=True, exist_ok=True)
        _write(
            dest / "pr-diff.json",
            {
                "action": "propose-index-entry",
                "package": pkg,
                "release_mode": self.release_mode,
            },
        )
        after = self.index_sha256()
        return {
            "index_sha256_after": after,
            "index_sha256_before": before,
            "index_unchanged": before == after,
            "ok": True,
            "pr_diff": str(dest / "pr-diff.json"),
        }

    def _load_blob(self, name: str, version: str) -> tuple[dict[str, Any], str]:
        idx = self.index()
        row = ((idx.get("packages") or {}).get(name) or {}).get("versions") or {}
        meta = row.get(version)
        if not isinstance(meta, dict):
            raise FileNotFoundError(f"not-in-index:{name}@{version}")
        rel = str(meta.get("blob") or "")
        blob_path = self.root / rel
        if not blob_path.is_file():
            raise FileNotFoundError(f"missing-blob:{rel}")
        digest = sha256_file(blob_path)
        expected = str(meta.get("sha256") or "")
        if expected and digest != expected:
            raise ValueError(f"blob-sha-mismatch:{rel}")
        pkg = _read(blob_path)
        return pkg, rel

    def verify(self, pkg: dict[str, Any]) -> dict[str, Any]:
        sig = str(pkg.get("signature") or "")
        if not sig.startswith(SIG_PREFIX) or sig != sign(pkg):
            return {
                "error": "signature-verification-failed",
                "ok": False,
                "refused": True,
            }
        return {"ok": True, "refused": False}

    def install(self, name: str, version: str, prefix: Path) -> dict[str, Any]:
        try:
            pkg, rel = self._load_blob(name, version)
        except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
            return {"error": str(exc), "ok": False, "refused": True}
        chk = self.verify(pkg)
        if not chk.get("ok"):
            return chk
        dest = prefix / "packages" / name
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True, exist_ok=True)
        for rel_file, body in (pkg.get("files") or {}).items():
            path = dest / str(rel_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(str(body), encoding="utf-8")
        lock_path = prefix / "lockfile.json"
        lock = _read(lock_path) if lock_path.is_file() else {"history": [], "pins": {}}
        prev = lock.get("pins", {}).get(name)
        if prev:
            lock.setdefault("history", []).append({"name": name, "version": prev})
        lock.setdefault("pins", {})[name] = version
        _write(lock_path, lock)
        return {
            "blob": rel,
            "lockfile": "lockfile.json",
            "ok": True,
            "pin": version,
            "prefix_files": sorted(p.name for p in dest.rglob("*") if p.is_file()),
        }

    def upgrade(self, name: str, prefix: Path) -> dict[str, Any]:
        idx = self.index()
        versions = list(
            (((idx.get("packages") or {}).get(name) or {}).get("versions") or {}).keys()
        )
        if not versions:
            return {"error": "no-versions", "ok": False}
        latest = sorted(versions)[-1]
        return self.install(name, latest, prefix)

    def rollback(self, name: str, prefix: Path) -> dict[str, Any]:
        lock_path = prefix / "lockfile.json"
        if not lock_path.is_file():
            return {"error": "no-lockfile", "ok": False}
        lock = _read(lock_path)
        hist = lock.get("history") or []
        prev = None
        rest = []
        for row in reversed(hist):
            if prev is None and row.get("name") == name:
                prev = row.get("version")
                continue
            rest.append(row)
        rest.reverse()
        if not prev:
            return {"error": "no-history", "ok": False}
        lock["history"] = rest
        _write(lock_path, lock)
        result = self.install(name, str(prev), prefix)
        # install would re-push the then-current pin into history; drop that
        lock2 = _read(lock_path)
        if lock2.get("history"):
            lock2["history"] = rest
            _write(lock_path, lock2)
        result["rolled_back_to"] = prev
        return result

    def export_to(self, dest: Path) -> Path:
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(self.root, dest)
        return dest

    def pin(self, prefix: Path, name: str) -> str | None:
        lock_path = prefix / "lockfile.json"
        if not lock_path.is_file():
            return None
        return (_read(lock_path).get("pins") or {}).get(name)
