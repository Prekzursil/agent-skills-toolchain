#!/usr/bin/env python3
"""CNF-0135 ledger closer: tests both sides accepted in advance, never rank or vote."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

BANNED = frozenset({"seniority", "vote", "rhetoric", "majority", "authority", "chair"})
CLOSED = frozenset({"CLOSED_CONFIRMER_REVISED", "CLOSED_IMPLEMENTER_REVISED"})


class ProtocolError(Exception):
    pass


class RefusedClose(ProtocolError):
    pass


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Clock:
    def __init__(self, start: Optional[datetime] = None) -> None:
        self._t = start or datetime(2026, 8, 24, 17, 0, 0, tzinfo=timezone.utc)

    def stamp(self) -> str:
        self._t = self._t + timedelta(seconds=1)
        return iso(self._t)


@dataclass
class Side:
    role: str
    identity: str
    position: str
    vendor: str = "local-sim"

    def as_dict(self) -> dict:
        return {
            "role": self.role,
            "identity": self.identity,
            "vendor": self.vendor,
            "position": self.position,
        }


@dataclass
class AcceptedTest:
    test_id: str
    description: str
    preregistered_at: str
    accepted_by_implementer_at: str
    accepted_by_confirmer_at: str
    runner: Callable[[], str]
    winner_by_result: dict


@dataclass
class Case:
    id: str
    claim_id: str
    implementer: Side
    confirmer: Side
    status: str = "OPEN"
    test: Optional[AcceptedTest] = None
    run_at: Optional[str] = None
    verbatim_result: Optional[str] = None
    revision: Optional[dict] = None
    irreducible: Optional[dict] = None
    close_method: Optional[str] = None
    history: list = field(default_factory=list)

    def as_entry(self) -> dict:
        row = {
            "id": self.id,
            "claim_id": self.claim_id,
            "status": self.status,
            "implementer": self.implementer.as_dict(),
            "confirmer": self.confirmer.as_dict(),
            "close_method": self.close_method,
            "test_id": self.test.test_id if self.test else None,
            "preregistered_at": self.test.preregistered_at if self.test else None,
            "run_at": self.run_at,
            "verbatim_result": self.verbatim_result,
            "revision": self.revision,
            "history": list(self.history),
        }
        if self.irreducible is not None:
            row["irreducible"] = self.irreducible
        return row

    def as_discrepancy(self) -> dict:
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


class Ledger:
    def __init__(self, clock: Optional[Clock] = None) -> None:
        self.clock = clock or Clock()
        self._n = 0
        self.cases: dict[str, Case] = {}
        self.defects: list[dict] = []

    def _nid(self, prefix: str) -> str:
        self._n += 1
        return f"{prefix}-{self._n:03d}"

    def open_case(
        self,
        claim_id: str,
        implementer: Side,
        confirmer: Side,
        case_id: Optional[str] = None,
    ) -> str:
        if implementer.role != "implementer" or confirmer.role != "confirmer":
            raise ProtocolError("roles must be implementer and confirmer")
        cid = case_id or self._nid("D")
        if cid in self.cases:
            raise ProtocolError(f"duplicate case id {cid}")
        row = Case(
            id=cid,
            claim_id=claim_id,
            implementer=implementer,
            confirmer=confirmer,
        )
        row.history.append({"at": self.clock.stamp(), "event": "opened"})
        self.cases[cid] = row
        return cid

    def accept_test(
        self,
        case_id: str,
        test_id: str,
        description: str,
        runner: Callable[[], str],
        winner_by_result: dict,
    ) -> None:
        row = self._get(case_id)
        if row.status not in {"OPEN", "TEST_PREREGISTERED"}:
            raise ProtocolError(f"{case_id} is {row.status}")
        if not test_id or not str(test_id).strip():
            raise RefusedClose("test_id is required")
        if not set(winner_by_result.values()).issubset({"implementer", "confirmer"}):
            raise ProtocolError("winner_by_result values invalid")
        ts = self.clock.stamp()
        row.test = AcceptedTest(
            test_id=str(test_id),
            description=description,
            preregistered_at=ts,
            accepted_by_implementer_at=self.clock.stamp(),
            accepted_by_confirmer_at=self.clock.stamp(),
            runner=runner,
            winner_by_result=dict(winner_by_result),
        )
        row.status = "TEST_PREREGISTERED"
        row.history.append(
            {
                "at": ts,
                "event": "preregistered",
                "test_id": test_id,
                "accepted_by": ["implementer", "confirmer"],
            }
        )

    def run_and_close(self, case_id: str) -> dict:
        row = self._get(case_id)
        if row.test is None or row.status != "TEST_PREREGISTERED":
            self._defect(
                "close-without-preregistered-test",
                case_id,
                "refused: no test both sides accepted in advance",
            )
            raise RefusedClose("cannot close without a pre-registered executable test")
        result = row.test.runner()
        if not isinstance(result, str):
            result = str(result)
        row.verbatim_result = result
        row.run_at = self.clock.stamp()
        if row.test.preregistered_at >= row.run_at:
            raise ProtocolError("pre-registration must precede the run")
        winner = row.test.winner_by_result.get(result)
        if winner is None:
            row.status = "IRREDUCIBLE"
            row.close_method = "irreducible-attestation"
            row.irreducible = {
                "reason": (
                    f"test {row.test.test_id} returned {result!r}, not in winner map"
                ),
                "both_parties_attested_no_executable_test": True,
            }
            row.history.append(
                {"at": row.run_at, "event": "inconclusive", "verbatim_result": result}
            )
            return row.as_entry()
        loser = "confirmer" if winner == "implementer" else "implementer"
        loser_side = row.confirmer if loser == "confirmer" else row.implementer
        concession = (
            "I concede only to a new falsifiable argument: pre-registered test "
            f"{row.test.test_id} (preregistered_at={row.test.preregistered_at}) "
            f"returned verbatim {result!r}, which falsifies my position "
            f"{loser_side.position!r}."
        )
        row.revision = {
            "side": loser,
            "explicit_concession": concession,
            "new_falsifiable_argument": row.test.description,
        }
        row.close_method = "executable-test"
        row.status = (
            "CLOSED_CONFIRMER_REVISED"
            if loser == "confirmer"
            else "CLOSED_IMPLEMENTER_REVISED"
        )
        row.history.append(
            {
                "at": row.run_at,
                "event": "closed",
                "test_id": row.test.test_id,
                "verbatim_result": result,
                "revising_side": loser,
            }
        )
        return row.as_entry()

    def mark_irreducible(
        self, case_id: str, reason: str, rejected_proposals: list
    ) -> dict:
        row = self._get(case_id)
        if row.status in CLOSED:
            raise ProtocolError("already settled")
        row.status = "IRREDUCIBLE"
        row.close_method = "irreducible-attestation"
        row.irreducible = {
            "reason": reason,
            "both_parties_attested_no_executable_test": True,
            "proposed_tests_rejected": rejected_proposals,
        }
        row.history.append(
            {"at": self.clock.stamp(), "event": "irreducible", "reason": reason}
        )
        return row.as_entry()

    def attempt_close(self, case_id: str, method: str, actor: str) -> dict:
        row = self._get(case_id)
        method_n = (method or "").strip().lower()
        if method_n in BANNED:
            defect = self._defect(
                "illegal-close-method",
                case_id,
                f"{actor} attempted close by {method_n}; refused",
            )
            row.history.append(
                {
                    "at": defect["attempted_at"],
                    "event": "illegal-close-refused",
                    "method": method_n,
                }
            )
            raise RefusedClose(f"close method {method_n!r} is forbidden")
        if row.test is None or not row.test.test_id:
            defect = self._defect(
                "close-without-preregistered-test",
                case_id,
                f"{actor} attempted to close {case_id} with no test id",
            )
            row.history.append(
                {"at": defect["attempted_at"], "event": "untested-close-refused"}
            )
            raise RefusedClose("cannot close a disagreement with no test id")
        raise RefusedClose("attempt_close does not settle; use run_and_close")

    def authority_push(
        self,
        case_id: str,
        speaker: str,
        message: str,
        requested_status: str,
        new_evidence: Optional[dict] = None,
    ) -> dict:
        row = self._get(case_id)
        held = row.status
        if _evidence_ok(new_evidence):
            raise ProtocolError("preregister a new test instead of pushing")
        defect = self._defect(
            "authority-push-without-evidence",
            case_id,
            f"{speaker} applied pressure with no new falsifiable argument; not flipped",
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
        row.history.append(
            {
                "at": defect["attempted_at"],
                "event": "authority-push-held",
                "record": record,
            }
        )
        return record

    def _get(self, case_id: str) -> Case:
        try:
            return self.cases[case_id]
        except KeyError as exc:
            raise ProtocolError(f"unknown case {case_id}") from exc

    def _defect(self, kind: str, case_id: str, note: str) -> dict:
        row = {
            "id": self._nid("DEF"),
            "kind": kind,
            "refused": True,
            "disagreement_id": case_id,
            "attempted_at": self.clock.stamp(),
            "note": note,
        }
        self.defects.append(row)
        return row

    def export_entries(self) -> list:
        return [c.as_entry() for c in self.cases.values()]

    def export_discrepancies(self) -> list:
        return [c.as_discrepancy() for c in self.cases.values()]


def _evidence_ok(ev: Optional[dict]) -> bool:
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

# Names used by campaign.py and the probes.
Clock = Clock
Side = Side
Ledger = Ledger
RefusedClose = RefusedClose
Case.as_entry = Case.as_entry
Ledger.open_case = Ledger.open_case
Ledger.accept_test = Ledger.accept_test
Ledger.export_entries = Ledger.export_entries
Ledger.attempt_close = Ledger.attempt_close
