r"""Discharge the register items whose owner gates were just answered.

Validator check REACH-4 exists for exactly this: once a question is ANSWERED, the items it gated
must stop listing it as a live blocker and show a real next action instead. Answering OQ-1/OQ-2/OQ-8
without doing this leaves three items claiming to be blocked by questions that have answers -- which
is how a register accumulates phantom blockers.

R-A03 CLOSES. Its target is "the three Prompt-Two entry inputs were never filled - selected option
IDs (:10514), owner overrides/priorities (:10518), release mode (:10522)". All three are now filled:
OQ-1, OQ-2 and OQ-3 respectively. The item asked for the inputs to exist, and they do.

R-M18 does NOT close. OQ-8 answered the PRIORITY question; the enrolment itself is still work.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
REGISTER = REPO / "command-center/sources/REGISTER.md"

CLOSE = {
    "R-A03": (
        "ALL THREE ENTRY INPUTS ARE NOW FILLED, which is exactly what this item asked for. "
        "(1) Selected option IDs (:10514) = OQ-1, answered 2026-08-11: the 70 `owner_decisions` in "
        "07-OPTION-UNIVERSE.json, accepted verbatim. A reported 70-vs-123 conflict was investigated "
        "and DISSOLVED first - 123 is a BUCKET count at _USER-PROMPTS.md:28780, a different "
        "quantity, and three independent signals agree on 70. (2) Owner overrides and priority "
        "ordering (:10518) = OQ-2, answered: ascending phase, then unblocking power. (3) Release "
        "mode (:10522) = OQ-3, answered 2026-08-10: PR-ONLY. "
        "The `[PASTE SELECTED OPTION IDS HERE]` placeholder is no longer literal. "
        "SCOPE, disclosed: all three are DELEGATED DEFAULTS taken under an explicit owner "
        "instruction, not owner-authored selections - each answer_provenance says so and invites "
        "override. Closing this item unblocks its 6 still-open dependents "
        "(R-A02, R-A07, R-A08, R-A11, R-A16, R-A17), whose R-A03 edges were the last owner-gated "
        "link in that chain."
    ),
}

REGATE = {
    "R-M18": (
        "OQ-8 ANSWERED 2026-08-11 (delegated default): enrol the monitor cockpit at the same "
        "priority as the other MONITOR rows. The gate is discharged; the enrolment itself is still "
        "work, so this item stays OPEN with a real next action rather than closing on a ruling.",
        "Enrol the cockpit into the unified contract at normal MONITOR priority. It is already "
        "reachable - a [cockpit] stanza sits at line 58 of all three monitors.toml copies (R-M01, "
        "closed on that evidence) - so this is a contract/registration change, not a build.",
    ),
}


def main() -> int:
    raw = CATALOG.read_text(encoding="utf-8")
    doc = json.loads(raw)
    assert json.dumps(doc, indent=1, ensure_ascii=False) == raw, (
        "serialiser drift; refusing to write"
    )

    answered = {q["id"] for q in doc["owner_questions"] if q.get("state") == "ANSWERED"}
    closed, regated = [], []

    for item in doc["items"]:
        iid = item["id"]
        gates = list(item.get("owner_gate") or [])
        live = [g for g in gates if g not in answered]
        if gates and len(live) != len(gates):
            item["owner_gate"] = (
                live  # drop only the DISCHARGED gates, keep any still open
            )
            item.setdefault("history", []).append(
                {
                    "event": "owner-gate-discharged",
                    "date": "2026-08-11",
                    "discharged": [g for g in gates if g in answered],
                    "still_gated_by": live,
                }
            )
        if iid in CLOSE and not live:
            item["status"] = item["disposition"] = "DONE-VERIFIED"
            item["disposition_evidence"] = CLOSE[iid]
            closed.append(iid)
        elif iid in REGATE:
            ev, action = REGATE[iid]
            item["evidence"] = ev
            item["next_smallest_action"] = action
            regated.append(iid)

    CATALOG.write_text(
        json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8", newline=""
    )

    # Register status cells for anything closed, addressed by column index.
    if closed:
        reg = REGISTER.read_text(encoding="utf-8")
        eol = "\r\n" if "\r\n" in reg else "\n"
        lines = reg.split(eol)
        moved = []
        for n, line in enumerate(lines):
            if not line.lstrip().startswith("|"):
                continue
            parts = line.split("|")
            if len(parts) < 7 or parts[1].strip() not in closed:
                continue
            parts[3] = " DONE-VERIFIED "
            lines[n] = "|".join(parts)
            moved.append(parts[1].strip())
        REGISTER.write_text(eol.join(lines), encoding="utf-8", newline="")
        import hashlib

        lf = REGISTER.read_bytes().replace(b"\r\n", b"\n")
        doc["provenance"]["register_sha256"] = hashlib.sha256(lf).hexdigest()
        doc["provenance"]["register_bytes"] = len(lf)
        CATALOG.write_text(
            json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8", newline=""
        )
        print(f"  register rows moved: {moved}")

    still_open = sum(1 for i in doc["items"] if i["status"] == "OPEN")
    print(f"  CLOSED:  {', '.join(closed) or 'none'}")
    print(f"  REGATED: {', '.join(regated) or 'none'}")
    print(f"  items still OPEN: {still_open}")
    print("\nSUCCESS:clear-gates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
