"""Shared completion reducer. Exit-zero is not COMPLETE.

Call sites must import ``judge``. Exit code zero alone is structurally
insufficient: a planted local predicate that maps exit_code==0 to COMPLETE
is a different library, not this one.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

LIBRARY = "completion.reducer.judge"


@dataclass
class Observation:
    site: str = ""
    exit_code: int = 1
    state: str = ""
    artifact_path: str = ""
    repo_root: str = ""
    min_bytes: int = 0
    sentinel: str = ""
    schema_ok: bool = False
    evidence_anchor_count: int = 0
    tests_passed: bool = False
    negative_controls_ok: bool = False
    reviewer_verdict: str = ""
    open_p0_p1: int = 0
    registered: bool = False
    downstream_read_ok: bool = False


@dataclass
class Condition:
    n: int
    outcome: str
    basis: str = ""


@dataclass
class Judgment:
    verdict: str
    library: str = LIBRARY
    site: str = ""
    reason: str = ""
    failing_condition_ids: list[int] | None = None
    not_checked_ids: list[int] | None = None
    conditions: list[Condition] | None = None

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "library": self.library,
            "site": self.site,
            "reason": self.reason,
            "failing_condition_ids": list(self.failing_condition_ids or []),
            "not_checked_ids": list(self.not_checked_ids or []),
        }


def observation_from_mapping(site: str, payload: dict[str, Any] | Observation) -> Observation:
    if isinstance(payload, Observation):
        payload.site = payload.site or site
        return payload
    data = dict(payload or {})
    data.setdefault("site", site)
    return Observation(
        site=str(data.get("site") or site),
        exit_code=int(data.get("exit_code") or data.get("rc") or data.get("harvest_rc") or data.get("step_rc") or data.get("vendor_rc") or 1),
        state=str(data.get("state") or ""),
        artifact_path=str(
            data.get("artifact_path")
            or data.get("harvested")
            or data.get("artifact")
            or data.get("receipt_path")
            or data.get("workflow_artifact")
            or data.get("vendor_output")
            or data.get("output_path")
            or ""
        ),
        repo_root=str(data.get("repo_root") or ""),
        min_bytes=int(data.get("min_bytes") or 0),
        sentinel=str(data.get("sentinel") or ""),
        schema_ok=bool(data.get("schema_ok")),
        evidence_anchor_count=int(data.get("evidence_anchor_count") or 0),
        tests_passed=bool(data.get("tests_passed")),
        negative_controls_ok=bool(data.get("negative_controls_ok")),
        reviewer_verdict=str(data.get("reviewer_verdict") or ""),
        open_p0_p1=int(data.get("open_p0_p1") or 0),
        registered=bool(data.get("registered")),
        downstream_read_ok=bool(data.get("downstream_read_ok")),
    )


def judge(obs: Observation | dict[str, Any]) -> Judgment:
    if isinstance(obs, dict):
        obs = Observation(
            site=str(obs.get("site") or obs.get("harvest_rc") and "harvester" or ""),
            exit_code=int(obs.get("exit_code") or obs.get("harvest_rc") or 1),
            state=str(obs.get("state") or ""),
            artifact_path=str(obs.get("artifact_path") or obs.get("harvested") or ""),
            repo_root=str(obs.get("repo_root") or ""),
            min_bytes=int(obs.get("min_bytes") or 0),
            sentinel=str(obs.get("sentinel") or ""),
            schema_ok=bool(obs.get("schema_ok")),
            evidence_anchor_count=int(obs.get("evidence_anchor_count") or 0),
            tests_passed=bool(obs.get("tests_passed")),
            negative_controls_ok=bool(obs.get("negative_controls_ok")),
            reviewer_verdict=str(obs.get("reviewer_verdict") or ""),
            open_p0_p1=int(obs.get("open_p0_p1") or 0),
            registered=bool(obs.get("registered")),
            downstream_read_ok=bool(obs.get("downstream_read_ok")),
        )
    # Exit-zero is NOT completeness. A planted local predicate that maps
    # exit_code==0 → COMPLETE is a different library.
    path = Path(obs.artifact_path) if obs.artifact_path else None
    exists = bool(path and path.is_file())
    size_ok = bool(path and exists and path.stat().st_size >= obs.min_bytes)
    sentinel_ok = True
    if obs.sentinel and path and exists:
        sentinel_ok = obs.sentinel in path.read_text(encoding="utf-8", errors="replace")
    rows = [
        Condition(1, "SATISFIED" if exists else "UNSATISFIED", "artifact-exists"),
        Condition(2, "SATISFIED" if size_ok else "UNSATISFIED", "min-bytes"),
        Condition(3, "SATISFIED" if sentinel_ok else "UNSATISFIED", "sentinel"),
        Condition(4, "SATISFIED" if obs.schema_ok else "UNSATISFIED", "schema"),
        Condition(5, "SATISFIED" if obs.tests_passed else "UNSATISFIED", "tests"),
        Condition(6, "SATISFIED" if obs.negative_controls_ok else "UNSATISFIED", "negative-controls"),
        Condition(7, "SATISFIED" if obs.reviewer_verdict == "PASS" else "UNSATISFIED", "reviewer"),
        Condition(8, "SATISFIED" if obs.open_p0_p1 == 0 else "UNSATISFIED", "open-p0-p1"),
        Condition(9, "SATISFIED" if obs.registered else "UNSATISFIED", "registered"),
        Condition(10, "SATISFIED" if obs.downstream_read_ok else "UNSATISFIED", "downstream-read"),
        Condition(11, "SATISFIED" if str(obs.state).upper() == "SUCCESS" else "UNSATISFIED", "state"),
    ]
    failing = [c.n for c in rows if c.outcome != "SATISFIED"]
    complete = not failing
    return Judgment(
        verdict="COMPLETE" if complete else "INCOMPLETE",
        library=LIBRARY,
        site=obs.site,
        reason="shared-reducer" if complete else "predicate-failed",
        failing_condition_ids=failing,
        not_checked_ids=[],
        conditions=rows,
    )
