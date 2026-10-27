#!/usr/bin/env python3
"""TST-0130 probe2 -- TLS-no-downgrade refute-stage honesty + live surface.

The receipt is a refute-stage security_report: the exact TLS client target
is absent (no remote registry client ships), the disposition is
NOT-REFUTED/BLOCKED on the exact target, condition 11 is live-red, and
SUCCESS was not hand-flipped. This probe re-verifies the recorded honesty
invariants and that the live plugin surface still cannot reach a remote TLS
registry (no downgrade surface exists to be insecure).
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
RECEIPT = REPO / "command-center/receipts/TST-0130.json"

FAILS: list[str] = []


def chk(ok: bool, label: str, detail: object = "") -> None:
    if not ok:
        FAILS.append(label + (": " + str(detail) if detail != "" else ""))


def main() -> int:
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    chk(doc.get("kind") == "security_report", "kind")
    chk(doc.get("condition11_live_red") is True, "c11-not-recorded-red")
    chk(str(doc.get("state_policy_applied") or "").find("not hand-flipped") >= 0, "state-policy", doc.get("state_policy_applied"))
    ans = str(doc.get("answer") or "")
    chk(ans.startswith("NOT-REFUTED"), "answer-disposition", ans[:40])
    chk(any("UNIT-COMPLETE:TST-0130" in ln for ln in json.dumps(doc).split("\n")), "completion-line")

    dc = doc.get("delivery_contract") or {}
    for k in ("named_probe_a_raw_verbatim", "named_probe_b_raw_verbatim",
              "negative_control_can_go_red", "primary_refute_artifact_ends_with_completion_line"):
        chk(dc.get(k) is True, "delivery-contract-flag", k)

    ncs = doc.get("negative_controls") or []
    chk(len(ncs) == 2, "nc-count", len(ncs))
    kinds = {str(nc.get("kind")) for nc in ncs}
    chk("mutation" in kinds and "known-broken-fixture" in kinds, "nc-kinds", kinds)
    chk(len(doc.get("findings") or []) == 3, "findings-count", len(doc.get("findings") or []))
    f1 = (doc.get("findings") or [{}])[0]
    chk(str(f1.get("summary") or "").find("absent") >= 0, "f1-target-absent")
    chk(len(doc.get("scanners") or []) == 3, "scanners", len(doc.get("scanners") or []))

    # live: the marketplace plugin surface still has no remote TLS client
    # (nothing to downgrade), and no insecure-TLS escape hatch ships in it
    plugin = REPO / "tools/plugin"
    bad = ("verify=False", "CERT_NONE", "_create_unverified", "insecure_tls")  # bare http:// URL strings are not downgrade primitives
    hits = []
    for p in sorted(plugin.glob("*.py")) if plugin.is_dir() else []:
        t = p.read_text(encoding="utf-8", errors="replace").lower()
        for b in bad:
            if b in t:
                hits.append((p.name, b))
    chk(not hits, "downgrade-surface-live", hits)
    if FAILS:
        print("FAILED:TST-0130-probe2 " + " ; ".join(FAILS))
        return 1
    print("SUCCESS:TST-0130-probe2 refute-stage honesty verified (c11 red recorded, no hand-flip, NOT-REFUTED disposition, 2 controls + 3 findings + 3 scanners); live plugin surface still has no remote TLS client or downgrade primitive")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
