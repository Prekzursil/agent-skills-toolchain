#!/usr/bin/env python3
"""Source-baseline-before-fusion ordering invariant (WFA-0133).

Rule: a fusion may be scored only after every sources_resolved workflow
has a persisted baseline row on the same matched cases, against the
pinned metric registry. Unmeasured sources fail closed. The named
failure 'fused workflow performs worse than every source' (FC-11333)
is then a predicate over those rows, not a slogan.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from corpus import METRIC_REGISTRY, canonical, compute_metrics, sha256_text

KIND_SOURCE = "SOURCE_MEASURE"
KIND_FUSION = "FUSION_SCORE"
KIND_REFUSAL = "REFUSAL"


class FusionScoreRefused(Exception):
    def __init__(self, reason: str, missing: list[str] | None = None):
        super().__init__(reason)
        self.reason = reason
        self.missing = list(missing or [])


def worse_than_every_source(
    fusion_metrics: dict[str, float],
    source_metrics: list[dict[str, float]],
    registry: list[dict[str, Any]] | None = None,
) -> bool:
    """True iff fusion is strictly worse than every source on EVERY metric."""
    if not source_metrics:
        return False
    regs = registry if registry is not None else METRIC_REGISTRY
    for spec in regs:
        mid = spec["id"]
        hib = bool(spec["higher_is_better"])
        f = float(fusion_metrics[mid])
        extrema = [float(s[mid]) for s in source_metrics]
        if hib:
            if not (f < min(extrema)):
                return False
        else:
            if not (f > max(extrema)):
                return False
    return True


class BaselineLedger:
    def __init__(
        self,
        path: Path,
        *,
        registry: list[dict[str, Any]] | None = None,
        registry_sha: str | None = None,
    ) -> None:
        self.path = Path(path)
        self.registry = list(registry if registry is not None else METRIC_REGISTRY)
        self.registry_sha = registry_sha or sha256_text(canonical(self.registry))
        self.events: list[dict[str, Any]] = []
        self._seq = 0
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def persist(self) -> None:
        payload = {
            "registry_sha256": self.registry_sha,
            "events": self.events,
        }
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        raw = (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode("utf-8")
        tmp.write_bytes(raw)
        with tmp.open("rb+") as fh:
            fh.flush()
            os.fsync(fh.fileno())
        tmp.replace(self.path)
        with self.path.open("rb+") as fh:
            fh.flush()
            os.fsync(fh.fileno())

    def write_close_marker(self, marker: Path) -> dict[str, Any]:
        self.persist()
        digest = hashlib.sha256(self.path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        last_source = max(
            (e["seq"] for e in self.events if e["kind"] == KIND_SOURCE), default=-1
        )
        body = canonical(
            {
                "closed": True,
                "ledger_sha256": digest,
                "last_source_seq": last_source,
                "ts_ns": time.time_ns(),
            }
        )
        marker.parent.mkdir(parents=True, exist_ok=True)
        tmp = marker.with_suffix(marker.suffix + ".tmp")
        tmp.write_text(body + "\n", encoding="utf-8")
        with tmp.open("rb+") as fh:
            fh.flush()
            os.fsync(fh.fileno())
        tmp.replace(marker)
        with marker.open("rb+") as fh:
            fh.flush()
            os.fsync(fh.fileno())
        st = marker.stat()
        return {
            "path": str(marker),
            "mtime_ns": int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9))),
            "ledger_sha256": digest,
            "last_source_seq": last_source,
        }

    def _append(self, kind: str, extra: dict[str, Any]) -> dict[str, Any]:
        self._seq += 1
        event = {
            "seq": self._seq,
            "ts_ns": time.time_ns(),
            "kind": kind,
            "registry_sha256": self.registry_sha,
            **extra,
        }
        self.events.append(event)
        self.persist()
        return event

    def has_baseline(self, merge_unit_id: str, source_id: str, case_ids: list[str]) -> bool:
        want = set(case_ids)
        for ev in self.events:
            if ev.get("kind") != KIND_SOURCE:
                continue
            if ev.get("merge_unit_id") != merge_unit_id:
                continue
            if ev.get("workflow_id") != source_id:
                continue
            if set(ev.get("case_ids") or []) != want:
                continue
            if ev.get("registry_sha256") != self.registry_sha:
                continue
            return True
        return False

    def measure_source(self, unit: dict[str, Any], source_id: str) -> dict[str, Any]:
        if source_id not in (unit.get("sources_resolved") or []):
            raise FusionScoreRefused("not-a-resolved-source", [source_id])
        metrics = compute_metrics(unit, source_id)
        return self._append(
            KIND_SOURCE,
            {
                "merge_unit_id": unit["id"],
                "workflow_id": source_id,
                "role": "source",
                "case_ids": list(unit["matched_cases"]),
                "metrics": metrics,
            },
        )

    def measure_all_sources(self, unit: dict[str, Any]) -> list[dict[str, Any]]:
        return [self.measure_source(unit, sid) for sid in unit["sources_resolved"]]

    def missing_sources(self, unit: dict[str, Any]) -> list[str]:
        cases = list(unit["matched_cases"])
        return [
            sid
            for sid in unit["sources_resolved"]
            if not self.has_baseline(unit["id"], sid, cases)
        ]

    def score_fusion(
        self,
        unit: dict[str, Any],
        *,
        registry_sha: str | None = None,
    ) -> dict[str, Any]:
        pin = registry_sha if registry_sha is not None else self.registry_sha
        if pin != self.registry_sha:
            ev = self._append(
                KIND_REFUSAL,
                {
                    "merge_unit_id": unit["id"],
                    "workflow_id": unit["fusion_id"],
                    "role": "fusion",
                    "reason": "metric-registry-mismatch",
                    "missing": [],
                },
            )
            return {
                "accepted": False,
                "reason": "metric-registry-mismatch",
                "missing": [],
                "event": ev,
            }
        missing = self.missing_sources(unit)
        if missing:
            ev = self._append(
                KIND_REFUSAL,
                {
                    "merge_unit_id": unit["id"],
                    "workflow_id": unit["fusion_id"],
                    "role": "fusion",
                    "reason": "unmeasured-sources",
                    "missing": missing,
                    "case_ids": list(unit["matched_cases"]),
                },
            )
            return {
                "accepted": False,
                "reason": "unmeasured-sources",
                "missing": missing,
                "event": ev,
            }
        metrics = compute_metrics(unit, unit["fusion_id"])
        source_metrics = [
            ev["metrics"]
            for ev in self.events
            if ev.get("kind") == KIND_SOURCE
            and ev.get("merge_unit_id") == unit["id"]
            and ev.get("workflow_id") in set(unit["sources_resolved"])
        ]
        worse = worse_than_every_source(metrics, source_metrics, self.registry)
        ev = self._append(
            KIND_FUSION,
            {
                "merge_unit_id": unit["id"],
                "workflow_id": unit["fusion_id"],
                "role": "fusion",
                "case_ids": list(unit["matched_cases"]),
                "metrics": metrics,
                "worse_than_every_source": worse,
            },
        )
        return {
            "accepted": True,
            "reason": "ok",
            "missing": [],
            "metrics": metrics,
            "worse_than_every_source": worse,
            "event": ev,
        }


def both_states(units: list[dict[str, Any]], scratch: Path) -> dict[str, Any]:
    """Fail-closed then fail-open on the same fusion. Uses a scratch ledger."""
    unit = units[0]
    book = BaselineLedger(scratch)
    refused = book.score_fusion(unit)
    partial = book.measure_source(unit, unit["sources_resolved"][0])
    still = book.score_fusion(unit)
    rest = book.measure_all_sources(unit)
    accepted = book.score_fusion(unit)
    mutated = book.score_fusion(unit, registry_sha="0" * 64)
    planted = next(u for u in units if u.get("planted_worse_than_every_source"))
    planted_book = BaselineLedger(scratch.with_name(scratch.stem + "-planted.json"))
    planted_book.measure_all_sources(planted)
    planted_score = planted_book.score_fusion(planted)
    silent = next(u for u in units if not u.get("planted_worse_than_every_source"))
    silent_book = BaselineLedger(scratch.with_name(scratch.stem + "-silent.json"))
    silent_book.measure_all_sources(silent)
    silent_score = silent_book.score_fusion(silent)
    ok = (
        refused.get("accepted") is False
        and refused.get("reason") == "unmeasured-sources"
        and set(refused.get("missing") or []) == set(unit["sources_resolved"])
        and still.get("accepted") is False
        and accepted.get("accepted") is True
        and mutated.get("accepted") is False
        and mutated.get("reason") == "metric-registry-mismatch"
        and planted_score.get("worse_than_every_source") is True
        and silent_score.get("worse_than_every_source") is False
    )
    return {
        "unmeasured_refused": refused.get("accepted") is False,
        "unmeasured_missing": refused.get("missing"),
        "partial_source_measured": partial["workflow_id"],
        "partial_still_refused": still.get("accepted") is False,
        "partial_missing": still.get("missing"),
        "all_sources_measured_n": len(rest),
        "measured_accepted": accepted.get("accepted") is True,
        "registry_mismatch_refused": mutated.get("reason") == "metric-registry-mismatch",
        "planted_worse_fires": planted_score.get("worse_than_every_source") is True,
        "honest_fusion_silent": silent_score.get("worse_than_every_source") is False,
        "discriminates": ok,
        "ok": ok,
    }
