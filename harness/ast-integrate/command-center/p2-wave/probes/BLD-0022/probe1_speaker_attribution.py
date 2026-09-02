#!/usr/bin/env python3
"""Named probe 1: speaker-attribution control.

An agent-authored sentence must never classify OWNER-EXPLICIT. Both-states:
the owner fixture is EXPLICIT; the same wording in the agent fixture is not.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import classify as C  # noqa: E402
import corpus as CORP  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0022.json"


def fail(msg: str) -> int:
    print(f"FAILED:BLD-0022-probe1 {msg}")
    return 1


def main() -> int:
    utts = CORP.load_fixture_utterances()
    speakers = {u.speaker for u in utts}
    if speakers != {"owner", "agent"}:
        return fail(f"fixture speakers={speakers}")

    owner_v = C.classify("CTRL-OWNER-1", utts)
    agent_v = C.classify("CTRL-AGENT-1", utts)

    if owner_v.classification != C.OWNER_EXPLICIT:
        return fail(f"good-state owner wording -> {owner_v.classification}")
    if owner_v.owner_quote_anchor is None or "owner-select.md" not in (
        owner_v.owner_quote_anchor or ""
    ):
        return fail(f"owner quote anchor {owner_v.owner_quote_anchor}")
    if agent_v.classification == C.OWNER_EXPLICIT:
        return fail("agent wording classified OWNER-EXPLICIT (speaker leak)")
    if agent_v.owner_quote is not None:
        return fail("agent sentence stored as owner_quote")

    # Mutant: relabel the agent file as owner. That MUST flip CTRL-AGENT-1
    # to OWNER-EXPLICIT, proving the speaker field is load-bearing.
    mutant = [
        C.Utterance(
            speaker="owner" if "agent-select.md" in u.path else u.speaker,
            path=u.path,
            line=u.line,
            text=u.text,
        )
        for u in utts
    ]
    mutant_v = C.classify("CTRL-AGENT-1", mutant)
    if mutant_v.classification != C.OWNER_EXPLICIT:
        return fail(
            "speaker-swap mutant did not become OWNER-EXPLICIT; "
            "control would be silent in both states"
        )

    implied = C.classify("CTRL-IMPLIED-1", utts)
    if implied.classification != C.OWNER_IMPLIED:
        return fail(f"CTRL-IMPLIED-1 -> {implied.classification}")

    if ART.is_file() and ART.stat().st_size > 0:
        doc = json.loads(ART.read_text(encoding="utf-8"))
        for row in list(doc.get("selected_options") or []) + list(
            doc.get("control_classifications") or []
        ):
            if row.get("classification") != C.OWNER_EXPLICIT:
                continue
            quote = str(row.get("owner_quote") or "")
            anchor = str(row.get("owner_quote_anchor") or "")
            if not quote or not anchor:
                return fail(f"OWNER-EXPLICIT {row.get('id')} missing quote")
            if "agent-select.md" in anchor:
                return fail(f"OWNER-EXPLICIT {row.get('id')} cites agent file")

    out = {
        "probe": "probe1-speaker-attribution",
        "unit_id": "BLD-0022",
        "owner_explicit": owner_v.classification,
        "agent_not_explicit": agent_v.classification,
        "mutant_flips_to_explicit": mutant_v.classification == C.OWNER_EXPLICIT,
        "implied": implied.classification,
        "fired_on_bad": True,
        "silent_on_good": owner_v.classification == C.OWNER_EXPLICIT,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:BLD-0022-probe1 speaker-attribution both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
