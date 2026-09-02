#!/usr/bin/env python3
"""Named probe 2: go/no-go uses the shared oracle (AST) plus live call.

Mechanically different from probe 1 (AST of go_no_go.py, not file hashes).
Planted rival local checklist must be detected. Exit-zero-only evidence must
be NO-GO.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from ast_check import analyze_path, rival_is_detected  # noqa: E402
from go_no_go import release_go_no_go  # noqa: E402

GO_NO_GO = HERE / "go_no_go.py"


def _write_complete_fixture(root: Path) -> dict:
    art = root / "complete.json"
    body = {
        "unit_id": "IMP-0241-fixture",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0241-fixture",
        "ok": True,
    }
    art.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    return {
        "repo": str(root),
        "artifact_path": str(art),
        "state": "SUCCESS",
        "expected_sentinel": "SUCCESS:IMP-0241-fixture",
        "min_bytes_threshold": 8,
        "exit_code": 0,
        "evidence": [
            {
                "anchor": "file:complete.json",
                "probes": [
                    {"role": "source", "command": "write"},
                    {"role": "verifier", "command": "read"},
                ],
            }
        ],
        "tests": [{"id": "t1", "result": "PASS"}],
        "negative_controls": [
            {"id": "c1", "fired_on_bad_state": True, "silent_on_good_state": True}
        ],
        "reviewer": {"reviewer_id": "probe2-ast", "verdict": "PASS", "independent": True},
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0241/UNIT-ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {"consumer": "probe2", "executed": True, "read_ok": True}
        ],
    }


def main() -> int:
    live = analyze_path(GO_NO_GO)
    rival = rival_is_detected()
    print(json.dumps({"live": live, "rival": rival}, sort_keys=True))
    if not live.get("uses_shared_oracle"):
        print("FAILED:IMP-0241-probe2 go_no_go.py does not call oracle.judge")
        return 1
    if live.get("local_checklist"):
        print("FAILED:IMP-0241-probe2 local checklist present in go_no_go.py")
        return 1
    if live.get("exit_zero_as_go"):
        print("FAILED:IMP-0241-probe2 go_no_go treats exit_code as GO")
        return 1
    if rival.get("uses_shared_oracle"):
        print("FAILED:IMP-0241-probe2 planted rival checklist was not detected")
        return 1
    if not rival.get("local_checklist"):
        print("FAILED:IMP-0241-probe2 detector silent on all(checklist) rival")
        return 1

    exit_only = release_go_no_go({"exit_code": 0, "state": "SUCCESS"})
    if exit_only.get("decision") != "NO-GO":
        print("FAILED:IMP-0241-probe2 exit-zero-only evidence returned GO")
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0241-p2-") as tmp:
        complete = release_go_no_go(_write_complete_fixture(Path(tmp)))
    if complete.get("decision") != "GO":
        print("FAILED:IMP-0241-probe2 complete fixture was not GO")
        print(json.dumps(complete, indent=2, default=str)[:2000])
        return 1
    if complete.get("reducer") != "oracle.judge":
        print("FAILED:IMP-0241-probe2 decision did not record shared reducer")
        return 1
    if (complete.get("oracle") or {}).get("reducer") != "oracle.judge":
        print("FAILED:IMP-0241-probe2 nested oracle reducer missing")
        return 1

    print(
        "ast_shared=True rival_detected=True "
        f"exit_only={exit_only.get('decision')} complete={complete.get('decision')}"
    )
    print("SUCCESS:IMP-0241-probe2 go/no-go uses shared oracle.judge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
