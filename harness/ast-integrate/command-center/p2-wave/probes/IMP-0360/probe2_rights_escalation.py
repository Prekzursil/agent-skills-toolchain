#!/usr/bin/env python3
"""Probe 2: negative control — rights-escalating custom role must be refused.

Starts from the tests (not an author summary): attempt to author a custom
role that grants a tool no builtin template allows (runtime.unrestricted).
Both-states: the same observer-based spec without that tool is accepted;
with the tool, author_custom_role returns accepted=False and
rights_escalation_check.fired is True. Stripping the ceiling tokens from a
planted-bad role must make the check SILENT, proving it is not stuck-on.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.roles.templates import (  # noqa: E402
    NEVER_GRANTED_PERMISSION,
    NEVER_GRANTED_SOURCE,
    NEVER_GRANTED_TOOL,
    RoleMandate,
    author_custom_role,
    builtin_registry,
    rights_escalation_check,
)

ART = REPO / "command-center/receipts/IMP-0360.json"
UNIT = "IMP-0360"


def _observer_spec(**overrides):
    spec = {
        "id": "custom.observer.probe",
        "name": "Probe observer",
        "template_id": "observer",
        "tool_access": ["read"],
        "speaking": True,
        "vote": False,
        "veto": False,
        "vote_weight": 0.0,
    }
    spec.update(overrides)
    return spec


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:IMP-0360-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("unit_id")) != UNIT or "SUCCESS:IMP-0360" not in ART.read_text(encoding="utf-8"):
        print("FAILED:IMP-0360-probe2 receipt sentinel/unit_id")
        return 1
    reviewer = doc.get("reviewer") or {}
    if str(doc.get("reviewer_verdict") or reviewer.get("verdict") or "").upper() != "PASS":
        print("FAILED:IMP-0360-probe2 reviewer_verdict not PASS")
        return 1

    reg = builtin_registry()
    ceiling = reg.ceiling()
    if NEVER_GRANTED_TOOL in ceiling.tools:
        print(f"FAILED:IMP-0360-probe2 {NEVER_GRANTED_TOOL} is already on the ceiling")
        return 1
    if NEVER_GRANTED_SOURCE in ceiling.sources:
        print(f"FAILED:IMP-0360-probe2 {NEVER_GRANTED_SOURCE} is already on the ceiling")
        return 1
    if NEVER_GRANTED_PERMISSION in ceiling.permissions:
        print(f"FAILED:IMP-0360-probe2 {NEVER_GRANTED_PERMISSION} is already on the ceiling")
        return 1

    good = author_custom_role(_observer_spec(), reg)
    print(f"good_state accepted={good.accepted} fired={None if good.escalation is None else good.escalation.fired}")
    if not good.accepted or good.role is None:
        print(f"FAILED:IMP-0360-probe2 good custom role refused {list(good.refusals)}")
        return 1
    good_check = rights_escalation_check(good.role, reg, base=reg.get("observer"))
    print(f"good_state_check fired={good_check.fired} reasons={list(good_check.reasons)}")
    if good_check.fired:
        print("FAILED:IMP-0360-probe2 escalation check not silent on known-good")
        return 1

    bad = author_custom_role(
        _observer_spec(
            id="custom.observer.escalate",
            tool_access=["read", NEVER_GRANTED_TOOL],
        ),
        reg,
    )
    print(f"bad_state accepted={bad.accepted} refusals={list(bad.refusals)}")
    if bad.accepted or bad.role is not None:
        print("FAILED:IMP-0360-probe2 rights-escalating role was accepted")
        return 1
    if bad.escalation is None or not bad.escalation.fired:
        print("FAILED:IMP-0360-probe2 refusal was not an escalation fire")
        return 1
    if NEVER_GRANTED_TOOL not in ",".join(bad.escalation.excess_tools):
        print(f"FAILED:IMP-0360-probe2 excess_tools={bad.escalation.excess_tools}")
        return 1
    if not any("rights-escalation:tool_access" in r for r in bad.refusals):
        print("FAILED:IMP-0360-probe2 refusals missing rights-escalation:tool_access")
        return 1

    # Planted-bad mandate (bypass author) must FIRE; remove the extra tool and
    # the same check must be SILENT (both-states, detector not stuck-on).
    observer = reg.get("observer")
    assert observer is not None
    planted = RoleMandate(
        id="planted.escalate",
        name="Planted",
        kind="custom",
        template_id="observer",
        obligations=observer.obligations,
        permissions=observer.permissions,
        tool_access=observer.tool_access | frozenset({NEVER_GRANTED_TOOL}),
        source_access=observer.source_access,
        speaking=observer.speaking,
        vote=observer.vote,
        veto=observer.veto,
        vote_weight=observer.vote_weight,
        incompatible_with=observer.incompatible_with,
    )
    planted_fire = rights_escalation_check(planted, reg, base=observer)
    print(f"planted_bad fired={planted_fire.fired} reasons={list(planted_fire.reasons)}")
    if not planted_fire.fired:
        print("FAILED:IMP-0360-probe2 planted-bad did not fire")
        return 1
    restored = RoleMandate(
        id="planted.restored",
        name="Restored",
        kind="custom",
        template_id="observer",
        obligations=observer.obligations,
        permissions=observer.permissions,
        tool_access=observer.tool_access,
        source_access=observer.source_access,
        speaking=observer.speaking,
        vote=observer.vote,
        veto=observer.veto,
        vote_weight=observer.vote_weight,
        incompatible_with=observer.incompatible_with,
    )
    restored_check = rights_escalation_check(restored, reg, base=observer)
    print(f"planted_restored fired={restored_check.fired}")
    if restored_check.fired:
        print("FAILED:IMP-0360-probe2 restored planted role still fires")
        return 1

    # Second escalation axis: permission no template allows.
    perm_bad = author_custom_role(
        _observer_spec(
            id="custom.observer.override",
            permissions=[NEVER_GRANTED_PERMISSION],
        ),
        reg,
    )
    print(f"perm_bad accepted={perm_bad.accepted} refusals={list(perm_bad.refusals)}")
    if perm_bad.accepted or not any("rights-escalation:permissions" in r for r in perm_bad.refusals):
        print("FAILED:IMP-0360-probe2 override_quorum permission was not refused as escalation")
        return 1

    # Exceeding the cited template with a grant that *some other* template has
    # (chair veto) must still be refused — custom observer cannot self-grant veto.
    veto_bad = author_custom_role(
        _observer_spec(id="custom.observer.veto", veto=True),
        reg,
    )
    print(f"veto_bad accepted={veto_bad.accepted} refusals={list(veto_bad.refusals)}")
    if veto_bad.accepted or not any("exceeds-template:veto" in r for r in veto_bad.refusals):
        print("FAILED:IMP-0360-probe2 observer+veto was not refused as exceeds-template")
        return 1
    # Global ceiling includes chair.veto, so this is exceeds-template, not
    # "no template allows". Confirm the two detectors discriminate.
    if veto_bad.escalation is not None and "veto" in veto_bad.escalation.excess_rights:
        print("FAILED:IMP-0360-probe2 observer veto misclassified as global-ceiling excess")
        return 1

    extra_key = author_custom_role(
        _observer_spec(id="custom.observer.extra", **{"self_grant_admin": True}),
        reg,
    )
    print(f"extra_key accepted={extra_key.accepted} refusals={list(extra_key.refusals)}")
    if extra_key.accepted or "schema-invalid:unknown-fields" not in extra_key.refusals:
        print("FAILED:IMP-0360-probe2 extra mandate field was not schema-refused")
        return 1

    out = {
        "pass": True,
        "probe": "probe2-rights-escalation",
        "unit_id": UNIT,
        "good_silent": True,
        "escalation_refused": True,
        "never_granted_tool": NEVER_GRANTED_TOOL,
        "planted_both_states": True,
        "permission_escalation_refused": True,
        "exceeds_template_veto_refused": True,
        "unknown_field_refused": True,
        "reviewer_id": "IMP-0360-probe2-rights-escalation",
        "reviewer_verdict": "PASS",
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:IMP-0360-probe2 rights-escalating custom role refused")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
