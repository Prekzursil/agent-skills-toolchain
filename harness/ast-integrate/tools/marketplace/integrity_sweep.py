"""Named blob/index integrity sweep (IMP-0123).

The sweep walks the WHOLE blob store single-threaded, hashes every object it
visits (``coverage_count``) and compares the index entries against the live
digests.  A sweep is healthy only when it found no drift AND its coverage
equals the store's object count - a budget-capped sample can never be
reported as clean.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

WORKERS = 1  # the sweep is deliberately single-threaded (bounded, auditable)


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

    def list_object_paths(self) -> list[Path]:
        """Every stored object (sorted), ignoring in-flight ``.tmp`` files."""
        return sorted(
            p for p in self.objects.iterdir() if p.is_file() and not p.name.endswith(".tmp")
        )

    def object_count(self) -> int:
        return len(self.list_object_paths())


@dataclass
class SweepResult:
    healthy: bool
    findings: list[Finding] = field(default_factory=list)
    named_drift_entries: list[str] = field(default_factory=list)
    coverage_count: int = 0
    store_object_count: int = 0
    coverage_equals_object_count: bool = True
    workers: int = WORKERS
    elapsed_seconds: float = 0.0
    unverified_entries: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "healthy": self.healthy,
            "findings": [f.as_dict() for f in self.findings],
            "named_drift_entries": list(self.named_drift_entries),
            "coverage_count": self.coverage_count,
            "store_object_count": self.store_object_count,
            "coverage_equals_object_count": self.coverage_equals_object_count,
            "workers": self.workers,
            "unverified_entries": list(self.unverified_entries),
        }


class SweepBudget:
    def __init__(self, max_objects: int = 10_000, max_seconds: float = 30.0) -> None:
        self.max_objects = int(max_objects)
        self.max_seconds = float(max_seconds)


def plant_named_packages(
    root: Path,
    packages: dict[str, bytes],
    extra_blobs: dict[str, bytes] | list[bytes] | None = None,
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
    index.path.write_text(json.dumps({"entries": entries}, indent=2) + "\n", encoding="utf-8")
    return store, index


def run_sweep(store: BlobStore, index: Index, budget: SweepBudget | None = None) -> SweepResult:
    """Hash every object in the store (within ``budget``) and check the index against it."""
    started = time.monotonic()
    paths = store.list_object_paths()
    store_object_count = len(paths)
    max_objects = budget.max_objects if budget is not None else None
    max_seconds = budget.max_seconds if budget is not None else None

    live: dict[str, str] = {}  # stored name -> live digest of the bytes on disk
    coverage = 0
    for path in paths:
        if max_objects is not None and coverage >= max(0, max_objects):
            break
        if max_seconds is not None and (time.monotonic() - started) > max_seconds:
            break
        live[path.name] = _digest(path.read_bytes())
        coverage += 1

    findings: list[Finding] = []
    named: list[str] = []
    unverified: list[str] = []
    for entry in index.entries:
        digest = entry["digest"]
        name = entry["id"]
        if digest in live:
            if live[digest] != digest:
                findings.append(Finding("blob-digest-mismatch", [name], digest))
                findings.append(Finding("index-blob-mismatch", [name], digest))
                named.append(name)
            continue
        if not (store.objects / digest).is_file():
            findings.append(Finding("missing-blob", [name], digest))
            named.append(name)
        else:
            unverified.append(name)  # present but not hashed within the budget

    complete = coverage == store_object_count
    return SweepResult(
        healthy=not findings and complete,
        findings=findings,
        named_drift_entries=sorted(set(named)),
        coverage_count=coverage,
        store_object_count=store_object_count,
        coverage_equals_object_count=complete,
        workers=WORKERS,
        elapsed_seconds=time.monotonic() - started,
        unverified_entries=sorted(unverified),
    )
