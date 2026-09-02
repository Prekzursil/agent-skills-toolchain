"""Attach a SCOPE-CHANGED pointer to register items whose stated action is now partly done.

THE HAZARD THIS PREVENTS, already measured once tonight: R-A22's `next_smallest_action` told the
next session to author a 344,197-byte artifact that already existed. An action line that describes
delivered work is worse than an open item -- it spends a whole session re-deriving it.

Lane A3 measured all twenty of its items and found EIGHT of the ten HARNESS rows have materially
reduced scope: parts are built, at paths nobody declared. None of them closes -- every one is
STAYS-OPEN or OWNER-GATED -- but every one's action line is now wider than the real residual.

WHY POINTERS AND NOT PROSE. I verified every CLOSE I applied by re-measuring its anchor myself. I
have NOT re-measured these eight, so copying A3's findings into `evidence` would present another
agent's measurement as my own -- the exact laundering the fan-out contract forbids. Instead each
item gets a `scope_note` naming the lane, the row, and the artifact to read. The catalog then POINTS
at evidence rather than asserting it, and the next reader knows the scope moved without being told a
number nobody re-checked.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
SOURCE = "command-center/CLOSE-PROPOSALS-A3.md"

#: id -> the one-line residual A3 measured. Deliberately terse: the artifact carries the evidence.
SCOPE = {
    "R-H01": "RESUME.json is 18 days stale AND factually wrong (two independent signals). One-file "
    "rewrite, but it writes into the LIVE continuation root, outside the lane's authority.",
    "R-H02": "Both .json twins confirmed absent, BUT WORK-UNIT-CATALOG.json is already a "
    "machine-readable reconciliation. Residual: add the ~14 missing fields and alias it, "
    "or emit the twin. Do not rebuild the reconciliation.",
    "R-H03": "All three filenames absent, BUT reachability -- the actual purpose -- is already "
    "computable via DEPENDENCY-GRAPH.json + validate.py, which prints it. Residual: the "
    "capability-preservation graph and the contracted filenames only.",
    "R-H04": "Reframed: deliver ONE interleave order plan. The two binaries are moot, and "
    "14-OWNER-DECISION-PACKET.md has functional equivalents under different names "
    "(OWNER-QUESTION-PACKET.md + OWNER-DECISIONS.md) -- a naming reconciliation, not loss.",
    "R-H05": "EVIDENCE/RUNS/DEPLOYMENTS.jsonl all absent, BUT CLAIM-REGISTRY.json is already a "
    "claim/evidence ledger. Residual reduced to RUNS + DEPLOYMENTS; propose aliasing the "
    "existing registry as EVIDENCE rather than duplicating it.",
    "R-H07": "Dep-blocked on R-H06. NOT-CHECKED by A3: the contract's verbatim 17-fix list was not "
    "located, so the residual size is unconfirmed.",
    "R-H08": "PARTLY REFUTED: 2 of the 3 named mechanisms are BUILT, at an undeclared path "
    "(skills/codex-databricks-fanout/scripts/harness/). Residual: timeout readback and a "
    "submission idempotency key.",
    "R-H09": "The safety question is ANSWERED -- projection is loss-free at name level, live-only "
    "skills = 0. Residual: per-file content direction, which A3 marks NOT-CHECKED.",
}


def main() -> int:
    raw = CATALOG.read_text(encoding="utf-8")
    doc = json.loads(raw)
    assert json.dumps(doc, indent=1, ensure_ascii=False) == raw, (
        "serialiser no longer round-trips this file byte-exactly; refusing to rewrite"
    )

    touched = []
    for item in doc["items"]:
        note = SCOPE.get(item["id"])
        if not note:
            continue
        if item.get("scope_note"):
            continue
        item["scope_note"] = (
            f"SCOPE REDUCED, not closed (2026-08-11). {note} "
            f"MEASURED BY lane A3, NOT re-verified by the orchestrator -- read {SOURCE} row "
            f"{item['id']} before acting, and re-measure before citing any figure from it. "
            "Recorded because an action line describing already-delivered work sends the next "
            "session to rebuild it; R-A22's did exactly that."
        )
        item.setdefault("history", []).append(
            {
                "event": "scope-pointer-added",
                "date": "2026-08-11",
                "source": SOURCE,
                "unchanged_fields": "status, disposition, next_smallest_action",
            }
        )
        touched.append(item["id"])

    if sorted(touched) != sorted(SCOPE):
        print(
            f"FAILED:scope-pointers expected {sorted(SCOPE)}, touched {sorted(touched)}"
        )
        return 1

    # Nothing may have been closed or re-dispositioned by this script.
    closed_now = [
        i["id"] for i in doc["items"] if i["id"] in SCOPE and i["status"] != "OPEN"
    ]
    if closed_now:
        print(f"FAILED:scope-pointers changed a status: {closed_now}")
        return 1

    CATALOG.write_text(
        json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8", newline=""
    )
    print(f"  scope_note added to {len(touched)}: {', '.join(sorted(touched))}")
    print("  status/disposition/next_smallest_action deliberately UNCHANGED on all 8")
    print("\nSUCCESS:scope-pointers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
