#!/usr/bin/env python3
"""Named probe 2: the same undeclared Write is blocked at the tool layer."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from permission_layers import run_demonstration  # noqa: E402

ART = REPO / "command-center/research/RES-0056.json"


def main() -> int:
    if not ART.is_file():
        print("FAILED:RES-0056-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "blocked at the tool layer" not in text:
        print("FAILED:RES-0056-probe2 tool-layer phrase absent")
        return 1
    if "SUCCESS:RES-0056" not in text:
        print("FAILED:RES-0056-probe2 sentinel absent")
        return 1

    effective = [m for m in doc.get("mitigations") or [] if m.get("recorded_as_effective")]
    theatre = [m for m in doc.get("mitigations") or [] if m.get("classification") == "security-theatre"]
    if len(effective) < 1:
        print("FAILED:RES-0056-probe2 no effective mitigation after bypass review")
        return 1
    if len(theatre) < 1:
        print("FAILED:RES-0056-probe2 theatre not named")
        return 1
    for m in effective:
        if m.get("bypass_outcome") != "HELD":
            print("FAILED:RES-0056-probe2 effective mitigation not held under bypass")
            return 1
    for m in theatre:
        if m.get("recorded_as_effective") is True:
            print("FAILED:RES-0056-probe2 theatre recorded as effective")
            return 1

    with tempfile.TemporaryDirectory(prefix="res0056-p2-") as tmp:
        root = Path(tmp)
        demo = run_demonstration(root)
        denied = root / "VIOLATION.txt"
        granted = root / "GRANTED.txt"
        synonym = root / "SYNONYM.txt"

        if denied.exists() or synonym.exists():
            print("FAILED:RES-0056-probe2 denied write leaked to disk")
            return 1
        if not granted.exists():
            print("FAILED:RES-0056-probe2 granted Write control did not write")
            return 1

    if not demo["same_violation_blocked_at_tool_layer"]:
        print("FAILED:RES-0056-probe2 tool layer did not block")
        return 1
    if not demo["tool_layer_both_states_control"]:
        print("FAILED:RES-0056-probe2 both-states control failed")
        return 1
    if not demo["lexical_filter_bypassed"]:
        print("FAILED:RES-0056-probe2 lexical bypass did not fire")
        return 1
    if not doc["demonstrations"]["same_violation_blocked_at_tool_layer"]:
        print("FAILED:RES-0056-probe2 artifact pairing flag false")
        return 1

    # Two HTTP rails per confirmed claim.
    for claim in doc.get("claims") or []:
        rails = claim.get("rails") or []
        kinds = {r.get("role") or r.get("kind") for r in rails}
        if claim.get("verdict") == "CONFIRMED" and len(rails) < 2:
            print("FAILED:RES-0056-probe2 single-rail claim", claim.get("id"))
            return 1
        if claim.get("verdict") == "CONFIRMED" and not ({"api", "prose"} <= kinds or {"api", "prose"} <= {r.get("kind") for r in rails}):
            # role field is api|prose
            roles = {r.get("role") for r in rails}
            if not {"api", "prose"} <= roles:
                print("FAILED:RES-0056-probe2 claim missing api+prose", claim.get("id"), roles)
                return 1
        for r in rails:
            if not r.get("permalink") or not r.get("sha256") or r.get("http_status") != 200:
                print("FAILED:RES-0056-probe2 incomplete rail", r)
                return 1

    print(json.dumps({
        "tool_stopped": True,
        "denied_file_exists": False,
        "granted_file_exists": True,
        "lexical_bypassed": True,
        "allowlist_held": True,
        "classification": "ENFORCED",
    }, sort_keys=True))
    print("tool_blocked=True both_states=True theatre_named=True")
    print("SUCCESS:RES-0056-probe2 same violation blocked at the tool layer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
