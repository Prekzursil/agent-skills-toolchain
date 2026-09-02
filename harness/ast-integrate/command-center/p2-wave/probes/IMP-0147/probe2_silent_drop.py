#!/usr/bin/env python3
"""IMP-0147 probe 2: unmigratable fixture is a typed refusal; silent-drop goes red."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.migrate import (  # noqa: E402
    REFUSAL_DOWNGRADE,
    REFUSAL_UNKNOWN_KEY,
    migrate,
    migrate_skip_unknown_keys,
)
from agentspec.spec import CURRENT_SPEC_VERSION, SPEC_VERSION_PRE_PHASE7  # noqa: E402

HERE = Path(__file__).resolve().parent
UNMIGRATABLE = HERE / "fixtures" / "unmigratable-unknown-key.json"
TWIN = HERE / "fixtures" / "new-twin.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def refusal_test(result) -> bool:
    """The load-bearing assertion: typed refusal, no partial workflow."""
    return (
        result.ok is False
        and result.workflow is None
        and result.refusal_id == REFUSAL_UNKNOWN_KEY
    )


def main() -> int:
    bad = _load(UNMIGRATABLE)
    good = migrate(_load(TWIN))  # already current; identity
    if not good.ok or good.workflow is None:
        print(f"FAILED:IMP-0147-probe2 current twin refused: {good.refusal_id}")
        return 1

    live = migrate(bad)
    if not refusal_test(live):
        print(
            "FAILED:IMP-0147-probe2 live migrator did not refuse unknown key: "
            f"ok={live.ok} id={live.refusal_id} workflow={live.workflow is not None}"
        )
        return 1

    mutant = migrate_skip_unknown_keys(bad)
    mutant_would_pass_refusal_test = refusal_test(mutant)
    if mutant_would_pass_refusal_test:
        print("FAILED:IMP-0147-probe2 silent-drop mutant still refuses; test is not load-bearing")
        return 1
    if not mutant.ok or mutant.workflow is None:
        print(
            "FAILED:IMP-0147-probe2 silent-drop mutant did not produce a partial workflow: "
            f"ok={mutant.ok} id={mutant.refusal_id}"
        )
        return 1
    # Partial graph: mystery_payload was dropped rather than refused.
    dropped = True
    for node in mutant.workflow.get("nodes") or []:
        if "mystery_payload" in node:
            dropped = False
    if not dropped:
        print("FAILED:IMP-0147-probe2 mutant did not drop mystery_payload")
        return 1

    # new -> old is refused, never a reverse rewrite.
    current = dict(good.workflow)
    current["spec_version"] = CURRENT_SPEC_VERSION
    down = migrate(current, target=SPEC_VERSION_PRE_PHASE7)
    if down.ok or down.workflow is not None or down.refusal_id != REFUSAL_DOWNGRADE:
        print(
            "FAILED:IMP-0147-probe2 new->old was not refused: "
            f"ok={down.ok} id={down.refusal_id} workflow={down.workflow is not None}"
        )
        return 1

    payload = {
        "probe": "probe2-silent-drop-refusal",
        "unit_id": "IMP-0147",
        "pass": True,
        "live_refusal_id": live.refusal_id,
        "live_partial_workflow": live.workflow is not None,
        "mutant_refusal_test_goes_red": not mutant_would_pass_refusal_test,
        "mutant_ok": mutant.ok,
        "mutant_dropped_unknown_key": dropped,
        "downgrade_refusal_id": down.refusal_id,
        "downgrade_partial_workflow": down.workflow is not None,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:IMP-0147-probe2 unmigratable fixture typed-refusal; "
        "silent-drop mutation makes refusal test go red"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
