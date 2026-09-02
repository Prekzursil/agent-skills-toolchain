"""Destruction oracle: hash owner-visible paths before and after an operation.

Nothing present beforehand may be missing or altered unless the operation
declared that change. Skipped paths are NOT-CHECKED and are counted
separately from verified-unchanged. Folding skips into the pass count is
the lie this oracle exists to refuse.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from lifecycle import ChangeSet
from walker import census, hashed_only, skipped_only


@dataclass
class OracleResult:
    operation: str
    paths_hashed: int
    paths_skipped: int
    paths_altered: int
    verified_unchanged: list[str]
    skipped_paths: list[str]
    loss: list[dict[str, Any]]
    declared_ok: list[str]
    skipped_then_missing: list[str]
    undeclared_creates: list[str]
    skipped_are_not_checked: bool = True
    skip_folded_into_pass: bool = False
    declared_change_set: dict[str, list[str]] = field(default_factory=dict)

    @property
    def silent(self) -> bool:
        return not self.loss

    @property
    def lying_pass_count(self) -> int:
        """What a dishonest oracle would report by treating skips as pass."""
        return self.paths_hashed + self.paths_skipped

    @property
    def honest_pass_count(self) -> int:
        return len(self.verified_unchanged)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.operation,
            "paths_hashed": self.paths_hashed,
            "paths_skipped": self.paths_skipped,
            "paths_altered": self.paths_altered,
            "skipped_are_not_checked": True,
            "skip_folded_into_pass": False,
            "verified_unchanged_count": len(self.verified_unchanged),
            "verified_unchanged": sorted(self.verified_unchanged),
            "skipped_paths": sorted(self.skipped_paths),
            "loss": self.loss,
            "declared_ok": sorted(self.declared_ok),
            "skipped_then_missing": sorted(self.skipped_then_missing),
            "undeclared_creates": sorted(self.undeclared_creates),
            "oracle_silent": self.silent,
            "honest_pass_count": self.honest_pass_count,
            "lying_pass_count_if_skips_folded": self.lying_pass_count,
            "declared_change_set": self.declared_change_set,
        }


def compare(
    operation: str,
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
    declared: ChangeSet,
) -> OracleResult:
    declared_paths = declared.all_paths()
    hashed_b = hashed_only(before)
    skipped_b = skipped_only(before)
    hashed_a = hashed_only(after)
    loss: list[dict[str, Any]] = []
    verified: list[str] = []
    altered: list[str] = []
    declared_ok: list[str] = []
    skipped_then_missing: list[str] = []

    for path, row in hashed_b.items():
        nxt = after.get(path)
        missing = nxt is None or nxt.get("skipped")
        changed = (not missing) and nxt.get("sha256") != row.get("sha256")
        if missing or changed:
            altered.append(path)
            if path in declared_paths:
                declared_ok.append(path)
            else:
                loss.append(
                    {
                        "path": path,
                        "kind": "missing" if missing else "hash-changed",
                        "before_sha256": row.get("sha256"),
                        "after_sha256": None
                        if missing
                        else nxt.get("sha256"),
                    }
                )
        else:
            verified.append(path)

    for path in skipped_b:
        if path not in after:
            skipped_then_missing.append(path)

    undeclared_creates = sorted(
        p
        for p in hashed_a
        if p not in hashed_b and p not in declared_paths
    )

    return OracleResult(
        operation=operation,
        paths_hashed=len(hashed_b),
        paths_skipped=len(skipped_b),
        paths_altered=len(altered),
        verified_unchanged=verified,
        skipped_paths=list(skipped_b),
        loss=loss,
        declared_ok=declared_ok,
        skipped_then_missing=skipped_then_missing,
        undeclared_creates=undeclared_creates,
        declared_change_set=declared.as_dict(),
    )


def run_op(
    profile: Path,
    operation: str,
    apply_fn: Callable[[Path], None],
    declared: ChangeSet,
) -> OracleResult:
    before = census(profile)
    apply_fn(profile)
    after = census(profile)
    return compare(operation, before, after, declared)
