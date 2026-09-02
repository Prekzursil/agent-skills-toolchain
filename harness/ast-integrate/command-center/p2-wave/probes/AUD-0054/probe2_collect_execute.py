#!/usr/bin/env python3
"""Probe 2: collect-versus-execute on a real run; catches runtime-only skips."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402

ART = C.REPO / "command-center/audit/AUD-0054-platform-conditional-tests.json"


def main() -> int:
    ast_doc = C.ast_census()
    run_doc = C.run_fixture_suite()
    indep = C.independence(ast_doc, run_doc)
    errors: list[str] = []
    if not run_doc["runtime_control_collected"]:
        errors.append("runtime-only node was not collected")
    if run_doc["runtime_control_executed"]:
        errors.append("runtime-only node executed; expected skip")
    if not run_doc["runtime_control_skipped"]:
        errors.append("runtime-only node was not skipped at runtime")
    if sys.platform.startswith("win"):
        if not run_doc["posix_control_skipped"]:
            errors.append("posix-only control did not skip on Windows")
    else:
        if not run_doc["windows_control_skipped"]:
            errors.append("windows-only control did not skip on this POSIX host")
        if not run_doc["posix_control_executed"]:
            errors.append("posix-only control did not execute on this POSIX host")
    if not indep["independent"]:
        errors.append(indep["reason"])
    if ast_doc["runtime_control_in_decorator_scan"]:
        errors.append("probe 1 would also see the runtime skip; pair not independent")

    payload = {
        "probe": "probe2-collect-execute",
        "host_platform": run_doc["host_platform"],
        "collected": run_doc["collected"],
        "executed": run_doc["executed"],
        "skipped": run_doc["skipped"],
        "collected_minus_executed": run_doc["collected_minus_executed"],
        "independence": indep,
        "errors": errors,
    }
    print(json.dumps(payload, sort_keys=True))

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            errors.append(f"artifact self-declared {st}")
        if C.art_section(doc, "independence").get("independent") is not True:
            errors.append("artifact missing independence=true")

    if errors:
        print("FAILED:AUD-0054-probe2 " + "; ".join(errors))
        return 1
    print(
        "collected={0} executed={1} skipped={2} runtime_only_skipped=True independent=True".format(
            len(run_doc["collected"]),
            len(run_doc["executed"]),
            len(run_doc["skipped"]),
        )
    )
    print("SUCCESS:AUD-0054-probe2 collect-vs-execute found runtime-only skip probe 1 missed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
