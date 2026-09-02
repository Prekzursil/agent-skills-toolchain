#!/usr/bin/env python3
"""Probe 2: retired-definition retrieval rehearsal + owner-visible refusal.

Independent of probe 1. Preservation is hashed and retrieved by content.
Owner-relied retirement without sign-off is refused and writes no edge.
A non-owner-relied helper may supersede without sign-off (both-states).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import supersession as S  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0119-decertification-and-supersession.json"


def main() -> int:
    ctrls = S.run_controls()
    ok, failed = S.controls_ok(ctrls)
    h, n, u = ctrls["happy"], ctrls["no_owner"], ctrls["unused_no_owner"]
    print(
        f"retrieval ok={h['retrieval']['ok']} sha={h['preservation']['sha256']} "
        f"bytes={h['preservation']['bytes']} path={h['preservation']['path']}"
    )
    print(
        f"no_owner accepted={n['accepted']} refusals={n['refusals']} "
        f"status={n['retired_status_after']} edge={n['superseded_by']}"
    )
    print(
        f"unused_no_owner accepted={u['accepted']} owner_required={u['owner']['required']} "
        f"status={u['retired_status_after']}"
    )
    if not ok:
        print("FAILED:WFA-0119-probe2 " + ",".join(failed))
        return 1

    retrieved = S.retrieve_definition(h["preservation"]["sha256"])
    if not retrieved.get("ok"):
        print("FAILED:WFA-0119-probe2 live-retrieval-failed")
        return 1
    expected_def = S.load_workflows()["wf-certified-intake-v1"]["definition"]
    if retrieved.get("definition") != expected_def:
        print("FAILED:WFA-0119-probe2 retrieved-definition-mismatch")
        return 1

    # Owner-relied + missing sign-off must not retire; unused helper may.
    if n["accepted"] or not u["accepted"]:
        print("FAILED:WFA-0119-probe2 owner-both-states")
        return 1
    if n["retired_status_after"] != "CERTIFIED":
        print("FAILED:WFA-0119-probe2 owner-refuse-mutated-status")
        return 1

    if not ART.is_file():
        print("FAILED:WFA-0119-probe2 artifact-missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:WFA-0119-probe2 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:WFA-0119" not in text:
        print("FAILED:WFA-0119-probe2 sentinel-absent")
        return 1
    tests = doc.get("tests") or {}
    if tests.get("retired_definition_retrievable") is not True:
        print("FAILED:WFA-0119-probe2 artifact-missing-retrieval")
        return 1
    if tests.get("owner_relied_without_signoff_refused") is not True:
        print("FAILED:WFA-0119-probe2 artifact-missing-owner-refuse")
        return 1
    if tests.get("non_owner_relied_without_signoff_accepted") is not True:
        print("FAILED:WFA-0119-probe2 artifact-missing-unused-accept")
        return 1
    pres = (doc.get("supersession") or {}).get("preservation") or {}
    if pres.get("sha256") != h["preservation"]["sha256"]:
        print("FAILED:WFA-0119-probe2 artifact-preservation-hash-drift")
        return 1
    if doc.get("production_retirement") != "not-executed":
        print("FAILED:WFA-0119-probe2 overclaim-production-retirement")
        return 1
    print("SUCCESS:WFA-0119-probe2 retrieval-rehearsal owner-visible both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
