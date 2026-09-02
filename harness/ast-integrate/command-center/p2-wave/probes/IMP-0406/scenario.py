"""Live measurements for IMP-0406 shadow-mode zero-effect and arming gate."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.router.shadow import (  # noqa: E402
    ARMED_OK,
    MODE_OFF,
    MODE_SHADOW,
    REFUSE_BELOW_CRITERION,
    REFUSE_WITHOUT_CRITERION,
    ArmingWithoutCriterion,
    Calibration,
    Session,
    ShadowRouter,
    config_from_mapping,
    load_config,
    numeric_arming_criterion,
)

FIXTURE = HERE / "fixtures" / "session-ab.json"
BELOW = Calibration(metric="held_out_selection_precision", value=0.5, n=200)
ABOVE = Calibration(metric="held_out_selection_precision", value=0.95, n=200)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_pair() -> tuple[Session, Session]:
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    ctx = str(doc["baseline_injected_context"]).encode("utf-8")
    query = str(doc["query"])
    sid = str(doc["session_id"])
    on = Session(session_id=f"{sid}-on", query=query, injected_context=ctx)
    off = Session(session_id=f"{sid}-off", query=query, injected_context=bytes(ctx))
    return on, off


def prose_extracted_criterion(prose: str) -> float | None:
    match = re.search(r"([0-9]+\.[0-9]+)", prose)
    if match is None:
        return None
    return float(match.group(1))


def leaky_shadow_apply(router: ShadowRouter, session: Session) -> Session:
    """Known-broken injector: appends the would-be payload while still in shadow."""
    selection = router.select(session.query)
    return session.with_context(session.injected_context + selection.payload)


def measure_zero_effect() -> dict:
    on_session, off_session = load_pair()
    baseline = bytes(on_session.injected_context)
    shadow = ShadowRouter.load(mode=MODE_SHADOW)
    silent = ShadowRouter.load(mode=MODE_OFF)
    on_result = shadow.apply(on_session)
    off_result = silent.apply(off_session)
    leaked = leaky_shadow_apply(ShadowRouter.load(mode=MODE_SHADOW), on_session)
    armed = ShadowRouter.load(mode=MODE_SHADOW)
    arm_ok = armed.try_arm(ABOVE, owner_signoff=True)
    armed_result = armed.apply(on_session)
    would = on_result.selection
    return {
        "baseline_bytes": len(baseline),
        "baseline_sha256": _digest(baseline),
        "shadow_on_bytes": len(on_result.session.injected_context),
        "shadow_on_sha256": on_result.session.digest(),
        "shadow_off_bytes": len(off_result.session.injected_context),
        "shadow_off_sha256": off_result.session.digest(),
        "byte_identical": on_result.session.injected_context
        == off_result.session.injected_context
        == baseline,
        "shadow_injected": on_result.injected,
        "off_injected": off_result.injected,
        "would_inject_bytes": len(would.payload),
        "would_inject_sha256": would.payload_digest(),
        "selected_ids": [c.id for c in would.capabilities],
        "shadow_log_len": len(shadow.shadow_log),
        "leak_sha256": leaked.digest(),
        "leak_differs": leaked.injected_context != baseline,
        "armed_reason": arm_ok.reason,
        "armed_injected": armed_result.injected,
        "armed_sha256": armed_result.session.digest(),
        "armed_differs": armed_result.session.injected_context != baseline,
        "armed_payload_appended": armed_result.session.injected_context
        == baseline + would.payload,
        "zero_delta_bytes": (
            0
            if on_result.session.injected_context == baseline
            else abs(len(on_result.session.injected_context) - len(baseline))
        ),
    }


def measure_arming_gate() -> dict:
    cfg = load_config()
    criterion = numeric_arming_criterion()
    router = ShadowRouter(config=cfg, mode=MODE_SHADOW)
    below = router.try_arm(BELOW, owner_signoff=True)
    after_refuse = router.apply(load_pair()[0])
    prose_value = prose_extracted_criterion(cfg.arming_criterion_prose)
    prose_would_arm = (
        prose_value is not None and BELOW.value >= prose_value and BELOW.n >= cfg.arming_sample_size_min
    )
    no_signoff = ShadowRouter(config=cfg, mode=MODE_SHADOW).try_arm(
        ABOVE, owner_signoff=False
    )
    missing_err = None
    missing_refused = False
    try:
        config_from_mapping(
            {
                "arming_metric": cfg.arming_metric,
                "arming_sample_size_min": cfg.arming_sample_size_min,
                "arming_criterion_prose": cfg.arming_criterion_prose,
            }
        )
    except ArmingWithoutCriterion as exc:
        missing_err = str(exc)
        missing_refused = True
    bool_err = None
    bool_refused = False
    try:
        config_from_mapping(
            {
                "arming_criterion": True,
                "arming_metric": cfg.arming_metric,
                "arming_sample_size_min": cfg.arming_sample_size_min,
            }
        )
    except ArmingWithoutCriterion as exc:
        bool_err = str(exc)
        bool_refused = True
    return {
        "arming_criterion": criterion,
        "arming_criterion_type": type(criterion).__name__,
        "arming_metric": cfg.arming_metric,
        "arming_sample_size_min": cfg.arming_sample_size_min,
        "criterion_fingerprint": cfg.criterion_fingerprint(),
        "config_path": cfg.source_path,
        "prose": cfg.arming_criterion_prose,
        "prose_extracted_criterion": prose_value,
        "prose_mutant_would_arm": prose_would_arm,
        "below_armed": below.armed,
        "below_reason": below.reason,
        "below_calibration_value": below.calibration_value,
        "below_still_shadow": not router.is_armed()
        and after_refuse.injected is False
        and after_refuse.session.injected_context == load_pair()[0].injected_context,
        "no_signoff_armed": no_signoff.armed,
        "no_signoff_reason": no_signoff.reason,
        "missing_criterion_refused": missing_refused,
        "missing_criterion_error": missing_err,
        "bool_criterion_refused": bool_refused,
        "bool_criterion_error": bool_err,
        "expected_below_reason": REFUSE_BELOW_CRITERION,
        "expected_missing_reason": REFUSE_WITHOUT_CRITERION,
        "gate_uses_json_number": criterion == cfg.arming_criterion
        and (prose_value is None or criterion != prose_value),
    }


def measure_all() -> dict:
    zero = measure_zero_effect()
    gate = measure_arming_gate()
    return {"zero_effect": zero, "arming_gate": gate, "armed_ok_token": ARMED_OK}
