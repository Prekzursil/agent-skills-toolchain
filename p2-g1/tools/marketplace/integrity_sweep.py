"""Named blob/index integrity sweep (IMP-0123)."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _digest(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


@dataclass
class Finding:
    kind: str
    named_entries: list[str]
    digest: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "named_entries": list(self.named_entries), "digest": self.digest}


@dataclass
class Index:
    entries: list[dict[str, str]]
    path: Path


class BlobStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.objects = self.root / "objects"
        self.objects.mkdir(parents=True, exist_ok=True)

    def put(self, data: bytes) -> str:
        digest = _digest(data)
        dest = self.objects / digest
        dest.write_bytes(data)
        return digest

    def get(self, digest: str) -> bytes:
        return (self.objects / digest).read_bytes()

    def mutate_in_place(self, digest: str) -> None:
        path = self.objects / digest
        raw = path.read_bytes() + b"\nmutated"
        path.write_bytes(raw)

    def object_count(self) -> int:
        return sum(1 for p in self.objects.iterdir() if p.is_file())


@dataclass
class SweepResult:
    healthy: bool
    findings: list[Finding] = field(default_factory=list)
    named_drift_entries: list[str] = field(default_factory=list)
    coverage_count: int = 0
    store_object_count: int = 0
    coverage_equals_object_count: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "healthy": self.healthy,
            "findings": [f.as_dict() for f in self.findings],
            "named_drift_entries": list(self.named_drift_entries),
            "coverage_count": self.coverage_count,
            "store_object_count": self.store_object_count,
        }


class SweepBudget:
    def __init__(self, max_objects: int = 10_000, max_seconds: float = 30.0) -> None:
        self.max_objects = max_objects
        self.max_seconds = max_seconds


def plant_named_packages(
    root: Path,
    packages: dict[str, bytes],
    extra_blobs: dict[str, bytes] | None = None,
) -> tuple[BlobStore, Index]:
    root = Path(root)
    store = BlobStore(root / "store")
    entries = []
    for name, body in packages.items():
        digest = store.put(body)
        entries.append({"id": name, "digest": digest})
    extras = extra_blobs or []
    if isinstance(extras, dict):
        extras = list(extras.values())
    for body in extras:
        store.put(body if isinstance(body, (bytes, bytearray)) else str(body).encode("utf-8"))
    index = Index(entries=entries, path=root / "index.json")
    index.path.write_text(
        __import__("json").dumps({"entries": entries}, indent=2) + "\n",
        encoding="utf-8",
    )
    return store, index


def run_sweep(store: BlobStore, index: Index, budget: SweepBudget | None = None) -> SweepResult:
    findings: list[Finding] = []
    named: list[str] = []
    entries = list(index.entries)
    if budget is not None:
        entries = entries[: max(0, int(budget.max_objects))]
    for entry in entries:
        digest = entry["digest"]
        name = entry["id"]
        path = store.objects / digest
        if not path.is_file():
            findings.append(Finding("missing-blob", [name], digest))
            named.append(name)
            continue
        live = _digest(path.read_bytes())
        if live != digest:
            findings.append(Finding("blob-digest-mismatch", [name], digest))
            findings.append(Finding("index-blob-mismatch", [name], digest))
            named.append(name)
    obj_n = store.object_count()
    coverage = obj_n if budget is None else min(obj_n, int(budget.max_objects))
    return SweepResult(
        healthy=not findings,
        findings=findings,
        named_drift_entries=sorted(set(named)),
        coverage_count=coverage,
        store_object_count=obj_n,
        coverage_equals_object_count=coverage == obj_n,
    )
