#!/usr/bin/env python3
"""Named probe 2: post-rollback capability vector equals the sources' union.

Mechanically different from probe 1 (set equality over capability ids, not
structural fingerprints). Plants a LOSSY fusion that dropped `audit` while in
service; rollback must recover it so the restored vector equals the union of
the originals. A sabotaged restore that strips a capability must FIRE. An
honest lossless fusion must also satisfy set equality (false-positive control).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from tools.workflow.fusion_rollback import (  # noqa: E402
    capability_vector,
    rollback,
    sabotaged_restore_fires,
)
import scenario as S  # noqa: E402


def main() -> int:
    expected = S.original_capability_union()

    # Lossy fusion IN SERVICE: body dropped `audit`. Rollback must recover it.
    svc, fusion = S.armed_service(
        "union_collapse", "wf.fusion.lossy-in-service", lossy=True, enqueue=True
    )
    fusion_caps = capability_vector(fusion)
    if "audit" in fusion_caps:
        print("FAILED:IMP-0205-probe2 planted loss did not drop audit from fusion body")
        return 1
    if fusion_caps == expected:
        print("FAILED:IMP-0205-probe2 lossy fusion unexpectedly equals source union")
        return 1
    result = rollback(svc, "wf.fusion.lossy-in-service")
    restored = svc.capability_vector()
    lost = sorted(expected - restored)
    extra = sorted(restored - expected)
    if lost or extra:
        print(
            f"FAILED:IMP-0205-probe2 capability set unequal lost={lost} extra={extra}"
        )
        return 1
    if "audit" not in restored:
        print("FAILED:IMP-0205-probe2 dropped capability was not recovered")
        return 1
    if result.get("dropped_capability_recovered") is not True:
        print("FAILED:IMP-0205-probe2 recovery flag unset")
        return 1

    # False-positive control: lossless fusion also has empty set difference.
    svc2, _ = S.armed_service(
        "conditional_hybrid", "wf.fusion.honest", lossy=False, enqueue=False
    )
    r2 = rollback(svc2, "wf.fusion.honest")
    honest_vec = svc2.capability_vector()
    if honest_vec != expected:
        print(f"FAILED:IMP-0205-probe2 honest fusion rollback vector {sorted(honest_vec)}")
        return 1
    if not r2["capability_set_equal"]:
        print("FAILED:IMP-0205-probe2 honest fusion set-equal flag false")
        return 1

    # Both-states: sabotaged restore that strips `cite` MUST fire.
    control = sabotaged_restore_fires(fusion, drop_capability="cite")
    if not control["fired"] or "cite" not in control["lost"]:
        print(f"FAILED:IMP-0205-probe2 sabotaged restore did not fire: {control}")
        return 1
    if control["set_equal"]:
        print("FAILED:IMP-0205-probe2 sabotaged restore reported set equality")
        return 1

    report = {
        "probe": "probe2-capability-union",
        "unit_id": "IMP-0205",
        "pass": True,
        "fusion_body_dropped": "audit",
        "fusion_vector_before_rollback": sorted(fusion_caps),
        "source_union": sorted(expected),
        "restored_vector": sorted(restored),
        "set_difference_empty": True,
        "dropped_capability_recovered": True,
        "honest_fusion_also_equal": True,
        "sabotaged_restore_fired": True,
        "sabotaged_lost": control["lost"],
    }
    print(json.dumps(report, sort_keys=True))
    print(
        "lossy_dropped=audit recovered=True union_equal=True "
        f"sabotage_fired={control['fired']} honest_equal=True"
    )
    print("SUCCESS:IMP-0205-probe2 post-rollback capability vector equals sources union")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
