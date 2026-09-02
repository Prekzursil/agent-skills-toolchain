#!/usr/bin/env python3
"""CNF-0135 executable disagreement closer.

Confirmer and implementer settle only by a test both accepted before it ran.
Seniority, vote, rhetoric, and authority-toned pressure cannot close or flip.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

FORBIDDEN_METHODS = frozenset(
    {
        "seniority",
        "vote",
        "rhetoric",
        "majority",
        "authority",
        "chair",
        "order",
    }
)
SETTLED_STATUSES = frozenset(
    {"CLOSED_CONFIRMER_REVISED", "CLOSED_IMPLEMENTER_REVISED"}
)


class TiebreakError(Exception):
    pass


class IllegalClose(TiebreakError):
    pass


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class StepClock:
    def __init__(self, start: Optional[datetime] = None) -> None:
        self._t = start or datetime(2026, 8, 24, 17, 0, 0, tzinfo=timezone.utc)

    def stamp(self) -> str:
        self._t = self._t + timedelta(seconds=1)
        return iso(self._t)


@dataclass
class Party:
    role: str
    identity: str
    position: str
    vendor: str = "local-sim"

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "identity": self.identity,
            "vendor": self.vendor,
            "position": self.position,
        }


@dataclass
class RegisteredTest:
    test_id: str
    description: str
    preregistered_at: str
    accepted_by_implementer_at: str
    accepted_by_confirmer_at: str
    runner: Callable[[], str]
    winner_by_result: dict


@dataclass
class Disagreement:
    id: str
    claim_id: str
    implementer: Party
    confirmer: Party
    status: str = "OPEN"
    test: Optional[RegisteredTest] = None
    run_at: Optional[str] = None
    verbatim_result: Optional[str] = None
    revision: Optional[dict] = None
    irreducible: Optional[dict] = None
    close_method: Optional[str] = None
    history: list = field(default_factory=list)

    def to_entry(self) -> dict:
        entry = {
            "id": self.id,
            "claim_id": self.claim_id,
            "status": self.status,
            "implementer": self.implementer.to_dict(),
            "confirmer": self.confirmer.to_dict(),
            "close_method": self.close_method,
            "test_id": self.test.test_id if self.test else None,
            "preregistered_at": self.test.preregistered_at if self.test else None,
            "run_at": self.run_at,
            "verbatim_result": self.verbatim_result,
            "revision": self.revision,
            "history": list(self.history),
        }
        if self.irreducible is not None:
            entry["irreducible"] = self.irreducible
        return entry

    def to_discrepancy(self) -> dict:
        disposition = {
            "CLOSED_CONFIRMER_REVISED": "confirmation-defect",
            "CLOSED_IMPLEMENTER_REVISED": "implementation-defect",
            "IRREDUCIBLE": "specification-ambiguity",
        }.get(self.status, "open")
        return {
            "id": f"disc-{self.id}",
            "claim_id": self.claim_id,
            "implementer_position": self.implementer.position,
            "confirmer_position": self.confirmer.position,
            "status": self.status,
            "test_id": self.test.test_id if self.test else None,
            "preregistered_at": self.test.preregistered_at if self.test else None,
            "verbatim_result": self.verbatim_result,
            "revising_side": (self.revision or {}).get("side"),
            "disposition": disposition,
        }


class TiebreakProtocol:
    def __init__(self, clock: Optional[StepClock] = None) -> None:
        self.clock = clock or StepClock()
        self._seq = 0
        self.disagreements: dict[str, Disagreement] = {}
        self.defects: list[dict] = []

    def _new_id(self, prefix: str) -> str:
        self._seq += 1
        return f"{prefix}-{self._seq:03d}"

    def open(
        self,
        claim_id: str,
        implementer: Party,
        confirmer: Party,
        disagreement_id: Optional[str] = None,
    ) -> str:
        if implementer.role != "implementer" or confirmer.role != "confirmer":
            raise TiebreakError("roles must be implementer and confirmer")
        did = disagreement_id or self._new_id("D")
        if did in self.disagreements:
            raise TiebreakError(f"duplicate disagreement id {did}")
        d = Disagreement(
            id=did,
            claim_id=claim_id,
            implementer=implementer,
            confirmer=confirmer,
        )
        d.history.append({"at": self.clock.stamp(), "event": "opened"})
        self.disagreements[did] = d
        return did

    def preregister(
        self,
        disagreement_id: str,
        test_id: str,
        description: str,
        runner: Callable[[], str],
        winner_by_result: dict,
    ) -> None:
        d = self._require(disagreement_id)
        if d.status not in {"OPEN", "TEST_PREREGISTERED"}:
            raise TiebreakError(f"{disagreement_id} is {d.status}; cannot preregister")
        if not test_id or not str(test_id).strip():
            raise IllegalClose("test_id is required to preregister")
        roles = set(winner_by_result.values())
        if not roles.issubset({"implementer", "confirmer"}):
            raise TiebreakError("winner_by_result values must be implementer or confirmer")
        ts = self.clock.stamp()
        impl_at = self.clock.stamp()
        conf_at = self.clock.stamp()
        d.test = RegisteredTest(
            test_id=str(test_id),
            description=description,
            preregistered_at=ts,
            accepted_by_implementer_at=impl_at,
            accepted_by_confirmer_at=conf_at,
            runner=runner,
            winner_by_result=dict(winner_by_result),
        )
        d.status = "TEST_PREREGISTERED"
        d.history.append(
            {
                "at": ts,
                "event": "preregistered",
                "test_id": test_id,
                "accepted_by": ["implementer", "confirmer"],
            }
        )

    def run_and_close(self, disagreement_id: str) -> dict:
        d = self._require(disagreement_id)
        if d.test is None or d.status != "TEST_PREREGISTERED":
            self._record_defect(
                kind="close-without-preregistered-test",
                disagreement_id=disagreement_id,
                note="run_and_close refused: no test both sides accepted in advance",
            )
            raise IllegalClose("cannot close without a pre-registered executable test")
        result = d.test.runner()
        if not isinstance(result, str):
            result = str(result)
        d.verbatim_result = result
        d.run_at = self.clock.stamp()
        if d.test.preregistered_at >= d.run_at:
            raise TiebreakError("pre-registration timestamp must precede the run")
        winner = d.test.winner_by_result.get(result)
        if winner is None:
            d.status = "IRREDUCIBLE"
            d.close_method = "irreducible-attestation"
            d.irreducible = {
                "reason": (
                    f"pre-registered test {d.test.test_id} returned {result!r}, "
                    "which is not in the agreed winner map; no side is settled"
                ),
                "both_parties_attested_no_executable_test": True,
            }
            d.history.append(
                {"at": d.run_at, "event": "inconclusive", "verbatim_result": result}
            )
            return d.to_entry()
        loser = "confirmer" if winner == "implementer" else "implementer"
        loser_party = d.confirmer if loser == "confirmer" else d.implementer
        concession = (
            "I concede only to a new falsifiable argument: pre-registered test "
            f"{d.test.test_id} (preregistered_at={d.test.preregistered_at}) "
            f"returned verbatim {result!r}, which falsifies my position "
            f"{loser_party.position!r}."
        )
        d.revision = {
            "side": loser,
            "explicit_concession": concession,
            "new_falsifiable_argument": d.test.description,
        }
        d.close_method = "executable-test"
        d.status = (
            "CLOSED_CONFIRMER_REVISED"
            if loser == "confirmer"
            else "CLOSED_IMPLEMENTER_REVISED"
        )
        d.history.append(
            {
                "at": d.run_at,
                "event": "closed",
                "test_id": d.test.test_id,
                "verbatim_result": result,
                "revising_side": loser,
            }
        )
        return d.to_entry()

    def declare_irreducible(
        self,
        disagreement_id: str,
        reason: str,
        proposed_tests_rejected: list,
    ) -> dict:
        d = self._require(disagreement_id)
        if d.status in SETTLED_STATUSES:
            raise TiebreakError("already settled; cannot declare irreducible")
        d.status = "IRREDUCIBLE"
        d.close_method = "irreducible-attestation"
        d.irreducible = {
            "reason": reason,
            "both_parties_attested_no_executable_test": True,
            "proposed_tests_rejected": proposed_tests_rejected,
        }
        d.history.append(
            {"at": self.clock.stamp(), "event": "irreducible", "reason": reason}
        )
        return d.to_entry()

    def attempt_close(self, disagreement_id: str, method: str, actor: str) -> dict:
        d = self._require(disagreement_id)
        method_n = (method or "").strip().lower()
        if method_n in FORBIDDEN_METHODS:
            defect = self._record_defect(
                kind="illegal-close-method",
                disagreement_id=disagreement_id,
                note=f"{actor} attempted close by {method_n}; refused",
            )
            d.history.append(
                {
                    "at": defect["attempted_at"],
                    "event": "illegal-close-refused",
                    "method": method_n,
                }
            )
            raise IllegalClose(f"close method {method_n!r} is forbidden")
        if d.test is None or not d.test.test_id:
            defect = self._record_defect(
                kind="close-without-preregistered-test",
                disagreement_id=disagreement_id,
                note=f"{actor} attempted to close {disagreement_id} with no test id",
            )
            d.history.append(
                {"at": defect["attempted_at"], "event": "untested-close-refused"}
            )
            raise IllegalClose("cannot close a disagreement with no test id")
        raise IllegalClose(
            f"attempt_close does not settle; use run_and_close (method={method_n!r})"
        )

    def authority_push(
        self,
        disagreement_id: str,
        speaker: str,
        message: str,
        requested_status: str,
        new_evidence: Optional[dict] = None,
    ) -> dict:
        d = self._require(disagreement_id)
        held = d.status
        if _has_falsifiable_evidence(new_evidence):
            raise TiebreakError(
                "authority_push does not accept evidence; preregister a new test"
            )
        defect = self._record_defect(
            kind="authority-push-without-evidence",
            disagreement_id=disagreement_id,
            note=(
                f"{speaker} applied authority-toned pressure with no new "
                "falsifiable argument; verdict not flipped"
            ),
        )
        record = {
            "pressure_applied": True,
            "speaker": speaker,
            "message": message,
            "new_falsifiable_evidence": False,
            "verdict_flipped": False,
            "held_status": held,
            "requested_status": requested_status,
            "defect_id": defect["id"],
        }
        d.history.append(
            {
                "at": defect["attempted_at"],
                "event": "authority-push-held",
                "record": record,
            }
        )
        return record

    def _require(self, disagreement_id: str) -> Disagreement:
        try:
            return self.disagreements[disagreement_id]
        except KeyError as exc:
            raise TiebreakError(f"unknown disagreement {disagreement_id}") from exc

    def _record_defect(self, kind: str, disagreement_id: str, note: str) -> dict:
        defect = {
            "id": self._new_id("DEF"),
            "kind": kind,
            "refused": True,
            "disagreement_id": disagreement_id,
            "attempted_at": self.clock.stamp(),
            "note": note,
        }
        self.defects.append(defect)
        return defect

    def export_entries(self) -> list:
        return [d.to_entry() for d in self.disagreements.values()]

    def export_discrepancies(self) -> list:
        return [d.to_discrepancy() for d in self.disagreements.values()]


def _has_falsifiable_evidence(ev: Optional[dict]) -> bool:
    if not isinstance(ev, dict):
        return False
    test_id = ev.get("test_id")
    ts = ev.get("preregistered_at")
    result = ev.get("verbatim_result")
    return bool(
        isinstance(test_id, str)
        and test_id.strip()
        and isinstance(ts, str)
        and len(ts) >= 20
        and isinstance(result, str)
        and result != ""
    )
