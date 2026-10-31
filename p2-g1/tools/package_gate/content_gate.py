"""Package content gate: exclusion set + size ceiling. Independent planted refusals."""
from __future__ import annotations

import json
import tarfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator

HERE = Path(__file__).resolve().parent
OVERSIZE_BYTES = 200 * 1024 * 1024
SYNTHETIC_CREDENTIAL = "ghp_SYNTHETIC_IMP0464_NOT_A_REAL_SECRET"
SIZE_CEILING = OVERSIZE_BYTES


@dataclass
class FileRow:
    relpath: str
    is_dir: bool
    size: int


@dataclass
class ExclusionSet:
    patterns: list[dict[str, Any]]
    size_ceiling_bytes: int = SIZE_CEILING

    def with_extra(self, extra: list[dict[str, Any]]) -> "ExclusionSet":
        return ExclusionSet(
            patterns=list(self.patterns) + list(extra),
            size_ceiling_bytes=self.size_ceiling_bytes,
        )


@dataclass
class GateResult:
    ok: bool
    reasons: list[str] = field(default_factory=list)
    pattern_match_counts: dict[str, int] = field(default_factory=dict)
    hits: list[dict[str, str]] = field(default_factory=list)
    files: list[FileRow] = field(default_factory=list)
    packed_file_count: int = 0
    packed_bytes: int = 0
    packed_members: list[str] = field(default_factory=list)
    total_bytes: int = 0
    packed_file: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "reasons": list(self.reasons),
            "pattern_match_counts": dict(self.pattern_match_counts),
            "hits": [{"relpath": h.get("relpath", ""), "pattern": h.get("pattern", "")} for h in self.hits],
            "packed_file_count": self.packed_file_count,
            "packed_bytes": self.packed_bytes,
            "total_bytes": self.total_bytes,
            "packed_members": list(self.packed_members),
        }


def load_exclusion_set(path: Path | None = None) -> ExclusionSet:
    src = Path(path) if path else HERE / "exclusion_set.json"
    doc = json.loads(src.read_text(encoding="utf-8"))
    return ExclusionSet(
        patterns=list(doc.get("patterns") or []),
        size_ceiling_bytes=int(doc.get("size_ceiling_bytes") or SIZE_CEILING),
    )


def write_clean_tree(root: Path) -> Path:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text("clean package\n", encoding="utf-8")
    (root / "src").mkdir(exist_ok=True)
    (root / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (root / "plugin.json").write_text('{"name":"clean","version":"0.0.1"}\n', encoding="utf-8")
    return root


def plant_git(root: Path) -> Path:
    git = Path(root) / ".git"
    git.mkdir(parents=True, exist_ok=True)
    (git / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (git / "config").write_text("[core]\n\trepositoryformatversion = 0\n", encoding="utf-8")
    return git


def plant_oversize(root: Path) -> Path:
    path = Path(root) / "payload.bin"
    path.parent.mkdir(parents=True, exist_ok=True)
    # 200 MiB on disk. Seek+write is enough on NTFS/ext4.
    with path.open("wb") as fh:
        fh.seek(OVERSIZE_BYTES - 1)
        fh.write(b"\0")
    return path


def plant_credential(root: Path, name: str = ".env") -> Path:
    path = Path(root) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if name.endswith(".json"):
        path.write_text(json.dumps({"token": SYNTHETIC_CREDENTIAL}) + "\n", encoding="utf-8")
    else:
        path.write_text(f"GITHUB_TOKEN={SYNTHETIC_CREDENTIAL}\n", encoding="utf-8")
    return path


def plant_pycache(root: Path) -> Path:
    d = Path(root) / "__pycache__"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "app.cpython-312.pyc"
    p.write_bytes(b"\x00pyc")
    return p


def plant_log(root: Path) -> Path:
    p = Path(root) / "build.log"
    p.write_text("log line\n", encoding="utf-8")
    return p


def plant_transcript(root: Path) -> Path:
    p = Path(root) / "session.transcript.jsonl"
    p.write_text("{}\n", encoding="utf-8")
    return p


def _iter_files(root: Path) -> Iterator[Path]:
    for path in sorted(Path(root).rglob("*")):
        yield path


def _match(pattern: dict[str, Any], rel: str, is_dir: bool, size: int, body: bytes | None) -> bool:
    kind = str(pattern.get("kind") or "")
    value = str(pattern.get("value") or "")
    posix = rel.replace("\\", "/")
    parts = posix.split("/")
    if kind == "dirname":
        return value in parts or posix == value or posix.startswith(value + "/")
    if kind == "suffix":
        return posix.endswith(value)
    if kind == "basename":
        return Path(posix).name == value
    if kind == "name-contains":
        return value in Path(posix).name
    if kind == "oversize":
        return (not is_dir) and size >= int(pattern.get("value") or OVERSIZE_BYTES)
    if kind == "credential-file":
        if Path(posix).name != value and posix != value:
            return False
        if body is None:
            return True
        return SYNTHETIC_CREDENTIAL.encode("ascii") in body or b"token" in body.lower() or b"GITHUB_TOKEN" in body
    return False


def evaluate(
    root: Path,
    exclusion: ExclusionSet | None = None,
    pack_to: Path | None = None,
) -> GateResult:
    root = Path(root)
    excl = exclusion or load_exclusion_set()
    counts = {str(p.get("id")): 0 for p in excl.patterns}
    hits: list[dict[str, str]] = []
    files: list[FileRow] = []
    reasons: list[str] = []
    total = 0
    for path in _iter_files(root):
        rel = path.relative_to(root).as_posix()
        is_dir = path.is_dir()
        size = 0 if is_dir else path.stat().st_size
        files.append(FileRow(relpath=rel, is_dir=is_dir, size=size))
        if not is_dir:
            total += size
        body = None
        if (not is_dir) and size <= 1_000_000:
            try:
                body = path.read_bytes()
            except OSError:
                body = None
        for pat in excl.patterns:
            if _match(pat, rel, is_dir, size, body):
                pid = str(pat.get("id"))
                counts[pid] = counts.get(pid, 0) + 1
                hits.append({"relpath": rel, "pattern": pid})
                klass = str(pat.get("failure_class") or pid)
                if klass not in reasons:
                    reasons.append(klass)
    if total >= excl.size_ceiling_bytes and "size-ceiling-exceeded" not in reasons:
        reasons.append("size-ceiling-exceeded")
        if counts.get("oversize-file", 0) == 0:
            counts["oversize-file"] = counts.get("oversize-file", 0)
    ok = not reasons
    packed_members: list[str] = []
    packed_bytes = 0
    packed_count = 0
    packed_file = None
    if ok and pack_to is not None:
        pack_to = Path(pack_to)
        pack_to.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(pack_to, "w:gz") as tf:
            for path in _iter_files(root):
                rel = path.relative_to(root).as_posix()
                tf.add(path, arcname=rel)
                if path.is_file():
                    packed_members.append(rel)
                    packed_bytes += path.stat().st_size
                    packed_count += 1
        packed_file = str(pack_to)
    elif (not ok) and pack_to is not None and Path(pack_to).exists():
        Path(pack_to).unlink()
    return GateResult(
        ok=ok,
        reasons=reasons,
        pattern_match_counts=counts,
        hits=hits,
        files=files,
        packed_file_count=packed_count,
        packed_bytes=packed_bytes,
        packed_members=packed_members,
        total_bytes=total,
        packed_file=packed_file,
    )


def merge_counts(rows: Iterable[dict[str, int]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        for k, v in (row or {}).items():
            out[k] = out.get(k, 0) + int(v or 0)
    return out


def dead_or_broken_patterns(merged: dict[str, int]) -> list[str]:
    return sorted(k for k, v in merged.items() if int(v or 0) == 0)
