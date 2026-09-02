#!/usr/bin/env python3
"""Named probe 2: lineage-stripped fixture is REFUSED at publish (both-states).

Different field than probe 1: this reads publish.accepted / refusal_id, not
round-trip sha256. Good state must accept; stripped and licence-stripped must
refuse with the named failure class.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from lineage import (  # noqa: E402
    FAILURE_CLASS,
    REFUSAL_ID,
    LineageError,
    export_workflow,
    publish,
    strip_licences,
    strip_lineage,
)
from scenario import fused_union_alpha  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0179.json"
STRIPPED = HERE / "fixtures/lineage-stripped.json"


def _must_refuse(label: str, doc: dict) -> dict:
    result = publish(doc)
    if result.get("accepted"):
        raise AssertionError(f"{label} was accepted")
    if result.get("refusal_id") != REFUSAL_ID:
        raise AssertionError(f"{label} refusal_id={result.get('refusal_id')} want={REFUSAL_ID}")
    if result.get("failure_class") != FAILURE_CLASS:
        raise AssertionError(f"{label} failure_class={result.get('failure_class')!r}")
    if not result.get("issues"):
        raise AssertionError(f"{label} refused without issues")
    export_refused = False
    try:
        export_workflow(doc)
    except LineageError:
        export_refused = True
    if not export_refused:
        raise AssertionError(f"{label} export did not refuse (lossy round-trip would be possible)")
    return result


def main() -> int:
    good = fused_union_alpha()
    accepted = publish(good)
    if not accepted.get("accepted"):
        print("FAILED:IMP-0179-probe2 good-state publish refused")
        print(json.dumps(accepted, indent=2, default=str)[:3000])
        return 1

    runtime_stripped = strip_lineage(good)
    try:
        stripped_pub = _must_refuse("runtime-stripped", runtime_stripped)
    except AssertionError as exc:
        print(f"FAILED:IMP-0179-probe2 {exc}")
        return 1

    if not STRIPPED.is_file():
        print("FAILED:IMP-0179-probe2 fixtures/lineage-stripped.json missing")
        return 1
    file_stripped = json.loads(STRIPPED.read_text(encoding="utf-8"))
    if "lineage" in file_stripped:
        print("FAILED:IMP-0179-probe2 committed stripped fixture still has lineage")
        return 1
    try:
        file_pub = _must_refuse("file-stripped", file_stripped)
    except AssertionError as exc:
        print(f"FAILED:IMP-0179-probe2 {exc}")
        return 1

    licence_stripped = strip_licences(good)
    try:
        licence_pub = _must_refuse("licence-stripped", licence_stripped)
    except AssertionError as exc:
        print(f"FAILED:IMP-0179-probe2 {exc}")
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:IMP-0179-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    publish_block = doc.get("publish") or {}
    if publish_block.get("good_accepted") is not True:
        print("FAILED:IMP-0179-probe2 receipt good_accepted is not true")
        return 1
    if publish_block.get("stripped_refused") is not True:
        print("FAILED:IMP-0179-probe2 receipt stripped_refused is not true")
        return 1
    if publish_block.get("refusal_id") != REFUSAL_ID:
        print("FAILED:IMP-0179-probe2 receipt refusal_id drift")
        return 1

    out = {
        "probe": "probe2-publish-refuse",
        "unit_id": "IMP-0179",
        "good_accepted": True,
        "runtime_stripped_refused": True,
        "file_stripped_refused": True,
        "licence_stripped_refused": True,
        "refusal_id": REFUSAL_ID,
        "failure_class": FAILURE_CLASS,
        "stripped_issue_count": len(stripped_pub.get("issues") or []),
        "file_issue_count": len(file_pub.get("issues") or []),
        "licence_issue_count": len(licence_pub.get("issues") or []),
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "good=ACCEPT stripped=REFUSE file=REFUSE licence=REFUSE "
        f"refusal_id={REFUSAL_ID}"
    )
    print("SUCCESS:IMP-0179-probe2 lineage-stripped publish refusal both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
