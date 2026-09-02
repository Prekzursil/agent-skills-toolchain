"""Detector controls: the both-states fixture set that makes a detector evidence (TST-0014).

A detector (validator rule, hook check, gate script) is *controlled* only when the
registry names three fixtures for it and all three exist on disk:

* ``known_present`` -- a tree in which the enumerator must FIND the detector,
* ``known_broken``  -- a state on which the detector must FIRE,
* ``known_good``    -- a state on which the detector must stay SILENT.

A registry row that names a fixture which is not on disk is not a control; it
is a promise, and the gate treats the detector as uncontrolled. This module owns
the row parsing and the fixture-existence verdict so ``gate.py`` and any future
CI wiring share one definition of "controlled".
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
REGISTRY_PATH = HERE / "registry.json"

FIXTURE_KEYS: tuple[str, ...] = ("known_present", "known_broken", "known_good")
CONTROLLED = "controlled"
UNCONTROLLED = "uncontrolled"
REASON_NO_ROW = "no-registry-row"
REASON_MISSING_PREFIX = "registry-row-missing-fixture:"
REASON_CONTROLLED = "registry-row-with-existing-fixtures"
KNOWN_BROKEN_FIXTURE = "known-broken-fixture"

__all__ = [
    "FIXTURE_KEYS",
    "CONTROLLED",
    "UNCONTROLLED",
    "REASON_NO_ROW",
    "REASON_CONTROLLED",
    "Control",
    "ControlStatus",
    "load_registry_rows",
    "load_controls",
    "control_from_row",
    "fixture_exists",
    "evaluate_control",
    "status_for",
    "both_states_record",
]


@dataclass(frozen=True)
class Control:
    """One detector's declared both-states fixture set (paths relative to the repo)."""

    detector_id: str
    kind: str = ""
    source: str = ""
    known_present: str | None = None
    known_broken: str | None = None
    known_good: str | None = None

    def fixtures(self) -> dict[str, str | None]:
        """The three fixture slots keyed by ``FIXTURE_KEYS``."""
        return {
            "known_present": self.known_present,
            "known_broken": self.known_broken,
            "known_good": self.known_good,
        }

    def declared(self) -> list[str]:
        """Fixture slots the row actually fills (non-empty strings)."""
        return [k for k, v in self.fixtures().items() if isinstance(v, str) and v]


@dataclass(frozen=True)
class ControlStatus:
    """Verdict for one detector: controlled iff every fixture exists on disk."""

    detector_id: str
    verdict: str
    reason: str
    exists: dict[str, bool] = field(default_factory=dict)
    missing: tuple[str, ...] = ()

    @property
    def controlled(self) -> bool:
        return self.verdict == CONTROLLED


def load_registry_rows(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Return registry rows keyed by detector id (empty when the file is absent).

    Accepts either ``{"detectors": [...]}`` or a bare list. Rows without a
    non-empty string ``id`` are ignored rather than fabricated.
    """
    reg_path = Path(path) if path is not None else REGISTRY_PATH
    if not reg_path.is_file():
        return {}
    doc = json.loads(reg_path.read_text(encoding="utf-8"))
    rows: Iterable[Any]
    if isinstance(doc, dict):
        rows = doc.get("detectors") or []
    elif isinstance(doc, list):
        rows = doc
    else:
        rows = []
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get("id"), str) and row["id"]:
            out[row["id"]] = row
    return out


def control_from_row(row: Mapping[str, Any]) -> Control:
    """Build a ``Control`` from one registry row (missing slots stay ``None``)."""
    detector_id = row.get("id")
    if not isinstance(detector_id, str) or not detector_id:
        raise ValueError("registry row needs a non-empty string 'id'")

    def _slot(key: str) -> str | None:
        value = row.get(key)
        return value if isinstance(value, str) and value else None

    return Control(
        detector_id=detector_id,
        kind=str(row.get("kind") or ""),
        source=str(row.get("source") or ""),
        known_present=_slot("known_present"),
        known_broken=_slot("known_broken"),
        known_good=_slot("known_good"),
    )


def load_controls(path: Path | None = None) -> dict[str, Control]:
    """Registry rows lifted to ``Control`` objects, keyed by detector id."""
    return {did: control_from_row(row) for did, row in load_registry_rows(path).items()}


def fixture_exists(rel: Any, repo: Path = REPO) -> bool:
    """True when ``rel`` names an existing path (relative paths resolve against ``repo``)."""
    if not isinstance(rel, str) or not rel:
        return False
    candidate = Path(rel)
    if not candidate.is_absolute():
        candidate = Path(repo) / rel
    return candidate.exists()


def evaluate_control(control: Control, repo: Path = REPO) -> ControlStatus:
    """Controlled iff ``known_present``, ``known_broken`` and ``known_good`` all exist."""
    exists = {key: fixture_exists(value, repo) for key, value in control.fixtures().items()}
    missing = tuple(key for key in FIXTURE_KEYS if not exists[key])
    if missing:
        return ControlStatus(
            detector_id=control.detector_id,
            verdict=UNCONTROLLED,
            reason=REASON_MISSING_PREFIX + ",".join(missing),
            exists=exists,
            missing=missing,
        )
    return ControlStatus(
        detector_id=control.detector_id,
        verdict=CONTROLLED,
        reason=REASON_CONTROLLED,
        exists=exists,
    )


def status_for(detector_id: str, controls: Mapping[str, Control], repo: Path = REPO) -> ControlStatus:
    """Status of a detector id against loaded controls; no row means uncontrolled."""
    control = controls.get(detector_id)
    if control is None:
        return ControlStatus(
            detector_id=detector_id,
            verdict=UNCONTROLLED,
            reason=REASON_NO_ROW,
            exists={key: False for key in FIXTURE_KEYS},
            missing=FIXTURE_KEYS,
        )
    return evaluate_control(control, repo)


def both_states_record(
    control_id: str,
    description: str,
    *,
    silent_on_good_state: bool,
    fired_on_bad_state: bool,
    kind: str = KNOWN_BROKEN_FIXTURE,
) -> dict[str, Any]:
    """A negative-control row: the detector's behaviour on both fixture states.

    ``silent_on_good_state`` and ``fired_on_bad_state`` must be real booleans
    (not truthy stand-ins) so a missing probe field cannot read as a pass.
    """
    if not control_id:
        raise ValueError("control_id must be non-empty")
    for name, value in (
        ("silent_on_good_state", silent_on_good_state),
        ("fired_on_bad_state", fired_on_bad_state),
    ):
        if not isinstance(value, bool):
            raise TypeError(f"{name} must be a bool, got {type(value).__name__}")
    return {
        "id": control_id,
        "kind": kind,
        "description": description,
        "silent_on_good_state": silent_on_good_state,
        "fired_on_bad_state": fired_on_bad_state,
        "valid": silent_on_good_state and fired_on_bad_state,
    }
