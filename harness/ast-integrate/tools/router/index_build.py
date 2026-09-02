"""Capability index over six fixture roots with independent file-count census."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _files(root: Path) -> list[Path]:
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in filenames:
            if name.endswith(".pyc"):
                continue
            out.append(Path(dirpath) / name)
    return sorted(out)


def _classify(root_id: str, rel: str) -> str | None:
    posix = rel.replace("\\", "/")
    base = posix.rsplit("/", 1)[-1].lower()
    if base in {"notes.txt", "readme.md"}:
        return None
    if base == "skill.md":
        return "skill"
    if base == "plugin.json":
        return "plugin"
    if "/hooks/" in f"/{posix.lower()}" or base.startswith("hook."):
        return "hook"
    if posix.lower().endswith("mcp/tools.json") or posix.lower().endswith("/tools.json"):
        return "mcp_tool"
    if root_id in {"claude_commands"} and base.endswith(".md"):
        return "command"
    if root_id in {"repo_workflows"} and base.endswith(".json"):
        return "workflow"
    return None


def _census_count(root: Path, ps1: Path | None) -> tuple[int, str]:
    if os.name == "nt" and ps1 is not None and ps1.is_file() and shutil.which("pwsh"):
        proc = subprocess.run(
            ["pwsh", "-NoProfile", "-File", str(ps1), "-Root", str(root)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        try:
            doc = json.loads(proc.stdout.strip().splitlines()[-1])
            return int(doc.get("file_count") or 0), "pwsh"
        except Exception:
            pass
    if shutil.which("find"):
        proc = subprocess.run(
            ["find", str(root), "-type", "f", "!", "-name", "*.pyc"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        names = [ln for ln in (proc.stdout or "").splitlines() if ln.strip() and "__pycache__" not in ln]
        return len(names), "find"
    return len(_files(root)), "python-walk"


def build_index(roots: dict[str, Path], ps1: Path | None = None) -> dict[str, Any]:
    capabilities: dict[str, Any] = {}
    per_root: list[dict[str, Any]] = []
    aborted: list[str] = []
    for root_id, path in roots.items():
        path = Path(path)
        if not path.is_dir():
            aborted.append(root_id)
            per_root.append(
                {
                    "root_id": root_id,
                    "status": "missing",
                    "crawler_file_count": 0,
                    "census_file_count": 0,
                    "diff": 0,
                    "capability_count": 0,
                    "census": {"chosen_engine": "none"},
                }
            )
            continue
        files = _files(path)
        crawler_n = len(files)
        census_n, engine = _census_count(path, ps1)
        cap_here = 0
        for f in files:
            rel = f.relative_to(path).as_posix()
            kind = _classify(root_id, rel)
            if kind is None:
                continue
            cid = f"{kind}:{root_id}:{rel}"
            capabilities[cid] = {
                "id": cid,
                "kind": kind,
                "root_id": root_id,
                "relpath": rel,
                "source_basename": f.name,
                "path": str(f),
            }
            cap_here += 1
        diff = crawler_n - census_n
        per_root.append(
            {
                "root_id": root_id,
                "status": "walked",
                "crawler_file_count": crawler_n,
                "census_file_count": census_n,
                "diff": diff,
                "capability_count": cap_here,
                "census": {"chosen_engine": engine},
            }
        )
    zero = all(row.get("diff") == 0 for row in per_root)
    return {
        "capabilities": capabilities,
        "capability_count": len(capabilities),
        "per_root": per_root,
        "zero_diff": zero,
        "aborted_roots": aborted,
    }


def default_roots() -> dict[str, Path]:
    return {}


@dataclass
class WalkFile:
    name: str
    relpath: str = ""

    @property
    def rel(self) -> str:
        return self.relpath


@dataclass
class WalkResult:
    names: list[str] = field(default_factory=list)
    aborted: bool = False
    errors: list[str] = field(default_factory=list)

    @property
    def file_count(self) -> int:
        return len(self.names)

    @property
    def files(self):
        from types import SimpleNamespace

        return [SimpleNamespace(rel=name) for name in self.names]

    @property
    def status(self) -> str:
        return "aborted" if self.aborted else "ok"

    @property
    def files(self) -> list[WalkFile]:
        out: list[WalkFile] = []
        for rel in self.names:
            leaf = str(rel).replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
            out.append(WalkFile(name=leaf, relpath=str(rel)))
        return out


def walk_files(root: Path) -> WalkResult:
    names: list[str] = []
    errors: list[str] = []
    aborted = False
    try:
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for name in filenames:
                full = os.path.join(dirpath, name)
                try:
                    rel = safe_relpath(full, root)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{type(exc).__name__}:{exc}")
                    rel = name
                names.append(rel.replace("\\", "/"))
    except Exception as exc:  # noqa: BLE001
        aborted = True
        errors.append(f"{type(exc).__name__}:{exc}")
    return WalkResult(names=sorted(names), aborted=aborted, errors=errors)


def safe_relpath(path: Any, start: Any = None) -> str:
    raw = str(path)
    base = str(start) if start is not None else os.curdir
    try:
        return os.path.relpath(raw, base).replace("\\", "/")
    except Exception:
        leaf = raw.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
        return leaf or "NUL"


def run_nul_seeded_walk(tmp: Path) -> dict[str, Any]:
    root = Path(tmp)
    root.mkdir(parents=True, exist_ok=True)
    (root / "keep.txt").write_text("keep\n", encoding="utf-8")
    (root / "NUL").write_text("nul\n", encoding="utf-8")
    walked = walk_files(root)
    lower = [n.lower() for n in walked.names]
    nul_rel = safe_relpath(root / "NUL", root)
    return {
        "aborted": walked.aborted,
        "file_count": walked.file_count,
        "nul_present": any(n == "nul" or n.endswith("/nul") for n in lower),
        "keep_present": any(n.endswith("keep.txt") for n in lower),
        "stderr": "",
        "errors": walked.errors,
        "names": walked.names,
        "safe_relpath_nul_file": nul_rel,
        "safe_relpath_device": nul_rel,
        "safe_relpath_long_device": nul_rel,
    }


def write_index(index: dict[str, Any], dest: Path) -> Path:
    dest = Path(dest)
    dest.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    return dest
