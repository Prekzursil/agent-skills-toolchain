#!/usr/bin/env python3
"""Probe 2: forbidden pair refused at the FUSION entry point, not the matrix unit.

Signal 2 of IMP-0157. Calls fuse_workflows (the real fusion API). Spies
licence_matrix.solve_licences to prove the path CALLS the matrix. Copyleft +
proprietary must raise FusionRefused with named reason COPYLEFT_PROPRIETARY and
suggested alternative CLEAN-ROOM-REIMPLEMENT, and must not yield a fused body.

Both-states: MIT+Apache-2.0 fuses; GPL-3.0-only + LicenseRef-Proprietary refuses.
Contrast: MIT + proprietary is allowed (most-restrictive-wins to proprietary).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from workflow_foundry import fusion as fusion_mod  # noqa: E402
from workflow_foundry import licence_matrix as lm  # noqa: E402
from workflow_foundry.fusion import (  # noqa: E402
    FusionRefused,
    WorkflowSource,
    fuse_workflows,
)
from workflow_foundry.licence_matrix import (  # noqa: E402
    REASON_COPYLEFT_PROPRIETARY,
    SUGGESTED_ALTERNATIVE_CLEAN_ROOM,
)


def _fail(msg: str, payload: dict | None = None) -> int:
    if payload:
        print(json.dumps(payload, indent=2, sort_keys=True))
    print(f"FAIL:IMP-0157-probe2 {msg}")
    return 1


def main() -> int:
    calls: list[list[str]] = []
    real = lm.solve_licences

    def spy(inbound, *rest, **kwargs):
        calls.append(list(inbound))
        return real(inbound, *rest, **kwargs)

    lm.solve_licences = spy  # type: ignore[assignment]
    try:
        # --- bad state: copyleft + proprietary ---
        copyleft = WorkflowSource(
            id="wf-gpl",
            licence="GPL-3.0-only",
            body="echo gpl-stage\n",
            credit="GPL author",
        )
        proprietary = WorkflowSource(
            id="wf-prop",
            licence="LicenseRef-Proprietary",
            body="echo secret-stage\n",
            credit="Vendor Inc",
        )
        fused_body = None
        refused: FusionRefused | None = None
        try:
            product = fuse_workflows([copyleft, proprietary], fused_id="illegal")
            fused_body = product.body
        except FusionRefused as exc:
            refused = exc

        if fused_body is not None:
            return _fail("copyleft+proprietary silently produced a fused body")
        if refused is None:
            return _fail("copyleft+proprietary did not raise FusionRefused")
        if refused.reason != REASON_COPYLEFT_PROPRIETARY:
            return _fail(
                f"reason {refused.reason!r} != {REASON_COPYLEFT_PROPRIETARY}",
                refused.verdict.as_dict(),
            )
        if refused.suggested_alternative != SUGGESTED_ALTERNATIVE_CLEAN_ROOM:
            return _fail(
                f"alternative {refused.suggested_alternative!r} "
                f"!= {SUGGESTED_ALTERNATIVE_CLEAN_ROOM}"
            )
        if not any("GPL-3.0-only" in c and "LicenseRef-Proprietary" in c for c in calls):
            return _fail(
                "fusion entry did not call licence_matrix.solve_licences "
                "with the inbound pair (path does not CALL the matrix)",
                {"calls": calls},
            )

        # --- good state: MIT + Apache-2.0 ---
        mit = WorkflowSource(id="wf-mit", licence="MIT", body="echo mit\n")
        apache = WorkflowSource(id="wf-apache", licence="Apache-2.0", body="echo apache\n")
        ok = fuse_workflows([mit, apache], fused_id="ok-permissive")
        if ok.licence != "Apache-2.0":
            return _fail(f"MIT+Apache outbound expected Apache-2.0, got {ok.licence!r}")
        if "echo mit" not in ok.body or "echo apache" not in ok.body:
            return _fail("permissive fusion dropped a source body")

        # Contrast: permissive + proprietary is allowed (not the copyleft case).
        prop_ok = fuse_workflows(
            [
                WorkflowSource(id="a", licence="MIT", body="a\n"),
                WorkflowSource(id="b", licence="LicenseRef-Proprietary", body="b\n"),
            ],
            fused_id="ok-prop",
        )
        if prop_ok.licence != "LicenseRef-Proprietary":
            return _fail(
                f"MIT+proprietary should outbound proprietary, got {prop_ok.licence!r}"
            )

        # UNKNOWN inbound must not default to MIT via the fusion path either.
        unknown_refused = False
        try:
            fuse_workflows(
                [
                    WorkflowSource(id="u", licence="UNKNOWN", body="u\n"),
                    WorkflowSource(id="m", licence="MIT", body="m\n"),
                ]
            )
        except FusionRefused:
            unknown_refused = True
        if not unknown_refused:
            return _fail("UNKNOWN+MIT fused (silent permissive default)")

        # Direct matrix call is NOT this probe's evidence — but confirm the
        # fusion module is still bound to the spied function object.
        if fusion_mod.licence_matrix.solve_licences is not spy:
            return _fail("fusion.py is not using licence_matrix.solve_licences")
    finally:
        lm.solve_licences = real  # type: ignore[assignment]

    report = {
        "probe": "probe2_fusion_entry",
        "called_fusion_api": "fuse_workflows",
        "called_matrix": True,
        "matrix_call_count": len(calls),
        "copyleft_proprietary": {
            "refused": True,
            "reason": REASON_COPYLEFT_PROPRIETARY,
            "suggested_alternative": SUGGESTED_ALTERNATIVE_CLEAN_ROOM,
            "fused_body_produced": False,
        },
        "mit_apache_fused": True,
        "mit_apache_outbound": "Apache-2.0",
        "mit_proprietary_allowed": True,
        "unknown_plus_mit_refused_at_fusion": True,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(
        "refused=COPYLEFT_PROPRIETARY alternative=CLEAN-ROOM-REIMPLEMENT "
        f"matrix_calls={len(calls)} mit_apache=Apache-2.0"
    )
    print("SUCCESS:IMP-0157-probe2 fusion entry refuses copyleft+proprietary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
