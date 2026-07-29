"""Role-split compute-backend contracts (references/CSIE-DESIGN.md §4, §11 R6)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from harness.contract import Unit


@dataclass(frozen=True)
class Job:
    backend: str
    ref: str
    meta: dict = field(default_factory=dict)


@dataclass(frozen=True)
class MatrixVerdict:
    repo: str
    branch: str
    head_sha: str
    platforms: dict
    all_green: bool


@dataclass(frozen=True)
class Result:
    unit_id: str
    ok: bool
    reason: str
    size: int
    artifact: str | None = None
    branch: str | None = None


@dataclass(frozen=True)
class MintedToken:
    token: str
    repo: str
    expires_at: str


@dataclass(frozen=True)
class CloneSpec:
    repo: str
    url: str
    read_only: bool = True


@runtime_checkable
class BuildBackend(Protocol):
    def submit(self, units: list[Unit], meta: dict) -> Job: ...
    def poll(self, job: Job) -> str: ...
    def harvest(self, job: Job, dest: Path) -> dict[str, Path]: ...
    def cancel(self, job: Job) -> None: ...
    def teardown(self, job: Job) -> None: ...


@runtime_checkable
class VerifyBackend(Protocol):
    def verify(self, repo: str, branch: str) -> MatrixVerdict: ...
