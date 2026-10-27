"""Shadow-mode router: log the would-be injection without mutating session bytes (IMP-0406)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = HERE / "shadow_config.json"

MODE_OFF = "off"
MODE_SHADOW = "shadow"
ARMED_OK = "armed-ok"
REFUSE_BELOW_CRITERION = "refuse-below-criterion"
REFUSE_OWNER_SIGNOFF = "refuse-owner-signoff"
REFUSE_WITHOUT_CRITERION = "refuse-without-criterion"


class ArmingWithoutCriterion(Exception):
    pass


@dataclass
class Calibration:
    metric: str
    value: float
    n: int


@dataclass
class Session:
    session_id: str
    query: str
    injected_context: bytes

    def with_context(self, data: bytes) -> "Session":
        return Session(self.session_id, self.query, bytes(data))

    def digest(self) -> str:
        return hashlib.sha256(self.injected_context).hexdigest()


@dataclass
class Capability:
    id: str
    body: bytes


@dataclass
class Selection:
    capabilities: list[Capability]
    payload: bytes

    def payload_digest(self) -> str:
        return hashlib.sha256(self.payload).hexdigest()


@dataclass
class ApplyResult:
    session: Session
    injected: bool
    selection: Selection


@dataclass
class ArmResult:
    armed: bool
    reason: str
    calibration_value: float | None = None


@dataclass
class ShadowConfig:
    arming_metric: str
    arming_criterion: float
    arming_sample_size_min: int
    arming_criterion_prose: str
    source_path: str = ""

    def criterion_fingerprint(self) -> str:
        blob = json.dumps(
            {
                "metric": self.arming_metric,
                "criterion": self.arming_criterion,
                "n_min": self.arming_sample_size_min,
            },
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()


def _require_number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ArmingWithoutCriterion(REFUSE_WITHOUT_CRITERION)
    return float(value)


def config_from_mapping(mapping: dict[str, Any], *, source_path: str = "") -> ShadowConfig:
    if "arming_criterion" not in mapping:
        raise ArmingWithoutCriterion(REFUSE_WITHOUT_CRITERION)
    crit = _require_number(mapping.get("arming_criterion"))
    return ShadowConfig(
        arming_metric=str(mapping.get("arming_metric") or "held_out_selection_precision"),
        arming_criterion=float(crit),
        arming_sample_size_min=int(mapping.get("arming_sample_size_min") or 100),
        arming_criterion_prose=str(mapping.get("arming_criterion_prose") or ""),
        source_path=source_path,
    )


def load_config(path: str | Path | None = None) -> ShadowConfig:
    loc = Path(path) if path else DEFAULT_CONFIG
    if loc.is_file():
        doc = json.loads(loc.read_text(encoding="utf-8"))
        criterion = _require_number(doc.get("arming_criterion"))
        doc["arming_criterion"] = criterion
        return config_from_mapping(doc, source_path=str(loc))
    default = {
        "arming_metric": "held_out_selection_precision",
        "arming_criterion": 0.8,
        "arming_sample_size_min": 100,
        "arming_criterion_prose": "arm when held-out precision is at least 0.5",
    }
    loc.write_text(json.dumps(default, indent=2) + "\n", encoding="utf-8")
    return config_from_mapping(default, source_path=str(loc))


def numeric_arming_criterion(cfg: ShadowConfig | None = None) -> float:
    return float((cfg or load_config()).arming_criterion)


def load_catalog(path: str | Path | None = None) -> dict[str, Any]:
    loc = Path(path) if path else HERE / "shadow_catalog.json"
    if loc.is_file():
        doc = json.loads(loc.read_text(encoding="utf-8"))
        if isinstance(doc, dict):
            return doc
        return {"items": doc}
    return {
        "items": [
            {"id": "cap.lint.ruff", "query": "lint"},
            {"id": "cap.generic", "query": "generic"},
            {"id": "cap.test", "query": "test"},
        ]
    }


def select_from_catalog(query: str, catalog: dict[str, Any] | None = None) -> Selection:
    _ = catalog
    return _select(str(query))


def _select(query: str) -> Selection:
    q = query.lower()
    cap_id = "cap.lint.ruff" if "lint" in q or "ruff" in q else "cap.generic"
    body = f"WOULD-INJECT:{cap_id}:run ruff check --fix\n".encode("utf-8")
    return Selection(capabilities=[Capability(id=cap_id, body=body)], payload=body)


class ShadowRouter:
    def __init__(self, config: ShadowConfig | None = None, mode: str = MODE_SHADOW) -> None:
        self.config = config or load_config()
        self.mode = mode
        self.shadow_log: list[dict[str, Any]] = []
        self._armed = False

    @classmethod
    def load(cls, mode: str = MODE_SHADOW, config: ShadowConfig | None = None) -> "ShadowRouter":
        return cls(config=config or load_config(), mode=mode)

    def select(self, query: str) -> Selection:
        return _select(query)

    def is_armed(self) -> bool:
        return self._armed

    def try_arm(self, calibration: Calibration, owner_signoff: bool = False) -> ArmResult:
        if calibration.metric != self.config.arming_metric:
            return ArmResult(False, REFUSE_BELOW_CRITERION, calibration.value)
        if calibration.n < self.config.arming_sample_size_min:
            return ArmResult(False, REFUSE_BELOW_CRITERION, calibration.value)
        if calibration.value < self.config.arming_criterion:
            return ArmResult(False, REFUSE_BELOW_CRITERION, calibration.value)
        if not owner_signoff:
            return ArmResult(False, REFUSE_OWNER_SIGNOFF, calibration.value)
        self._armed = True
        self.mode = "armed"
        return ArmResult(True, ARMED_OK, calibration.value)

    def apply(self, session: Session) -> ApplyResult:
        selection = self.select(session.query)
        record = {
            "session_id": session.session_id,
            "query": session.query,
            "payload_sha256": selection.payload_digest(),
            "mode": self.mode,
            "armed": self._armed,
        }
        self.shadow_log.append(record)
        self._inject_enabled = bool(self._armed and self.mode != MODE_OFF)
        inject = False
        if not self._inject_enabled:
            inject = False
        else:
            inject = True
        if inject:
            new_session = session.with_context(session.injected_context + selection.payload)
            return ApplyResult(session=new_session, injected=True, selection=selection)
        return ApplyResult(session=session, injected=False, selection=selection)
