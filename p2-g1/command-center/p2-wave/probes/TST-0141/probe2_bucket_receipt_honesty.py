#!/usr/bin/env python3
"""TST-0141 probe2 -- token-bucket receipt honesty (exact target absent).

The receipt honestly records: the exact B07 token-bucket target was absent
(exact_target_outcome=BLOCKED-NOT-RUN), the probe-local qualified property
run (10000 interleavings, 64 takers, seed 1410141, zero violations) whose
values came from the measured probe output, two open defects, and withheld
SUCCESS while condition 11 is red. This probe re-verifies those honesty
invariants and that the absent target is still absent live.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
RECEIPT = REPO / "command-center/receipts/TST-0141.json"

FAILS: list[str] = []


def chk(ok: bool, label: str, detail: object = "") -> None:
    if not ok:
        FAILS.append(label + (": " + str(detail) if detail != "" else ""))


def main() -> int:
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    chk(doc.get("exact_target_outcome") == "BLOCKED-NOT-RUN", "exact-target-outcome", doc.get("exact_target_outcome"))
    chk(doc.get("success_withheld_while_condition11_red") is True, "withheld-flag")
    chk(str(doc.get("sentinel") or "").startswith("FAILED:TST-0141"), "sentinel-honesty")
    chk(any("UNIT-COMPLETE:TST-0141" in ln for ln in json.dumps(doc).splitlines()), "completion-line")

    prop = doc.get("property") or {}
    chk(prop.get("n") == 10000 and prop.get("n_takers") == 64, "property-shape", (prop.get("n"), prop.get("n_takers")))
    chk(prop.get("runs_completed") == 10000, "runs-completed")
    chk(prop.get("failures") == [] and prop.get("ok") is True, "property-not-clean")
    chk(int(prop.get("seed") or 0) == 1410141, "seed", prop.get("seed"))
    chk("probe1 output" in str(prop.get("source") or ""), "honest-source-note")

    defects = doc.get("defects") or []
    ids = {str(d.get("id")) for d in defects}
    chk({"TST-0141-D1", "TST-0141-D2"} <= ids and len(defects) == 2, "defects", ids)
    chk(all(d.get("status") == "open" for d in defects), "defects-closed")

    cloud = doc.get("cloud_ok_local_revalidation") or {}
    chk(cloud.get("state_not_flipped") is True, "state-flipped")
    chk(cloud.get("registered_not_flipped") is True, "registered-flipped")
    chk(str(cloud.get("live_condition11_first_red") or "").startswith("FAILED:"), "c11-first-red")

    ws = doc.get("window_semantics") or ""
    chk("no refill within a case" in ws, "window-semantics", ws)
    nfiles = doc.get("named_probe_files") or {}
    chk(len(nfiles) == 2, "named-probe-files", len(nfiles))
    for k, rel in nfiles.items():
        chk(not (REPO / str(rel)).is_file(), "dropped-sidecar-present", k)
    # the production B07 bucket surface the unit targeted is still absent
    prod = list((REPO / "tools").rglob("*token_bucket*.py")) if (REPO / "tools").is_dir() else []
    chk(not prod, "production-bucket-present-live", [str(p) for p in prod])
    if FAILS:
        print("FAILED:TST-0141-probe2 " + " ; ".join(FAILS))
        return 1
    print("SUCCESS:TST-0141-probe2 honesty receipt verified: exact target absent live and recorded so; probe-local property (10000x64, seed 1410141, 0 violations) recorded with honest source note; 2 open defects; no state/registration flips; dropped sidecars still dropped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
