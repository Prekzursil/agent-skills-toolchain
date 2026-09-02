"""Loud capability-mismatch degradation: DEGRADED, never silent SUCCESS."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

VERDICT_DEGRADED = "DEGRADED"
VERDICT_SUCCESS = "SUCCESS"


@dataclass
class Mismatch:
    field: str
    expected: Any
    observed: Any

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "expected": self.expected,
            "observed": self.observed,
        }


@dataclass
class DispatchResult:
    verdict: str
    mismatches: list[Mismatch] = field(default_factory=list)
    ordinary_looking_success: bool = False
    substitution_refused: bool = False
    retry_refused: bool = False


class DegradeLoudly:
    VERDICT_DEGRADED = VERDICT_DEGRADED
    VERDICT_SUCCESS = VERDICT_SUCCESS

    def seed_partial(self, path: Path, body: bytes) -> None:
        Path(path).write_bytes(body)

    def mismatch_request(self, path: Path) -> dict[str, Any]:
        return {"path": str(path), "streaming": True, "vendor": "openai"}

    def matched_request(self, path: Path) -> dict[str, Any]:
        return {"path": str(path), "streaming": False, "vendor": "anthropic"}

    def openai_fixture(self, streaming: bool = False) -> dict[str, Any]:
        return {"vendor": "openai", "streaming": streaming, "capable": False}

    def anthropic_fixture(self) -> dict[str, Any]:
        return {"vendor": "anthropic", "streaming": False, "capable": True}

    def dispatch(self, req: dict[str, Any], vendor: dict[str, Any]) -> DispatchResult:
        mismatches: list[Mismatch] = []
        if bool(req.get("streaming")) != bool(vendor.get("streaming")):
            mismatches.append(
                Mismatch("streaming", req.get("streaming"), vendor.get("streaming"))
            )
        if mismatches:
            return DispatchResult(
                verdict=VERDICT_DEGRADED,
                mismatches=mismatches,
                ordinary_looking_success=False,
            )
        return DispatchResult(verdict=VERDICT_SUCCESS, ordinary_looking_success=True)

    def dispatch_with_fallback(
        self,
        req: dict[str, Any],
        weak: dict[str, Any],
        capable: dict[str, Any],
    ) -> DispatchResult:
        live = self.dispatch(req, weak)
        if live.verdict == VERDICT_DEGRADED:
            live.substitution_refused = True
            return live
        return self.dispatch(req, capable)

    def assert_partial_preserved(self, path: Path, before: bytes) -> None:
        live_path = Path(path)
        if not live_path.is_file():
            raise AssertionError("partial work product was discarded")
        live = live_path.read_bytes()
        if live != before:
            raise AssertionError("partial work product was not preserved")

    def retry_mismatch(self, live: DispatchResult) -> DispatchResult:
        return DispatchResult(
            verdict=VERDICT_DEGRADED,
            mismatches=list(live.mismatches),
            retry_refused=True,
            ordinary_looking_success=False,
        )


degrade_loudly = DegradeLoudly()

__all__ = [
    "DegradeLoudly",
    "DispatchResult",
    "Mismatch",
    "VERDICT_DEGRADED",
    "VERDICT_SUCCESS",
    "degrade_loudly",
]
