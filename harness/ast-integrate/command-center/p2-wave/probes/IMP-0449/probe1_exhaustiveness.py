#!/usr/bin/env python3
"""Named probe 1: exhaustiveness. Unclassifiable input is UNCLASSIFIED FAILED.

Never silent SUCCESS. Never empty return. Classify never returns SUCCESS.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import failure_taxonomy as ft  # noqa: E402

CASES = [
    "",
    None,
    "the adapter seemed fine overall",
    "lorem ipsum dolor sit amet",
    {"text": "unexpected rainbow sparkles from the vendor"},
    {"message": "ok"},
    RuntimeError("something went sideways in a way nobody named"),
]


def main() -> int:
    failures: list[str] = []

    for i, raw in enumerate(CASES):
        result = ft.format_tool_result(f"IMP-0449-ex{i}", observation=raw)
        if result is None:
            failures.append(f"case{i} empty-return None")
            continue
        if not isinstance(result, ft.TerminalResult):
            failures.append(f"case{i} type={type(result).__name__}")
            continue
        if result.status != "FAILED":
            failures.append(f"case{i} status={result.status} (unclassified-becomes-success)")
        if result.class_ != ft.UNCLASSIFIED:
            failures.append(f"case{i} class={result.class_} want UNCLASSIFIED")
        if not result.reason:
            failures.append(f"case{i} empty reason")
        if not result.id:
            failures.append(f"case{i} empty id")
        marker = result.marker
        if not marker.startswith("FAILED:"):
            failures.append(f"case{i} marker={marker!r}")
        doc = ft.result_to_json(result)
        if "body" in doc or "prose" in doc or "message" in doc:
            failures.append(f"case{i} open-ended field leaked")
        dumped = json.dumps(doc)
        if result.status == "SUCCESS" or '"status": "SUCCESS"' in dumped and result.class_ == ft.UNCLASSIFIED:
            # SUCCESS in dump of a FAILED unclassified result would be a defect
            if doc.get("status") == "SUCCESS":
                failures.append(f"case{i} json SUCCESS")

    empty = ft.format_tool_result("IMP-0449-empty")
    if empty.status != "FAILED" or empty.class_ != ft.UNCLASSIFIED:
        failures.append(f"empty-call {empty.status}/{empty.class_}")
    if "empty-return" not in (empty.reason or ""):
        failures.append(f"empty-call reason={empty.reason!r}")

    ok = ft.format_tool_result("IMP-0449", ok=True)
    if ok.status != "SUCCESS" or ok.class_ is not None or not ok.marker.startswith("SUCCESS:IMP-0449"):
        failures.append(f"explicit-success {ok.to_json()}")

    cls_ok = ft.classify("totally novel vendor burp 0xZZ")
    if cls_ok != ft.UNCLASSIFIED:
        failures.append(f"classify returned {cls_ok}")
    if cls_ok == "SUCCESS" or str(cls_ok).upper() == "SUCCESS":
        failures.append("classify returned SUCCESS")

    for cls in ft.TAXONOMY_CLASSES:
        typed = {
            "win-arg-limit": ft.Observation(winerror=206, text="CreateProcess"),
            "timeout": ft.Observation(timed_out=True, exit_code=124),
            "schema-invalid": ft.Observation(schema_errors=3, artifact_present=True),
            "partial-artifact": ft.Observation(
                artifact_present=True, artifact_bytes=0
            ),
            "severed-stream": ft.Observation(exit_code=0, artifact_present=False),
            "adapter-exit-n": ft.Observation(exit_code=127),
            "blocked": ft.Observation(state="BLOCKED"),
            "degraded": ft.Observation(state="DEGRADED"),
        }[cls]
        got = ft.classify(typed)
        if got != cls:
            failures.append(f"typed {cls} -> {got}")
        formatted = ft.format_failure("IMP-0449-typed", typed)
        if formatted.status != "FAILED" or formatted.class_ != cls:
            failures.append(f"format typed {cls} -> {formatted.to_json()}")

    try:
        ft.TerminalResult(status="FAILED", id="x", reason="", class_="timeout")
        failures.append("empty-reason FAILED was allowed")
    except ft.TaxonomyError:
        pass

    try:
        ft.TerminalResult(status="SUCCESS", id="x", reason="nope")
        failures.append("SUCCESS with reason was allowed")
    except ft.TaxonomyError:
        pass

    if failures:
        print("FAILED:IMP-0449-probe1 exhaustiveness")
        for item in failures:
            print(" ", item)
        return 1

    print(
        json.dumps(
            {
                "probe": "probe1-exhaustiveness",
                "unit_id": "IMP-0449",
                "unclassified_cases": len(CASES) + 1,
                "unclassified_became_success": 0,
                "empty_returns": 0,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:IMP-0449-probe1 exhaustiveness UNCLASSIFIED never success never empty")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
