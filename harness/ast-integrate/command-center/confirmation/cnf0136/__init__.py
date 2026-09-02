"""CNF-0136: confirmation queue that refuses to launder infrastructure faults.

``taxonomy``   the fault taxonomy table; infra faults may never surface as
               CONFIRMED / REFUTED (``FORBIDDEN_INFRA_VERDICTS``)
``record``     confirmation-record contract validation + deterministic ids
``queue``      the record store that raises ``VerdictLaunderingError`` on an
               infra fault dressed as a verdict
``scheduler``  the queue scheduler with an injectable ``Clock``, ``Job`` and
               ``RunnerEvent`` model

The CNF-0136 scenario imports each submodule by dotted path; the names are
re-exported here so the package reads as one surface.
"""
from __future__ import annotations

from .queue import RecordStore, VerdictLaunderingError
from .record import RecordContractError, mint_record_id, validate_record
from .scheduler import Clock, ConfirmationQueueScheduler, Job, RunnerEvent, mark_in_flight
from .taxonomy import (
    FORBIDDEN_INFRA_VERDICTS,
    TAXONOMY,
    evidence_looks_like_infra,
    map_fault,
    naive_launder_to_refuted,
)

__all__ = [
    "Clock",
    "ConfirmationQueueScheduler",
    "FORBIDDEN_INFRA_VERDICTS",
    "Job",
    "RecordContractError",
    "RecordStore",
    "RunnerEvent",
    "TAXONOMY",
    "VerdictLaunderingError",
    "evidence_looks_like_infra",
    "map_fault",
    "mark_in_flight",
    "mint_record_id",
    "naive_launder_to_refuted",
    "validate_record",
    "queue",
    "record",
    "scheduler",
    "taxonomy",
]
