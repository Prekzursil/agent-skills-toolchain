"""Immutable Phase-0 baseline capture (TST-0302)."""
from __future__ import annotations

import json
import platform
import sys
from pathlib import Path
from typing import Any

from gitutil import inspect_repo
from metrics import measure_at_sha

STATUS_IMMUTABLE = "IMMUTABLE"
STATUS_PROVISIONAL = "PROVISIONAL"
KIND = "phase0-baseline"
REQUIRED = ("id", "status", "commit_sha", "metrics", "environment")


class BaselineImmutableError(Exception):
    pass


class DirtyTreeRejected(Exception):
    pass


class EmptyInputRefused(Exception):
    pass


class NoCommitAnchorError(Exception):
    pass


def schema_errors(record: dict[str, Any]) -> list[str]:
    errs = []
    for k in REQUIRED:
        if k not in record:
            errs.append(f"missing:{k}")
    if record.get("dirty") and record.get("status") == STATUS_IMMUTABLE:
        errs.append("dirty-must-be-provisional")
    return errs


def mutant_ignore_dirty_status(dirty: bool) -> str:
    return STATUS_IMMUTABLE


class BaselineStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._rows: list[dict[str, Any]] = []
        if self.path.is_file():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    self._rows.append(json.loads(line))

    def append(self, rec: dict[str, Any]) -> None:
        self._rows.append(rec)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")

    def get(self, baseline_id: str) -> dict[str, Any] | None:
        for rec in reversed(self._rows):
            if rec.get("id") == baseline_id:
                return rec
        return None


def capture_baseline(
    repo: Path,
    store: BaselineStore,
    baseline_id: str,
    *,
    accept_dirty: bool = False,
) -> dict[str, Any]:
    insp = inspect_repo(repo)
    if not insp.commit_sha:
        raise NoCommitAnchorError(str(repo))
    metrics = measure_at_sha(repo, insp.commit_sha)
    if int(metrics.get("input_cardinality") or 0) < 1:
        raise EmptyInputRefused("no cases/")
    dirty = bool(insp.dirty)
    if dirty and not accept_dirty:
        raise DirtyTreeRejected(str(repo))
    rec = {
        "id": baseline_id,
        "kind": KIND,
        "status": STATUS_PROVISIONAL if dirty else STATUS_IMMUTABLE,
        "tree_state": "dirty" if dirty else "clean",
        "dirty": dirty,
        "commit_sha": insp.commit_sha,
        "metrics": metrics,
        "measure_source": metrics["measure_source"],
        "environment": {
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
        },
    }
    store.append(rec)
    return rec


def rematerialize_from_sha(repo: Path, sha: str) -> dict[str, Any]:
    return measure_at_sha(repo, sha)


def unsafe_overwrite(store: BaselineStore, rec: dict[str, Any]) -> dict[str, Any]:
    """Detector control: mutate an IMMUTABLE row (must be rejected by schema)."""
    planted = dict(rec)
    planted["status"] = STATUS_IMMUTABLE
    planted["dirty"] = True
    return planted
